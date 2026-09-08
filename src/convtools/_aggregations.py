"""Define aggregations with various reduce functions."""

import ast
import copy
import warnings
from collections import defaultdict, deque
from decimal import Decimal
from math import ceil
from typing import Any, Callable, ClassVar, Dict, Sequence, Tuple, Union, cast

from ._base import (
    BaseConversion,
    CallFunc,
    ConversionException,
    ConverterOptionsCtx,
    DictComp,
    EscapedString,
    GeneratorComp,
    GeneratorItem,
    GetItem,
    If,
    InlineExpr,
    LazyEscapedString,
    List_,
    ListComp,
    NaiveConversion,
    Namespace,
    NamespaceCtx,
    Or,
    This,
    Tuple_,
    _None,
    _none,
)
from ._heuristics import Weights
from ._utils import Code, ast_unparse

_NAMED_EXPR = getattr(ast, "NamedExpr", None)
_BINDER_TYPES = tuple(
    t
    for t in (
        ast.Lambda,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
        _NAMED_EXPR,
    )
    if t is not None
)

_HOISTABLE_TYPES = (
    ast.Subscript,
    ast.Attribute,
    ast.Call,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.BoolOp,
    ast.IfExp,
)

_TEMPLATE_INFO_CACHE = {}  # type: Dict[Tuple[Any, ...], Tuple[Any, ...]]


def _is_binder(node):
    return isinstance(node, _BINDER_TYPES)


def _is_hoistable(node):
    return isinstance(node, _HOISTABLE_TYPES)


def _node_size(node):
    return sum(1 for _ in ast.walk(node))


def _opaque_eager_parts(node):
    if isinstance(node, ast.Lambda):
        args = node.args
        for default in list(args.defaults or []):
            if default is not None:
                yield default
        for default in list(getattr(args, "kw_defaults", None) or []):
            if default is not None:
                yield default
        return
    if isinstance(
        node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    ):
        if node.generators:
            yield node.generators[0].iter
        return


def _walk_expr_children_skip_binders(node, eager_only):
    if _is_binder(node):
        for part in _opaque_eager_parts(node):
            yield part
        return
    if eager_only:
        if isinstance(node, ast.BoolOp):
            if node.values:
                yield node.values[0]
            return
        if isinstance(node, ast.IfExp):
            yield node.test
            return
        if isinstance(node, ast.Compare):
            yield node.left
            if node.comparators:
                yield node.comparators[0]
            return
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            yield child
        elif _is_binder(child):
            for part in _opaque_eager_parts(child):
                yield part
        else:
            for grandchild in ast.iter_child_nodes(child):
                if isinstance(grandchild, ast.expr):
                    yield grandchild


def _walk_tree(node, eager_only):
    stack = list(_walk_expr_children_skip_binders(node, eager_only))
    while stack:
        current = stack.pop()
        yield current
        stack.extend(_walk_expr_children_skip_binders(current, eager_only))


def _iter_hoistable(node):
    if _is_hoistable(node):
        yield node
    for child in _walk_tree(node, eager_only=False):
        if _is_hoistable(child):
            yield child


def _iter_eager(node):
    yield node
    for child in _walk_tree(node, eager_only=True):
        yield child


def _parse_expr(code):
    if not code or not str(code).strip():
        return None
    try:
        return ast.parse(code, mode="eval").body
    except SyntaxError:
        return None


def _fmt_expr(node, original=None, rewritten=False):
    if not rewritten and original is not None:
        return original
    code = ast_unparse(node).strip()
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
        return code
    return "({})".format(code)


class _ReplaceDumps(ast.NodeTransformer):
    def __init__(self, dump_to_name):
        self.dump_to_name = dump_to_name
        self.changed = False

    def visit(self, node):
        if isinstance(node, ast.expr):
            name = self.dump_to_name.get(ast.dump(node))
            if name is not None:
                self.changed = True
                return ast.Name(id=name, ctx=ast.Load())
        if _is_binder(node):
            return self._visit_binder(node)
        return self.generic_visit(node)

    def _visit_binder(self, node):
        if isinstance(node, ast.Lambda):
            new_args = self._visit_lambda_args(node.args)
            if new_args is node.args:
                return node
            new_node = ast.Lambda(args=new_args, body=node.body)
            return ast.copy_location(new_node, node)
        if isinstance(
            node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            if not node.generators:
                return node
            first = node.generators[0]
            new_iter = self.visit(first.iter)
            if new_iter is first.iter:
                return node
            new_first = ast.comprehension(
                target=first.target,
                iter=new_iter,
                ifs=first.ifs,
                is_async=getattr(first, "is_async", 0),
            )
            new_gens = [new_first] + list(node.generators[1:])
            kwargs = {"generators": new_gens}
            if isinstance(node, ast.DictComp):
                kwargs["key"] = node.key
                kwargs["value"] = node.value
            else:
                kwargs["elt"] = node.elt
            return ast.copy_location(type(node)(**kwargs), node)
        return node

    def _visit_lambda_args(self, args):
        new_defaults = [
            self.visit(d) if d is not None else d for d in args.defaults
        ]
        kw_defaults = getattr(args, "kw_defaults", None)
        new_kw = None
        if kw_defaults is not None:
            new_kw = [
                self.visit(d) if d is not None else d for d in kw_defaults
            ]
        if new_defaults == list(args.defaults) and (
            kw_defaults is None or new_kw == list(kw_defaults)
        ):
            return args
        kwargs = dict(
            args=args.args,
            vararg=args.vararg,
            kwarg=args.kwarg,
            defaults=new_defaults,
        )
        for attr in ("posonlyargs", "kwonlyargs", "kw_defaults"):
            if hasattr(args, attr):
                kwargs[attr] = (
                    new_kw if attr == "kw_defaults" else getattr(args, attr)
                )
        return ast.arguments(**kwargs)


def _replace_dumps(node, dump_to_name):
    if node is None:
        return None, False
    transformer = _ReplaceDumps(dump_to_name)
    new_node = transformer.visit(node)
    return new_node, transformer.changed


def _rename_names(node, old_to_new):
    class _Renamer(ast.NodeTransformer):
        def visit_Name(self, name_node):
            new_id = old_to_new.get(name_node.id)
            if new_id is None:
                return name_node
            return ast.Name(id=new_id, ctx=name_node.ctx)

    return _Renamer().visit(node)


def _if_has_complete_else(if_stmt):
    orelse = if_stmt.orelse
    if not orelse:
        return False
    if len(orelse) == 1 and isinstance(orelse[0], ast.If):
        return _if_has_complete_else(orelse[0])
    return True


def _if_branch_bodies(if_stmt):
    """If/elif/else statement bodies; elif tests are not included."""
    bodies = [if_stmt.body]
    orelse = if_stmt.orelse
    while len(orelse) == 1 and isinstance(orelse[0], ast.If):
        bodies.append(orelse[0].body)
        orelse = orelse[0].orelse
    if orelse:
        bodies.append(orelse)
    return bodies


def _add_counts(left, right):
    return [a + b for a, b in zip(left, right)]


def _max_counts(left, right):
    return [max(a, b) for a, b in zip(left, right)]


def _count_sentinels(node, sentinel_to_index, n_values):
    counts = [0] * n_values
    if node is None:
        return counts
    names = []
    if isinstance(node, ast.Name):
        names.append(node)
    names.extend(
        n
        for n in _walk_tree(node, eager_only=False)
        if isinstance(n, ast.Name)
    )
    for name_node in names:
        index = sentinel_to_index.get(name_node.id)
        if index is not None:
            counts[index] += 1
    return counts


def _mark_eager_expr(node, sentinel_to_index, eager):
    if node is None:
        return
    names = []
    if isinstance(node, ast.Name):
        names.append(node)
    names.extend(
        n for n in _walk_tree(node, eager_only=True) if isinstance(n, ast.Name)
    )
    for name_node in names:
        index = sentinel_to_index.get(name_node.id)
        if index is not None:
            eager[index] = True


def _stmt_evaled_exprs(stmt):
    if isinstance(stmt, ast.Assign):
        yield stmt.value
        for target in stmt.targets:
            yield target
        return
    if isinstance(stmt, ast.AugAssign):
        yield stmt.value
        yield stmt.target
        return
    if isinstance(stmt, ast.AnnAssign):
        if stmt.value is not None:
            yield stmt.value
        yield stmt.target
        return
    if isinstance(stmt, ast.Expr):
        yield stmt.value
        return
    if isinstance(stmt, ast.Return) and stmt.value is not None:
        yield stmt.value


def _weight_block(stmts, sentinel_to_index, n_values):
    total = [0] * n_values
    for stmt in stmts:
        total = _add_counts(
            total, _weight_stmt(stmt, sentinel_to_index, n_values)
        )
    return total


def _weight_stmt(stmt, sentinel_to_index, n_values):
    if isinstance(stmt, ast.If):
        weights = _count_sentinels(stmt.test, sentinel_to_index, n_values)
        body_w = _weight_block(stmt.body, sentinel_to_index, n_values)
        else_w = _weight_block(stmt.orelse, sentinel_to_index, n_values)
        return _add_counts(weights, _max_counts(body_w, else_w))
    exprs = list(_stmt_evaled_exprs(stmt))
    if exprs:
        total = [0] * n_values
        for expr in exprs:
            total = _add_counts(
                total, _count_sentinels(expr, sentinel_to_index, n_values)
            )
        return total
    total = [0] * n_values
    for child in ast.iter_child_nodes(stmt):
        if isinstance(child, ast.expr):
            total = _add_counts(
                total, _count_sentinels(child, sentinel_to_index, n_values)
            )
        elif isinstance(child, ast.stmt):
            total = _add_counts(
                total, _weight_stmt(child, sentinel_to_index, n_values)
            )
    return total


def _mark_eager_block(stmts, sentinel_to_index, eager, tests_are_top_level):
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            if tests_are_top_level:
                _mark_eager_expr(stmt.test, sentinel_to_index, eager)
            if _if_has_complete_else(stmt):
                n = len(eager)
                branch_flags = []
                for body in _if_branch_bodies(stmt):
                    flags = [False] * n
                    _mark_eager_block(body, sentinel_to_index, flags, True)
                    branch_flags.append(flags)
                for i in range(n):
                    if all(flags[i] for flags in branch_flags):
                        eager[i] = True
            continue
        for expr in _stmt_evaled_exprs(stmt):
            _mark_eager_expr(expr, sentinel_to_index, eager)


def _analyze_template_block(lines, n_values):
    eager = [False] * n_values
    weights = [0] * n_values
    if not lines:
        return eager, weights
    sentinels = ["_red_val_{}_".format(i) for i in range(n_values)]
    sentinel_to_index = {name: i for i, name in enumerate(sentinels)}
    kwargs = {"result": "_red_result_", "row": "_red_row_"}
    for i, name in enumerate(sentinels):
        kwargs["value{}".format(i)] = name
    try:
        rendered = "\n".join(line % kwargs for line in lines)
        if not rendered.strip():
            return eager, weights
        tree = ast.parse(rendered)
    except (SyntaxError, TypeError, ValueError, KeyError):
        for i in range(n_values):
            placeholder = "%(value{})s".format(i)
            total = sum(line.count(placeholder) for line in lines)
            weights[i] = total
            eager[i] = total > 0
        return eager, weights
    _mark_eager_block(tree.body, sentinel_to_index, eager, True)
    weights = _weight_block(tree.body, sentinel_to_index, n_values)
    return eager, weights


def _template_info(prepare_lines, reduce_lines, n_values):
    key = (prepare_lines, reduce_lines, n_values)
    cached = _TEMPLATE_INFO_CACHE.get(key)
    if cached is not None:
        return cached
    init_eager, init_weight = _analyze_template_block(prepare_lines, n_values)
    reduce_eager, reduce_weight = _analyze_template_block(
        reduce_lines, n_values
    )
    info = (init_eager, init_weight, reduce_eager, reduce_weight)
    _TEMPLATE_INFO_CACHE[key] = info
    return info


class _CountItem(object):
    __slots__ = [
        "code",
        "tree",
        "weight",
        "is_self_eager_root",
        "kind",
        "record",
        "index",
        "child",
        "rewritten",
    ]

    def __init__(
        self,
        code,
        weight,
        is_self_eager_root,
        kind,
        record=None,
        index=None,
        child=None,
        tree=None,
        rewritten=False,
    ):
        self.code = code
        self.weight = weight
        self.is_self_eager_root = is_self_eager_root
        self.kind = kind
        self.record = record
        self.index = index
        self.child = child
        self.rewritten = rewritten
        self.tree = tree if tree is not None else _parse_expr(code)


class ReducerRecord(object):
    __slots__ = [
        "slot",
        "where_code",
        "value_codes",
        "not_none_flags",
        "prepare_first_lines",
        "reduce_lines",
        "initial_code",
        "row_code",
        "guard_chain",
    ]

    def __init__(
        self,
        where_code,
        value_codes,
        not_none_flags,
        prepare_first_lines,
        reduce_lines,
        initial_code,
        row_code,
    ):
        self.slot = None
        self.where_code = where_code
        self.value_codes = value_codes
        self.not_none_flags = not_none_flags
        self.prepare_first_lines = prepare_first_lines
        self.reduce_lines = reduce_lines
        self.initial_code = initial_code
        self.row_code = row_code
        self.guard_chain = None

    def dedup_key(self):
        # row_code is part of the identity: MaxRow/MinRow (and any template
        # using %(row)s) capture the piped input, not only the comparison value.
        return (
            self.where_code,
            self.value_codes,
            self.not_none_flags,
            self.prepare_first_lines,
            self.reduce_lines,
            self.initial_code,
            self.row_code,
        )


class GuardScope(object):
    __slots__ = ["reducers", "children"]

    def __init__(self):
        self.reducers = []
        self.children = {}


class SharingPlan(object):
    __slots__ = ["values", "guards", "signature", "temps"]

    def __init__(self):
        self.values = {}
        self.guards = {}
        self.signature = None
        self.temps = {}


def _build_guard_tree(records):
    root = GuardScope()
    for record in records:
        node = root
        for guard in record.guard_chain:
            child = node.children.get(guard)
            if child is None:
                child = GuardScope()
                node.children[guard] = child
            node = child
        node.reducers.append(record)
    return root


def _eager_and_weight(record, with_init):
    n_values = len(record.value_codes)
    init_eager, init_weight, reduce_eager, reduce_weight = _template_info(
        record.prepare_first_lines, record.reduce_lines, n_values
    )
    if with_init:
        eager = []
        weights = []
        reduce_is_empty = not record.reduce_lines
        for i in range(n_values):
            red_eager = False if reduce_is_empty else reduce_eager[i]
            eager.append(bool(init_eager[i] and red_eager))
            weights.append(max(init_weight[i], reduce_weight[i]))
        return eager, weights
    return list(reduce_eager), list(reduce_weight)


def _collect_count_items(scope, plan, with_init, self_scope, signature, items):
    for record in scope.reducers:
        eager_flags, weights = _eager_and_weight(record, with_init)
        codes = plan.values[id(record)]
        for i, code in enumerate(codes):
            items.append(
                _CountItem(
                    code,
                    weights[i],
                    scope is self_scope and eager_flags[i],
                    "value",
                    record=record,
                    index=i,
                )
            )
    for guard, child in scope.children.items():
        gcode = plan.guards.get(id(child), guard)
        items.append(
            _CountItem(
                gcode,
                1,
                scope is self_scope,
                "guard",
                child=child,
            )
        )
        _collect_count_items(
            child, plan, with_init, self_scope, signature, items
        )
    if signature is not None and scope is self_scope:
        items.append(_CountItem(plan.signature, 1, True, "signature"))


def _topo_temp_order(temp_entries):
    names = [name for name, _tree in temp_entries]
    name_set = set(names)
    depends = {name: set() for name in names}
    for name, tree in temp_entries:
        if tree is None:
            continue
        found = []
        if isinstance(tree, ast.Name) and tree.id in name_set:
            found.append(tree.id)
        for child in _walk_tree(tree, eager_only=False):
            if isinstance(child, ast.Name) and child.id in name_set:
                found.append(child.id)
        depends[name].update(found)
    remaining = set(names)
    ordered = []
    while remaining:
        ready = [
            name
            for name in names
            if name in remaining and not (depends[name] & remaining)
        ]
        if not ready:
            ordered.extend(n for n in names if n in remaining)
            break
        for name in ready:
            remaining.remove(name)
            ordered.append(name)
    by_name = dict(temp_entries)
    return [(name, by_name[name]) for name in ordered]


def _analyze_scope(scope, plan, with_init, signature, tmp_index):
    # Safety: an expression is evaluated only on rows where some naive
    # per-reducer use would have evaluated it, never above its guards, and
    # initial expressions are never shared. Reducer where/value expressions
    # are treated as deterministic and free of side effects on the row;
    # shared values are the same object in every reducer; reducer callables
    # must not mutate the values they receive.
    items = []
    _collect_count_items(scope, plan, with_init, scope, signature, items)
    local_temps = []
    local_i = 0
    while True:
        candidates = {}
        for item in items:
            if item.tree is None:
                continue
            eager_dumps = set()
            if item.is_self_eager_root:
                for node in _iter_eager(item.tree):
                    if _is_hoistable(node):
                        eager_dumps.add(ast.dump(node))
            for node in _iter_hoistable(item.tree):
                dumped = ast.dump(node)
                rec = candidates.get(dumped)
                if rec is None:
                    rec = {
                        "size": _node_size(node),
                        "count": 0,
                        "eager_ok": False,
                        "node": node,
                    }
                    candidates[dumped] = rec
                rec["count"] += item.weight
                if dumped in eager_dumps:
                    rec["eager_ok"] = True
        best = None
        best_key = None
        for dumped, rec in candidates.items():
            if rec["count"] < 2 or not rec["eager_ok"]:
                continue
            key = (rec["size"], rec["count"], dumped)
            if best is None or key > best:
                best = key
                best_key = dumped
        if best_key is None:
            break
        rec = candidates[best_key]
        internal_name = "__cse{}_{}_".format(id(scope) % 100000, local_i)
        local_i += 1
        rhs_tree = copy.deepcopy(rec["node"])
        mapping = {best_key: internal_name}
        for item in items:
            new_tree, changed = _replace_dumps(item.tree, mapping)
            if changed:
                item.tree = new_tree
                item.rewritten = True
        items.append(
            _CountItem(
                _fmt_expr(rhs_tree, rewritten=True),
                1,
                True,
                "temp_rhs",
                tree=rhs_tree,
                rewritten=True,
            )
        )
        local_temps.append((internal_name, rhs_tree))

    ordered = _topo_temp_order(local_temps)
    old_to_new = {}
    emitted = []
    for internal_name, tree in ordered:
        public_name = "_tmp{}_".format(tmp_index)
        tmp_index += 1
        old_to_new[internal_name] = public_name
        emitted.append((public_name, tree))
    if old_to_new:
        for item in items:
            if item.tree is not None:
                item.tree = _rename_names(item.tree, old_to_new)
        emitted = [
            (
                name,
                _rename_names(tree, old_to_new) if tree is not None else tree,
            )
            for name, tree in emitted
        ]

    plan.temps[id(scope)] = [
        (name, _fmt_expr(tree, rewritten=True) if tree is not None else "None")
        for name, tree in emitted
    ]

    for item in items:
        if item.kind == "temp_rhs":
            continue
        new_code = _fmt_expr(item.tree, item.code, item.rewritten)
        if item.kind == "value":
            codes = list(plan.values[id(item.record)])
            codes[item.index] = new_code
            plan.values[id(item.record)] = tuple(codes)
        elif item.kind == "guard":
            plan.guards[id(item.child)] = new_code
        elif item.kind == "signature":
            plan.signature = new_code

    for child in scope.children.values():
        tmp_index = _analyze_scope(child, plan, with_init, None, tmp_index)
    return tmp_index


def _init_plan(root, records, signature):
    plan = SharingPlan()
    for record in records:
        plan.values[id(record)] = record.value_codes
    plan.signature = signature
    return plan


def _count_reducer_nodes(node):
    total = 1 if node.reducers else 0
    for child in node.children.values():
        total += _count_reducer_nodes(child)
    return total


class ReduceManager:
    """Build group by / aggregate code."""

    __slots__ = [
        "var_row",
        "var_agg_data",
        "aggregate_mode",
        "var_agg_data_to_index",
        "records",
        "dedup",
    ]

    def __init__(self, var_row, var_agg_data, aggregate_mode):
        self.var_row = var_row
        self.var_agg_data = var_agg_data
        self.aggregate_mode = aggregate_mode
        self.var_agg_data_to_index = {}
        self.records = []
        self.dedup = {}

    def gen_agg_data_value(self):
        index = len(self.records)
        var_agg_data_value = self.fmt_agg_data_value(index)
        self.var_agg_data_to_index[var_agg_data_value] = index
        return var_agg_data_value

    def add_reducer_code(self, record):
        key = record.dedup_key()
        existing = self.dedup.get(key)
        if existing is not None:
            return existing.slot
        slot = self.gen_agg_data_value()
        record.slot = slot
        chain = []
        if record.where_code is not None:
            chain.append(record.where_code)
        for code, flag in zip(record.value_codes, record.not_none_flags):
            if flag:
                chain.append("{} is not None".format(code))
        record.guard_chain = tuple(chain)
        self.records.append(record)
        self.dedup[key] = record
        return slot

    def fmt_agg_data_value(self, index):
        return (
            "{}_v{}".format(self.var_agg_data, index)
            if self.aggregate_mode
            else "{}.v{}".format(self.var_agg_data, index)
        )

    def _record_kwargs(self, record, plan):
        kwargs = {"result": record.slot, "row": record.row_code}
        codes = plan.values[id(record)]
        for i, code in enumerate(codes):
            kwargs["value{}".format(i)] = code
        return kwargs

    def _emit_lines(self, code, lines, record, plan):
        if not lines:
            return
        kwargs = self._record_kwargs(record, plan)
        for line in lines:
            code.add_line(line % kwargs, 0)

    def _emit_scope(self, code, node, plan, with_init, after_temps=None):
        for tmp_name, tmp_code in plan.temps.get(id(node), ()):
            code.add_line("{} = {}".format(tmp_name, tmp_code), 0)
        if after_temps is not None:
            after_temps()
        if with_init and node.reducers:
            first_slot = node.reducers[0].slot
            code.add_line("if {} is _none:".format(first_slot), 1)
            for record in node.reducers:
                self._emit_lines(
                    code, record.prepare_first_lines, record, plan
                )
            if self.aggregate_mode:
                code.add_line("checksum_ += 1", 0)
            if any(record.reduce_lines for record in node.reducers):
                code.incr_indent_level(-1)
                code.add_line("else:", 1)
                for record in node.reducers:
                    self._emit_lines(code, record.reduce_lines, record, plan)
            code.incr_indent_level(-1)
        elif not with_init and node.reducers:
            for record in node.reducers:
                self._emit_lines(code, record.reduce_lines, record, plan)
        for guard, child in node.children.items():
            rewritten = plan.guards.get(id(child), guard)
            code.add_line("if {}:".format(rewritten), 1)
            self._emit_scope(code, child, plan, with_init)
            code.incr_indent_level(-1)

    def gen_group_by_code(self, var_signature_to_agg_data, code_signature):
        root = _build_guard_tree(self.records)
        plan = _init_plan(root, self.records, code_signature)
        _analyze_scope(root, plan, True, code_signature, 0)
        code = Code()
        code.add_line("for {} in data_:".format(self.var_row), 1)

        def _assign_agg_data():
            code.add_line(
                "{} = {}[{}]".format(
                    self.var_agg_data,
                    var_signature_to_agg_data,
                    plan.signature,
                ),
                0,
            )

        self._emit_scope(code, root, plan, True, after_temps=_assign_agg_data)
        return code

    def gen_aggregate_code(self):
        code = Code()
        if not self.records:
            return code
        with_init_root = _build_guard_tree(self.records)
        with_init_plan = _init_plan(with_init_root, self.records, None)
        _analyze_scope(with_init_root, with_init_plan, True, None, 0)
        expected_checksum = _count_reducer_nodes(with_init_root)

        reduce_records = [r for r in self.records if r.reduce_lines]
        reduce_root = (
            _build_guard_tree(reduce_records) if reduce_records else None
        )
        reduce_plan = None
        if reduce_root is not None:
            reduce_plan = _init_plan(reduce_root, reduce_records, None)
            _analyze_scope(reduce_root, reduce_plan, False, None, 0)

        code.add_line("checksum_ = 0", 0)
        if reduce_records:
            code.add_line("it_ = iter(data_)", 0)
            code.add_line("for {} in it_:".format(self.var_row), 1)
        else:
            code.add_line("for {} in data_:".format(self.var_row), 1)
        self._emit_scope(code, with_init_root, with_init_plan, True)
        code.add_line("if checksum_ == {}:".format(expected_checksum), 1)
        if ConverterOptionsCtx.get_option_value("debug"):
            code.add_line(
                "globals()['__BROKEN_EARLY__'] = True  # DEBUG ONLY",
                0,
            )
        code.add_line("break", -2)

        if reduce_records:
            code.add_line("for {} in it_:".format(self.var_row), 1)
            self._emit_scope(code, reduce_root, reduce_plan, False)
        return code

    def gen_group_by_data_container(self, grouper, container_name, ctx):
        attrs = [
            "v{}".format(self.var_agg_data_to_index[record.slot])
            for record in self.records
        ]
        code = Code()
        code.add_line("class {}:".format(container_name), 1)
        joined = ",".join("'{}'".format(attr) for attr in attrs)
        code.add_line("__slots__ = [{}]".format(joined), 0)
        code.add_line("def __init__(self, _none=__none__):", 1)
        if attrs:
            for attr in attrs:
                code.add_line("self.{} = _none".format(attr), 0)
        else:
            code.add_line("pass", 0)
        return ctx[
            grouper.compile_converter(container_name, code.to_string(0), ctx)
        ]

    def gen_init_aggregate_vars(self):
        if not self.records:
            return ""
        vars_code = " = ".join(
            [
                self.fmt_agg_data_value(
                    self.var_agg_data_to_index[record.slot]
                )
                for record in self.records
            ]
        )
        return "{} = _none".format(vars_code)


class BaseReducer(BaseConversion):
    """Base reduce operation to be used during the aggregation."""

    _expressions: Sequence[BaseConversion]

    default: Union[_None, BaseConversion] = _none
    initial: Union[_None, BaseConversion] = _none
    internals_are_public: bool
    # works_with_not_none_only: Union[Tuple[int, ...], Callable]
    # prepare_first_lines: Union[Tuple[str, ...], Callable]
    # reduce_lines: Union[Tuple[str, ...], Callable]
    where: Union[_None, BaseConversion]

    self_content_type = (
        (
            BaseConversion.self_content_type
            & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
        )
        | BaseConversion.ContentTypes.REDUCER
        | BaseConversion.ContentTypes.NONE_USAGE
    )

    def __init__(self, *expressions, initial=_none, default=_none, where=None):
        super().__init__()
        self.expressions = tuple(
            self.ensure_conversion(expression) for expression in expressions
        )
        self.default, self.initial = self.prepare_default_n_initial(
            default, initial
        )
        self.check_expressions()
        self.where = (
            _none
            if (where is None or where is _none)
            else self.ensure_conversion(where)
        )

    def check_expressions(self):
        if not self.internals_are_public and not isinstance(
            self.initial, _None
        ):
            warnings.warn(
                "2.0 will raise ValueError if initial is "
                f"passed to {self.__class__.__name__}",
                DeprecationWarning,
                stacklevel=1,
            )

    def prepare_default_n_initial(self, default, initial):
        if default is _none:
            default = self.default
        if initial is _none:
            initial = self.initial

        if initial is not _none:
            initial = self.ensure_conversion(initial)
            # Only auto-call naive Python callables (e.g. list, lambda: 0);
            # calling a bound InlineExpr (e.g. c.this % 3) would be wrong.
            if isinstance(initial, NaiveConversion) and callable(
                initial.value
            ):
                initial = initial.call()

            if default is _none and initial.ignores_input():
                default = initial

        if default is _none:
            raise ValueError("default is not provided")

        default = self.ensure_conversion(default)
        if isinstance(default, NaiveConversion) and callable(default.value):
            default = default.call()

        return default, initial

    def get_option(self, name, ctx, default=_none):
        if default is _none:
            option_value = getattr(self, name)
        else:
            option_value = getattr(self, name, default)
        if callable(option_value):
            return option_value(ctx)
        return option_value

    def gen_code_and_update_ctx(self, code_input, ctx) -> str:
        reduce_manager: ReduceManager = ctx["current_reduce_manager"][-1]

        where_code = None
        if not isinstance(self.where, _None):
            where_code = self.where.gen_code_and_update_ctx(code_input, ctx)

        works_with_not_none_only = self.get_option(
            "works_with_not_none_only", ctx
        )
        value_codes = []
        not_none_flags = []
        for index, expression in enumerate(self.expressions):
            expression_code = expression.gen_code_and_update_ctx(
                code_input, ctx
            )
            value_codes.append(expression_code)
            not_none_flags.append(
                bool(works_with_not_none_only[index])
                and not expression.has_hint(
                    BaseConversion.OutputHints.NOT_NONE
                )
            )

        reduce_lines = tuple(self.get_option("reduce_lines", ctx) or ())
        initial_code = None
        if not isinstance(self.initial, _None) and self.internals_are_public:
            initial_code = self.initial.gen_code_and_update_ctx(
                code_input, ctx
            )
            prepare_first_lines = (
                "%(result)s = {}".format(initial_code.replace("%", "%%")),
                *reduce_lines,
            )
        else:
            prepare_first_lines = tuple(
                self.get_option("prepare_first_lines", ctx) or ()
            )

        record = ReducerRecord(
            where_code=where_code,
            value_codes=tuple(value_codes),
            not_none_flags=tuple(not_none_flags),
            prepare_first_lines=prepare_first_lines,
            reduce_lines=reduce_lines,
            initial_code=initial_code,
            row_code=code_input,
        )
        new_code_input = reduce_manager.add_reducer_code(record)

        post_conversion = self.get_option("post_conversion", ctx, None)
        default_code = cast(
            BaseConversion, self.default
        ).gen_code_and_update_ctx(reduce_manager.var_row, ctx)
        return If(
            This.is_(EscapedString("_none")),
            EscapedString(default_code),
            (This if post_conversion is None else post_conversion),
        ).gen_code_and_update_ctx(new_code_input, ctx)

    def get_single_agg_reduction(self):
        pass


class OptionalExpressionReducer(BaseReducer):
    def check_expressions(self):
        super().check_expressions()
        if len(self.expressions) > 1:
            warnings.warn(
                "2.0 will raise TypeError if more than 1 expression is "
                f"passed to {self.__class__.__name__}",
                DeprecationWarning,
                stacklevel=1,
            )


class SingleExpressionReducer(BaseReducer):
    def check_expressions(self):
        super().check_expressions()
        expressions_len = len(self.expressions)
        if expressions_len < 1:
            raise ValueError("expected one expression")

        if expressions_len > 1:
            warnings.warn(
                "2.0 will raise TypeError if more than 1 expression is "
                f"passed to {self.__class__.__name__}",
                DeprecationWarning,
                stacklevel=1,
            )


class BaseDictReducer(BaseReducer):
    """Base reducer of two expressions.

    This reducer accepts 2 expressions:

    - the first one is used to calculate keys of the resulting dict
    - the second one is used to calculate values to be reduced and put as the
      final value, under the certain key.

    Effectively dict reducers allow for double grouping: the first one on the
    top level, the second one on DictReducer level.
    """

    def check_expressions(self):
        super().check_expressions()
        expressions_len = len(self.expressions)
        if expressions_len == 2:
            return

        if expressions_len == 1:
            expr = self.expressions[0]
            if (
                isinstance(expr, (Tuple_, List_))
                and expr.conversions is not None
                and len(expr.conversions) == 2
            ):
                self.expressions = tuple(expr.conversions)
                return
        raise ValueError("invalid dict reducer input: two values expected")


class SumReducer(SingleExpressionReducer):
    """Take a sum, None is considered as 0."""

    default = NaiveConversion(0)
    internals_are_public = True
    works_with_not_none_only = (False,)

    def prepare_first_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s = %(value0)s",)
        return ("%(result)s = %(value0)s or 0",)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s += %(value0)s",)
        return ("%(result)s += %(value0)s or 0",)

    def get_single_agg_reduction(self):
        if (
            isinstance(self.default, NaiveConversion)
            and self.default.value == 0
        ):
            return CallFunc(
                sum,
                GeneratorComp(
                    (
                        self.expressions[0]
                        if self.expressions[0].has_hint(
                            BaseConversion.OutputHints.NOT_NONE
                        )
                        else self.expressions[0].or_(0)
                    ),
                    self.where,
                    This,
                ),
            )


class SumOrNoneReducer(SingleExpressionReducer):
    """Take a sum. If at least one None is met, the result is None."""

    default = NaiveConversion(None)
    internals_are_public = True
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s += %(value0)s",)
        return (
            "if %(value0)s is None:",
            "    %(result)s = None",
            "elif %(result)s is not None:",
            "    %(result)s += %(value0)s",
        )


class _ComparisonReducer(SingleExpressionReducer):
    """Base class for reducers that compare values (Max/Min)."""

    comparison_op: str  # "<" for Max, ">" for Min

    default = NaiveConversion(None)
    internals_are_public = True
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = %(value0)s",)

    @property
    def reduce_lines(self):
        return (
            f"if %(result)s {self.comparison_op} %(value0)s:",
            "    %(result)s = %(value0)s",
        )


class MaxReducer(_ComparisonReducer):
    """Find maximum value, skips None."""

    comparison_op = "<"


class MinReducer(_ComparisonReducer):
    """Find minimum value, skips None."""

    comparison_op = ">"


class CountReducer(OptionalExpressionReducer):
    """Counts objects.

    It accepts either zero or one expression as an argument:
      - if zero expressions passed: counts number of rows
      - one expression: counts not None values of the evaluated expression
    """

    default = NaiveConversion(0)
    internals_are_public = True
    prepare_first_lines = ("%(result)s = 1",)
    reduce_lines = ("%(result)s += 1",)

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        if len(self.expressions) == 1 and not self.expressions[0].has_hint(
            BaseConversion.OutputHints.NOT_NONE
        ):
            return (True,)
        return (False,)


class CountDistinctReducer(SingleExpressionReducer):
    default = NaiveConversion(0)
    internals_are_public = False
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = {%(value0)s}",)
    reduce_lines = ("%(result)s.add(%(value0)s)",)
    post_conversion = CallFunc(len, This)


class FirstReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)
    reduce_lines = ()


class LastReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)
    reduce_lines = ("%(result)s = %(value0)s",)


class FirstNReducer(SingleExpressionReducer):
    """Return the first N values."""

    default = NaiveConversion(None)
    internals_are_public = True
    works_with_not_none_only = (False,)

    def __init__(self, n: int, expr, *args, **kwargs):
        if not isinstance(n, int):
            raise TypeError("n must be an integer")
        if n < 1:
            raise ValueError("n must be a positive integer")
        self.n = n
        super().__init__(expr, *args, **kwargs)

    def prepare_first_lines(self, _):
        return ("%(result)s = [%(value0)s]",)

    def reduce_lines(self, _):
        return (
            f"if len(%(result)s) < {self.n}: %(result)s.append(%(value0)s)",
        )


class LastNReducer(SingleExpressionReducer):
    """Return the last N values."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False,)

    def __init__(self, n: int, expr, *args, **kwargs):
        if not isinstance(n, int):
            raise TypeError("n must be an integer")
        if n < 1:
            raise ValueError("n must be a positive integer")
        self.n = n
        super().__init__(expr, *args, **kwargs)

    def prepare_first_lines(self, ctx):
        ctx["__deque__"] = deque
        return (f"%(result)s = __deque__([%(value0)s], maxlen={self.n})",)

    def reduce_lines(self, _):
        return ("%(result)s.append(%(value0)s)",)

    post_conversion = This.as_type(list)


class MaxRowReducer(SingleExpressionReducer):
    """Return a row with a max value of an argument."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = (%(value0)s, %(row)s)",)
    reduce_lines = (
        "if %(result)s[0] < %(value0)s:",
        "    %(result)s = (%(value0)s, %(row)s)",
    )
    post_conversion = GetItem(1)


class MinRowReducer(SingleExpressionReducer):
    """Return a row with a min value of an argument."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = (%(value0)s, %(row)s)",)
    reduce_lines = (
        "if %(result)s[0] > %(value0)s:",
        "    %(result)s = (%(value0)s, %(row)s)",
    )
    post_conversion = GetItem(1)

    def check_expressions(self):
        super().check_expressions()
        if not isinstance(self.initial, _None):
            warnings.warn(
                "2.0 will raise ValueError if initial is "
                f"passed to {self.__class__.__name__}",
                DeprecationWarning,
                stacklevel=1,
            )


class ArrayReducer(SingleExpressionReducer):
    """Collect values into an array."""

    default = NaiveConversion(None)
    internals_are_public = True
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = [%(value0)s]",)
    reduce_lines = ("%(result)s.append(%(value0)s)",)

    def get_single_agg_reduction(self):
        if (
            self.default.contents
            & (
                BaseConversion.ContentTypes.FUNCTION_OF_INPUT
                | BaseConversion.ContentTypes.HIDDEN_INPUT_USAGE
            )
            == 0
        ):
            return ListComp(self.expressions[0], self.where, This).or_(
                self.default
            )


class ListSortedOnceWrapper:
    """Wrap list, which is sorted only once."""

    __slots__ = ["list_", "append", "sorted", "key", "reverse"]

    def __init__(self, list_: list, key=None, reverse=False):
        self.list_ = list_
        self.append = self.list_.append
        self.sorted = False
        self.key = key
        self.reverse = reverse

    def get(self) -> list:
        if not self.sorted:
            self.list_.sort(key=self.key, reverse=self.reverse)
            self.sorted = True
            del self.append
        return self.list_


def _safe_sqrt(x):
    """Square root that works with both float and Decimal."""
    if isinstance(x, Decimal):
        return x.sqrt()
    return x**0.5


def _decimal_safe_mul(value, multiplier):
    """Multiply that works with both float and Decimal values."""
    if isinstance(value, Decimal):
        return value * Decimal(str(multiplier))
    return value * multiplier


class WelfordAccumulator:
    """Online accumulator for mean and variance using Welford's algorithm."""

    __slots__ = ["count", "mean", "m2"]

    def __init__(self, value):
        self.count = 1
        self.mean = value
        self.m2 = 0

    def update(self, value):
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)

    def get_variance(self):  # sample variance, None for n<2
        return self.m2 / (self.count - 1) if self.count > 1 else None

    def get_population_variance(self):
        return self.m2 / self.count if self.count else None


class WelfordCovarianceAccumulator:
    """Online accumulator for covariance/correlation using Welford's algo."""

    __slots__ = ["count", "mean_x", "mean_y", "m2_x", "m2_y", "c"]

    def __init__(self, x, y):
        self.count = 1
        self.mean_x = x
        self.mean_y = y
        self.m2_x = 0
        self.m2_y = 0
        self.c = 0  # co-moment

    def update(self, x, y):
        self.count += 1
        dx = x - self.mean_x
        self.mean_x += dx / self.count
        dx2 = x - self.mean_x

        dy = y - self.mean_y
        self.mean_y += dy / self.count
        dy2 = y - self.mean_y

        self.m2_x += dx * dx2
        self.m2_y += dy * dy2
        self.c += dx * dy2

    def get_covariance(self):  # sample covariance, None for n<2
        return self.c / (self.count - 1) if self.count > 1 else None

    def get_correlation(self):
        if self.count < 2:
            return None
        var_x = self.m2_x / (self.count - 1)
        var_y = self.m2_y / (self.count - 1)
        if var_x == 0 or var_y == 0:
            return None  # undefined when one variable is constant
        if isinstance(var_x, Decimal):
            return self.c / (self.count - 1) / (var_x.sqrt() * var_y.sqrt())
        return self.c / (self.count - 1) / (var_x**0.5 * var_y**0.5)


class ArraySortedReducer(SingleExpressionReducer):
    """Reduce values to a sorted array."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False,)
    reduce_lines = ("%(result)s.append(%(value0)s)",)
    post_conversion: Any = This.call_method("get")

    def __init__(self, *args, key=None, reverse=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.key = self.ensure_conversion(key)
        self.reverse = self.ensure_conversion(reverse)

    def prepare_first_lines(self, ctx):
        key_code = self.key.gen_code_and_update_ctx("%(value0)s", ctx)
        reverse_code = self.reverse.gen_code_and_update_ctx("%(value0)s", ctx)
        return (
            "%(result)s = ListSortedOnceWrapper("
            f"[%(value0)s], {key_code}, {reverse_code})",
        )


class ArrayDistinctReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = { %(value0)s: None }",)
    reduce_lines = ("%(result)s[%(value0)s] = None",)
    post_conversion = This.as_type(list)


class VarianceReducer(SingleExpressionReducer):
    """Sample variance using Welford's algorithm."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = WelfordAccumulator(%(value0)s)",)
    reduce_lines = ("%(result)s.update(%(value0)s)",)
    post_conversion = This.call_method("get_variance")


class PopulationVarianceReducer(SingleExpressionReducer):
    """Population variance using Welford's algorithm."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = WelfordAccumulator(%(value0)s)",)
    reduce_lines = ("%(result)s.update(%(value0)s)",)
    post_conversion = This.call_method("get_population_variance")


def std_dev_reducer(conv, *args, **kwargs) -> BaseConversion:
    """Sample standard deviation."""
    return VarianceReducer(conv, *args, **kwargs).pipe(
        If(This.is_not(None), CallFunc(_safe_sqrt, This), None)
    )


def population_std_dev_reducer(conv, *args, **kwargs) -> BaseConversion:
    """Population standard deviation."""
    return PopulationVarianceReducer(conv, *args, **kwargs).pipe(
        If(This.is_not(None), CallFunc(_safe_sqrt, This), None)
    )


class CovarianceReducer(BaseDictReducer):
    """Sample covariance using Welford's algorithm."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True, True)
    prepare_first_lines = (
        "%(result)s = WelfordCovarianceAccumulator(%(value0)s, %(value1)s)",
    )
    reduce_lines = ("%(result)s.update(%(value0)s, %(value1)s)",)
    post_conversion = This.call_method("get_covariance")


class CorrelationReducer(BaseDictReducer):
    """Pearson correlation using Welford's algorithm."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True, True)
    prepare_first_lines = (
        "%(result)s = WelfordCovarianceAccumulator(%(value0)s, %(value1)s)",
    )
    reduce_lines = ("%(result)s.update(%(value0)s, %(value1)s)",)
    post_conversion = This.call_method("get_correlation")


class DictReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument.
    Values: defined by the second argument, reduced with Last.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)
    reduce_lines = ("%(result)s[%(value0)s] = %(value1)s",)


lock_default_dict_conversion = InlineExpr(
    'setattr({this_}, "default_factory", None) or {this_}'
).pass_args(this_=This)


class DictArrayReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument.
    Values: defined by the second argument, reduced with Array.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = (
        "%(result)s = defaultdict(list)",
        "%(result)s[%(value0)s].append(%(value1)s)",
    )
    reduce_lines = ("%(result)s[%(value0)s].append(%(value1)s)",)
    post_conversion = lock_default_dict_conversion


class DictArrayDistinctReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with ArrayDistinct.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = (
        "%(result)s = defaultdict(dict)",
        "%(result)s[%(value0)s][%(value1)s] = None",
    )
    reduce_lines = ("%(result)s[%(value0)s][%(value1)s] = None",)
    post_conversion = InlineExpr(
        "{{k_: list(v_) for k_, v_ in {}.items()}}"
    ).pass_args(This)


class DictSumReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with Sum
       * None is considered 0
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = (
        "%(result)s = defaultdict(int)",
        "%(result)s[%(value0)s] = %(value1)s or 0",
    )
    post_conversion = lock_default_dict_conversion

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s[%(value0)s] += %(value1)s",)
        return ("%(result)s[%(value0)s] += (%(value1)s or 0)",)


class DictSumOrNoneReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with SumOrNone
       * if at least one None is met, the result is None
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = (
        "%(result)s = defaultdict(int)",
        "%(result)s[%(value0)s] = %(value1)s",
    )
    post_conversion = lock_default_dict_conversion

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s[%(value0)s] += %(value1)s",)
        return (
            "if %(value1)s is None:",
            "    %(result)s[%(value0)s] = None",
            "elif %(result)s[%(value0)s] is not None:",
            "    %(result)s[%(value0)s] += %(value1)s",
        )


class _DictComparisonReducer(BaseDictReducer):
    """Base class for dict reducers that compare values (DictMax/DictMin)."""

    comparison_op: str  # ">" for DictMax, "<" for DictMin

    default = NaiveConversion(None)
    internals_are_public = False
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (False, False)
        return (False, True)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        return (
            f"if %(value0)s not in %(result)s or %(value1)s {self.comparison_op} %(result)s[%(value0)s]:",
            "    %(result)s[%(value0)s] = %(value1)s",
        )


class DictMaxReducer(_DictComparisonReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with Max.
    """

    comparison_op = ">"


class DictMinReducer(_DictComparisonReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with Min.
    """

    comparison_op = "<"


class DictCountReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument (optional), reduced with Count.
       * counts rows if no 2nd arg is passed
       * counts non None values if 2nd arg is passed
    """

    default = NaiveConversion(None)
    internals_are_public = False
    prepare_first_lines = ("%(result)s = { %(value0)s: 1 }",)
    reduce_lines = (
        "if %(value0)s not in %(result)s:",
        "    %(result)s[%(value0)s] = 1",
        "else:",
        "    %(result)s[%(value0)s] += 1",
    )

    def check_expressions(self):
        BaseReducer.check_expressions(self)
        expressions_len = len(self.expressions)
        if expressions_len == 2:
            return

        if expressions_len == 1:
            expr = self.expressions[0]
            if (
                isinstance(expr, (Tuple_, List_))
                and expr.conversions is not None
                and len(expr.conversions) == 2
            ):
                self.expressions = tuple(expr.conversions)
        else:
            raise ValueError("invalid dict reducer input: two values expected")

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        if len(self.expressions) == 2 and not self.expressions[1].has_hint(
            BaseConversion.OutputHints.NOT_NONE
        ):
            return (False, True)
        return (False, False)


class DictCountDistinctReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with CountDistinct.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    prepare_first_lines = ("%(result)s = { %(value0)s: { %(value1)s } }",)
    reduce_lines = (
        "if %(value0)s not in %(result)s:",
        "    %(result)s[%(value0)s] = { %(value1)s }",
        "else:",
        "    %(result)s[%(value0)s].add(%(value1)s)",
    )
    post_conversion = InlineExpr(
        "{{ k_: len(v_) for k_, v_ in {}.items() }}"
    ).pass_args(This)

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (False, False)
        return (False, True)


class DictFirstReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with First.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)
    reduce_lines = (
        "if %(value0)s not in %(result)s:",
        "    %(result)s[%(value0)s] = %(value1)s",
    )


class DictLastReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with Last.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)
    reduce_lines = ("%(result)s[%(value0)s] = %(value1)s",)

    def get_single_agg_reduction(self):
        if (
            self.default.contents
            & (
                BaseConversion.ContentTypes.FUNCTION_OF_INPUT
                | BaseConversion.ContentTypes.HIDDEN_INPUT_USAGE
            )
            == 0
        ):
            return DictComp(
                self.expressions[0], self.expressions[1], self.where, This
            ).or_(self.default)


class DictFirstNReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with FirstN (first N values per key).
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)

    def __init__(self, n: int, key_expr, value_expr, *args, **kwargs):
        if not isinstance(n, int):
            raise TypeError("n must be an integer")
        if n < 1:
            raise ValueError("n must be a positive integer")
        self.n = n
        super().__init__(key_expr, value_expr, *args, **kwargs)

    def prepare_first_lines(self, _):
        return ("%(result)s = { %(value0)s: [%(value1)s] }",)

    def reduce_lines(self, _):
        return (
            "if %(value0)s not in %(result)s:",
            "    %(result)s[%(value0)s] = [%(value1)s]",
            f"elif len(%(result)s[%(value0)s]) < {self.n}:",
            "    %(result)s[%(value0)s].append(%(value1)s)",
        )


class DictLastNReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with LastN (last N values per key).
    """

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (False, False)

    def __init__(self, n: int, key_expr, value_expr, *args, **kwargs):
        if not isinstance(n, int):
            raise TypeError("n must be an integer")
        if n < 1:
            raise ValueError("n must be a positive integer")
        self.n = n
        super().__init__(key_expr, value_expr, *args, **kwargs)

    def prepare_first_lines(self, ctx):
        ctx["__deque__"] = deque
        return (
            f"%(result)s = defaultdict(lambda: __deque__(maxlen={self.n}))",
            "%(result)s[%(value0)s].append(%(value1)s)",
        )

    def reduce_lines(self, _):
        return ("%(result)s[%(value0)s].append(%(value1)s)",)

    post_conversion = InlineExpr(
        "{{k_: list(v_) for k_, v_ in {}.items()}}"
    ).pass_args(This)


class ReducerDispatcher:
    def __call__(self, *args, **kwargs) -> "BaseConversion":
        raise NotImplementedError


class AverageReducerDispatcher(ReducerDispatcher):
    """Calculates weighted average (default weight is 1)."""

    def __call__(
        self, value, weight=1, default=None, where=None
    ) -> "BaseConversion":
        if isinstance(weight, (int, float, Decimal)) and weight:
            return If(
                CountReducer(value, where=where),
                (
                    SumReducer(value, where=where)
                    / CountReducer(value, where=where)
                ),
                default,
            )
        return If(
            SumReducer(weight, where=where),
            (
                SumReducer(Or(value, 0) * Or(weight, 0), where=where)
                / SumReducer(weight, where=where)
            ),
            default,
        )


class TopReducer(DictCountReducer):
    """Return a list of the most frequent values.

    The resulting list is sorted in descending order of value frequency.
    """

    def __init__(self, k: int, key_conv, *args, **kwargs):
        if not isinstance(k, int):
            raise TypeError("K must be an integer.")

        if k < 1:
            raise ValueError("K must be a positive integer greater than 0.")

        self.k = k
        super().__init__(key_conv, key_conv, *args, **kwargs)

    def post_conversion(self, ctx):
        from operator import itemgetter

        ctx["operator_itemgetter"] = itemgetter
        return InlineExpr(
            "[k for k, v in sorted({data}.items(), key=operator_itemgetter(1), reverse=True)[:{k}]]"
        ).pass_args(data=This, k=self.k)


class ModeReducer(DictCountReducer):
    def __init__(self, conv, *args, **kwargs):
        super().__init__(conv, conv, *args, **kwargs)

    def post_conversion(self, ctx):
        from operator import itemgetter

        ctx["operator_itemgetter"] = itemgetter
        return InlineExpr(
            "sorted({data}.items(), key=operator_itemgetter(1), reverse=True)[0][0]"
        ).pass_args(data=This)


class PercentileReducer(ArraySortedReducer):
    """Calculates percentile (float: from 0 to 100 inclusive).

    >>> c.ReduceFuncs.Percentile(95, c.item("amount"))
    >>> c.ReduceFuncs.Percentile(95, c.item("amount"), interpolation="lower")

    interpolation options:
      * "linear"
      * "lower"
      * "higher"
      * "midpoint"
      * "nearest"
    """

    interpolation_to_method: ClassVar[Dict[str, Callable]] = {}
    works_with_not_none_only = (True,)

    def __init__(
        self, percentile: float, conv, *args, interpolation="linear", **kwargs
    ):
        """Init self.

        Args:
          percentile: 0.0-100.0 inclusive
          conv: conversion to apply before reduce phase
          args: unused
          interpolation: one of:
            * "linear"
            * "lower"
            * "higher"
            * "midpoint"
            * "nearest"
          kwargs: can accept `where`=conversion to pre-filter reduced values
        """
        self.percentile = percentile
        try:
            self.method = self.interpolation_to_method[interpolation]
        except KeyError as e:
            raise ValueError("unsupported interpolation type") from e

        super().__init__(conv, *args, **kwargs)
        if not 0 <= percentile <= 100:
            raise ValueError(
                "percentile must be a float between 0 and 100 inclusive"
            )

    @staticmethod
    def _percentile_index(data, percentile):
        return (len(data) - 1) * percentile / 100

    @staticmethod
    def percentile_linear(data, percentile):
        max_index = len(data) - 1
        index = PercentileReducer._percentile_index(data, percentile)
        left_index = int(index)
        left_value = data[left_index]
        if left_index == max_index:
            return left_value

        return left_value + _decimal_safe_mul(
            data[left_index + 1] - left_value, index - left_index
        )

    @staticmethod
    def percentile_lower(data, percentile):
        return data[int(PercentileReducer._percentile_index(data, percentile))]

    @staticmethod
    def percentile_higher(data, percentile):
        return data[
            ceil(PercentileReducer._percentile_index(data, percentile))
        ]

    @staticmethod
    def percentile_midpoint(data, percentile):
        index = PercentileReducer._percentile_index(data, percentile)
        left_index = int(index)
        if left_index == index:
            return data[left_index]

        left_value = data[left_index]
        return left_value + _decimal_safe_mul(
            data[left_index + 1] - left_value, 0.5
        )

    @staticmethod
    def percentile_nearest(data, percentile):
        index = PercentileReducer._percentile_index(data, percentile)
        left_index = int(index)
        if index - left_index > 0.5:
            return data[left_index + 1]
        else:
            return data[left_index]

    def post_conversion(self, ctx):  # pylint: disable=unused-argument
        return CallFunc(
            self.method,
            This.call_method("get"),
            self.percentile,
        )


PercentileReducer.interpolation_to_method = {
    "linear": PercentileReducer.percentile_linear,
    "lower": PercentileReducer.percentile_lower,
    "higher": PercentileReducer.percentile_higher,
    "midpoint": PercentileReducer.percentile_midpoint,
    "nearest": PercentileReducer.percentile_nearest,
}


def MedianReducer(  # pylint:disable=invalid-name
    conv, *args, **kwargs
) -> BaseConversion:
    return PercentileReducer(50, conv, *args, **kwargs)


class ReduceFuncs:
    """Expose the list of reduce functions."""

    # pylint: disable=invalid-name

    #: Sums values, treating `None` (and other falsy values) as `0`; default is `0`.
    Sum = SumReducer
    #: Sums values; any `None` makes the result `None`.
    SumOrNone = SumOrNoneReducer

    #: Returns the max value, skipping `None`.
    Max = MaxReducer
    #: Returns the row with the max value, skipping `None` comparison values.
    MaxRow = MaxRowReducer

    #: Returns the min value, skipping `None`.
    Min = MinReducer
    #: Returns the row with the min value, skipping `None` comparison values.
    MinRow = MinRowReducer

    #: `Count()` counts rows; `Count(value)` counts non-`None` values.
    Count = CountReducer
    #: Counts distinct non-`None` values.
    CountDistinct = CountDistinctReducer

    #: Returns the first encountered value.
    First = FirstReducer
    #: Returns the last encountered value.
    Last = LastReducer
    #: `FirstN(n, value)`: collects the first `n` encountered values as a list.
    FirstN = FirstNReducer
    #: `LastN(n, value)`: collects the last `n` encountered values as a list.
    LastN = LastNReducer

    #: `Average(value)` or `Average(value, weight)`: arithmetic or weighted
    #: mean; `None` handling differs between the two forms.
    Average = AverageReducerDispatcher()
    #: Calculates the median value, skipping `None`.
    Median = MedianReducer
    #: Calculates sample variance, skipping `None`.
    Variance = VarianceReducer
    #: Calculates sample standard deviation, skipping `None`.
    StdDev = std_dev_reducer
    #: Calculates population variance, skipping `None`.
    PopulationVariance = PopulationVarianceReducer
    #: Calculates population standard deviation, skipping `None`.
    PopulationStdDev = population_std_dev_reducer
    #: Calculates sample covariance between two variables, skipping `None`.
    Covariance = CovarianceReducer
    #: Calculates Pearson correlation between two variables, skipping `None`.
    Correlation = CorrelationReducer
    #: `Percentile(percentile, value, interpolation="linear")`: calculates a
    #: percentile (`percentile` in `[0, 100]`), skipping `None`.
    Percentile = PercentileReducer
    #: Returns the most common non-`None` value; on ties, the first encountered
    #: value wins.
    Mode = ModeReducer
    #: `TopK(k, value)`: returns a list of the `k` most frequent non-`None`
    #: values, sorted by descending frequency.
    TopK = TopReducer

    #: Collects values as a list.
    Array = ArrayReducer
    #: Collects distinct values as a list, preserving order.
    ArrayDistinct = ArrayDistinctReducer
    #: Collects values as a sorted list; optional `key=` / `reverse=` like
    #: `sorted`.
    ArraySorted = ArraySortedReducer

    #: Builds a dict whose values are the last value per key.
    Dict = DictReducer
    #: Builds a dict whose values are lists of values per key.
    DictArray = DictArrayReducer
    #: Builds a dict whose values are distinct lists per key, preserving order.
    DictArrayDistinct = DictArrayDistinctReducer
    #: Builds a dict whose values are sums per key, treating `None` as `0`.
    DictSum = DictSumReducer
    #: Builds a dict whose values are sums per key; any `None` makes that
    #: key's result `None`.
    DictSumOrNone = DictSumOrNoneReducer
    #: Builds a dict whose values are max values per key, skipping `None`.
    DictMax = DictMaxReducer
    #: Builds a dict whose values are min values per key, skipping `None`.
    DictMin = DictMinReducer
    #: `DictCount(key)` counts rows per key; `DictCount(key, value)` counts
    #: non-`None` values per key.
    DictCount = DictCountReducer
    #: Builds a dict whose values are counts of distinct non-`None` values
    #: per key.
    DictCountDistinct = DictCountDistinctReducer
    #: Builds a dict whose values are first encountered values per key.
    DictFirst = DictFirstReducer
    #: Builds a dict whose values are last encountered values per key.
    DictLast = DictLastReducer
    #: `DictFirstN(n, key, value)`: builds a dict whose values are the first
    #: `n` encountered values per key.
    DictFirstN = DictFirstNReducer
    #: `DictLastN(n, key, value)`: builds a dict whose values are the last
    #: `n` encountered values per key.
    DictLastN = DictLastNReducer


class GroupBy:
    """Generates the function which implements aggregation.

    Grouping is done by conversions passed to `__init__` method.
     - if there are any, the result is a list of reduced values.
     - if there is no keys to group by, the result is a single reduced value.

    Reduced value/values is/are defined by the parameter passed to
    ``aggregate`` method.

    Current optimizations:
     * piping like ``c.group_by(...).aggregate().pipe(...)`` won't run
       the aggregation twice
     * using the same reducer twicewon't result in double calculation
    """

    def __init__(self, *by):
        """Accept keys of group by as conversions.

        Args:
          by (tuple): keys of group by as conversions. Each is to resolve to a
            hashable object. If nothing is passed, the result is a single
            object.
        """
        self.by = by

    def aggregate(
        self, reducer: Union[dict, list, set, tuple, BaseConversion]
    ) -> "Grouper":
        if (
            not self.by
            and isinstance(reducer, BaseReducer)
            and isinstance(reducer.initial, _None)
        ):
            conv = reducer.get_single_agg_reduction()
            if conv is not None:
                return conv
        return Grouper(self.by, reducer)


def delegate_input_switching_method(name, force_iter_first=False):
    def method(self, *args, **kwargs):
        conversion = self.conversion
        if force_iter_first:
            conversion = conversion.to_iter()
        return Grouper(
            by=self.by,
            reducer=self.reducer,
            conversion=getattr(conversion, name)(*args, **kwargs),
        )

    return method


GROUPER_TEMPLATE = """
def {converter_name}({code_args}):
    {var_signature_to_agg_data} = defaultdict({var_agg_data_cls})

{code_group_by}

{code_result}
"""
AGGREGATE_TEMPLATE = """
def {converter_name}({code_args}):
    {code_init_agg_vars}

{code_aggregate}

{code_result}
"""


class Grouper(BaseConversion):
    """Fully initialized GroupBy conversion.

    Which delegates some of methods like iter to its internals.
    """

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.AGGREGATION
        | BaseConversion.ContentTypes.NONE_USAGE
    )

    SIGNATURE_NAME = "signature"
    AGG_DATA_NAME = "agg_data"
    AGG_RESULT_ITEM_NAME = "agg_result_item"
    SIGNATURE = Namespace(
        LazyEscapedString(SIGNATURE_NAME), {SIGNATURE_NAME: None}
    )
    AGG_DATA = Namespace(
        LazyEscapedString(AGG_DATA_NAME), {AGG_DATA_NAME: None}
    )
    AGG_RESULT_ITEM = Namespace(
        LazyEscapedString(AGG_RESULT_ITEM_NAME), {AGG_RESULT_ITEM_NAME: None}
    )
    AGG_RESULT_ITEM.weight = Weights.UNPREDICTABLE

    def __init__(self, by, reducer, conversion=None):
        super().__init__()
        self.by = [self.ensure_conversion(by_) for by_ in by]
        self.reducer = self.ensure_conversion(reducer)
        self.contents = self.contents & ~self.ContentTypes.REDUCER
        self.number_of_input_uses = 1
        self.aggregate_mode = len(self.by) == 0

        if conversion:
            self.conversion = self.ensure_conversion(conversion)
        else:
            self.conversion = self.ensure_conversion(
                ListComp(
                    GeneratorItem(
                        self.AGG_RESULT_ITEM,
                        self.SIGNATURE,
                        self.AGG_DATA,
                    ),
                    _none,
                    _none,
                )
                if len(self.by)
                else self.AGG_RESULT_ITEM
            )

    to_iter = delegate_input_switching_method("to_iter")
    iter = delegate_input_switching_method("iter", True)
    iter_mut = delegate_input_switching_method("iter_mut", True)
    iter_windows = delegate_input_switching_method("iter_windows", True)
    filter = delegate_input_switching_method("filter")
    flatten = delegate_input_switching_method("flatten", True)
    take_while = delegate_input_switching_method("take_while", True)
    drop_while = delegate_input_switching_method("drop_while", True)
    as_type = delegate_input_switching_method("as_type", True)
    sort = delegate_input_switching_method("sort", True)
    tap = delegate_input_switching_method("tap", True)

    def gen_code_and_update_ctx(self, code_input, ctx) -> str:
        ctx["defaultdict"] = defaultdict
        ctx["ListSortedOnceWrapper"] = ListSortedOnceWrapper
        ctx["WelfordAccumulator"] = WelfordAccumulator
        ctx["WelfordCovarianceAccumulator"] = WelfordCovarianceAccumulator

        suffix = self.gen_random_suffix(
            ctx, "aggregate", "group_by", "AggData"
        )
        var_row = f"row{suffix}"
        var_signature = f"signature{suffix}"
        var_signature_to_agg_data = f"signature_to_agg_data{suffix}"
        var_agg_data = f"agg_data{suffix}"
        var_agg_data_cls = f"AggData{suffix}"

        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This())

        reduce_manager = ReduceManager(
            var_row, var_agg_data, self.aggregate_mode
        )
        with function_ctx:
            if "current_reduce_manager" not in ctx:
                ctx["current_reduce_manager"] = [reduce_manager]
            else:
                ctx["current_reduce_manager"].append(reduce_manager)

            try:
                code_agg_result = self.reducer.gen_code_and_update_ctx(
                    var_row, ctx
                )
            finally:
                ctx["current_reduce_manager"].pop()
                if not ctx["current_reduce_manager"]:
                    del ctx["current_reduce_manager"]

            by_is_single = len(self.by) == 1
            code_signatures = []
            for index, by_ in enumerate(self.by):
                code_by = by_.gen_code_and_update_ctx(var_row, ctx)
                code_signatures.append(code_by)
                code_agg_result = self.replace_word(
                    code_agg_result,
                    code_by,
                    (
                        var_signature
                        if by_is_single
                        else f"{var_signature}[{index}]"
                    ),
                )

            code_signature = (
                code_signatures[0]
                if by_is_single
                else f"({', '.join(code_signatures)})"
            )

            if var_row in code_agg_result:
                raise ConversionException(
                    "something other than group_by keys and reducers have been used",
                    code_agg_result,
                )

            with NamespaceCtx(
                {
                    self.SIGNATURE_NAME: var_signature,
                    self.AGG_DATA_NAME: var_agg_data,
                    self.AGG_RESULT_ITEM_NAME: code_agg_result,
                },
                ctx,
            ):
                code_final_result = (
                    self.conversion.gen_code_and_update_ctx(None, ctx)
                    if self.aggregate_mode
                    else self.conversion.gen_code_and_update_ctx(
                        f"{var_signature_to_agg_data}.items()", ctx
                    )
                )
            agg_template_kwargs = {
                "code_args": function_ctx.get_def_all_args_code(),
                "code_result": f"    return {code_final_result}",
                "var_row": var_row,
            }

            if self.aggregate_mode:
                converter_name = f"aggregate{suffix}"
                grouper_code = AGGREGATE_TEMPLATE.format(
                    converter_name=converter_name,
                    code_init_agg_vars=reduce_manager.gen_init_aggregate_vars(),
                    code_aggregate=reduce_manager.gen_aggregate_code().to_string(
                        base_indent_level=1,
                    ),
                    **agg_template_kwargs,
                )
            else:
                converter_name = f"group_by{suffix}"
                ctx[var_agg_data_cls] = (
                    reduce_manager.gen_group_by_data_container(
                        self, var_agg_data_cls, ctx
                    )
                )
                grouper_code = GROUPER_TEMPLATE.format(
                    converter_name=converter_name,
                    var_signature_to_agg_data=var_signature_to_agg_data,
                    var_agg_data_cls=var_agg_data_cls,
                    var_agg_data=var_agg_data,
                    code_signature=code_signature,
                    code_group_by=reduce_manager.gen_group_by_code(
                        var_signature_to_agg_data=var_signature_to_agg_data,
                        code_signature=code_signature,
                    ).to_string(base_indent_level=1),
                    **agg_template_kwargs,
                )

            conversion = function_ctx.gen_conversion(
                converter_name, grouper_code
            )
        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


def Aggregate(  # pylint:disable=invalid-name
    *args, **kwargs
) -> BaseConversion:
    """Shortcut for `GroupBy().aggregate(*args, **kwargs)`."""
    return GroupBy().aggregate(*args, **kwargs)


class Reduce(BaseReducer):
    """Reduce operation, which is based on a callable / expression."""

    internals_are_public = True

    def __init__(
        self,
        to_call_with_2_args: Union[Callable, InlineExpr],
        *expressions: Tuple[Any, ...],
        initial: Union[_None, Callable, InlineExpr, Any],
        default: Union[_None, Callable, Any] = _none,
        unconditional_init: bool = False,
        where=None,
    ):
        """Init self.

        Args:
          to_call_with_2_args: defines the reduce function/expression
          expressions: args to be passed to `to_call_with_2_args` after the
            aggregation value
          initial: defines the very first item to be passed to
            `to_call_with_2_args` item. If callable, then the result of a call
            is used. If a conversion is passed, it is resolved on the first
            row met.
          default: defines the value to be returned when there was nothing to
            reduce in a group (e.g. the current reduce operation has filtered
            out some rows, while an adjacent reduce operation has got
            something to reduce, forming a group). If callable, then the result
            of a call is used.  When default is not passed, initial is used if
            it doesn't depend on input data.
          unconditional_init: tells whether the first call initializes the
            aggregation value OR there is a condition for that
          where: condition conversion to pre-filter values to be reduced.
        """
        super().__init__(
            *expressions, initial=initial, default=default, where=where
        )

        self.to_call_with_2_args = self.ensure_conversion(to_call_with_2_args)
        if unconditional_init:
            warnings.warn(
                "unconditional_init is no longer needed",
                DeprecationWarning,
                stacklevel=1,
            )

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        return (False,) * len(self.expressions)

    def reduce_lines(self, ctx):
        # Generate against %-free sentinels so expression code containing
        # literal % (e.g. c.this % 3, InlineExpr with %) can be escaped
        # without corrupting intentional %(result)s / %(row)s placeholders.
        result_sentinel = "__reduce_result_sentinel__"
        row_sentinel = "__reduce_row_sentinel__"
        value_sentinels = tuple(
            "__reduce_value_{}_sentinel__".format(i)
            for i in range(len(self.expressions))
        )
        value_args = tuple(
            EscapedString(sentinel) for sentinel in value_sentinels
        )
        to_call = self.to_call_with_2_args
        if isinstance(to_call, InlineExpr):
            conv = to_call.pass_args(
                EscapedString(result_sentinel), *value_args
            )
        elif isinstance(to_call, NaiveConversion) and callable(to_call.value):
            conv = to_call.call(EscapedString(result_sentinel), *value_args)
        else:
            raise AssertionError("unexpected callable", to_call)
        code = conv.gen_code_and_update_ctx(row_sentinel, ctx)
        code = (
            code.replace("%", "%%")
            .replace(result_sentinel, "%(result)s")
            .replace(row_sentinel, "%(row)s")
        )
        for i, sentinel in enumerate(value_sentinels):
            code = code.replace(sentinel, "%(value{})s".format(i))
        return (f"%(result)s = {code}",)
