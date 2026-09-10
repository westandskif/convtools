"""Share repeated eager expressions in generated aggregate/group_by code.

Safety: an expression is evaluated only on rows where some naive
per-reducer use would have evaluated it, never above its guards, and
initial expressions are never shared. Reducer where/value expressions
are treated as deterministic and free of side effects on the row;
shared values are the same object in every reducer; reducer callables
must not mutate the values they receive.
"""

import ast
import copy
from functools import lru_cache

from ._utils import ast_unparse

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


def _is_binder(node):
    return isinstance(node, _BINDER_TYPES)


def _is_hoistable(node):
    return isinstance(node, _HOISTABLE_TYPES)


def _structural_keys(root, intern):
    """Map id(node) -> (key, size) for every node under root.

    ``key`` is a small int interned via ``intern`` so that two subtrees get
    the same key if their ``ast.dump`` would be equal; computed bottom-up in
    one pass instead of dumping every subtree separately.
    """
    keys = {}

    def visit(node):
        parts = []
        size = 1
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                sub_key, sub_size = visit(value)
                size += sub_size
                parts.append((field, sub_key))
            elif isinstance(value, list):
                sub_keys = []
                for elem in value:
                    if isinstance(elem, ast.AST):
                        sub_key, sub_size = visit(elem)
                        size += sub_size
                        sub_keys.append(sub_key)
                    else:
                        sub_keys.append(repr(elem))
                parts.append((field, tuple(sub_keys)))
            else:
                parts.append((field, repr(value)))
        raw = (type(node), tuple(parts))
        key = intern.get(raw)
        if key is None:
            key = len(intern)
            intern[raw] = key
        entry = (key, size)
        keys[id(node)] = entry
        return entry

    visit(root)
    return keys


def _opaque_eager_parts(node):
    if isinstance(node, ast.Lambda):
        args = node.args
        for default in args.defaults:
            yield default
        for kw_default in args.kw_defaults:
            if kw_default is not None:
                yield kw_default
        return
    if isinstance(
        node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    ):
        yield node.generators[0].iter


def _walk_expr_children_skip_binders(node, eager_only):
    if _is_binder(node):
        for part in _opaque_eager_parts(node):
            yield part
        return
    if eager_only:
        if isinstance(node, ast.BoolOp):
            yield node.values[0]
            return
        if isinstance(node, ast.IfExp):
            yield node.test
            return
        if isinstance(node, ast.Compare):
            yield node.left
            yield node.comparators[0]
            return
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            yield child
        else:
            yield from ast.iter_child_nodes(child)


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


def _fmt_expr(node, original=None, rewritten=False):
    if not rewritten and original is not None:
        return original
    code = ast_unparse(node).strip()
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
        return code
    return "({})".format(code)


class _ReplaceDumps(ast.NodeTransformer):
    def __init__(self, key_to_name, keys):
        self.key_to_name = key_to_name
        self.keys = keys
        self.changed = False

    def visit(self, node):
        if isinstance(node, ast.expr):
            name = self.key_to_name.get(self.keys[id(node)][0])
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
        new_defaults = [self.visit(d) for d in args.defaults]
        new_kw = [
            self.visit(d) if d is not None else d for d in args.kw_defaults
        ]
        if new_defaults == list(args.defaults) and new_kw == list(
            args.kw_defaults
        ):
            return args
        kwargs = {field: getattr(args, field) for field in args._fields}
        kwargs["defaults"] = new_defaults
        kwargs["kw_defaults"] = new_kw
        return ast.arguments(**kwargs)


def _replace_dumps(node, key_to_name, keys):
    transformer = _ReplaceDumps(key_to_name, keys)
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
    bodies.append(orelse)
    return bodies


def _add_counts(left, right):
    return [a + b for a, b in zip(left, right)]


def _max_counts(left, right):
    return [max(a, b) for a, b in zip(left, right)]


def _count_sentinels(node, sentinel_to_index, n_values):
    counts = [0] * n_values
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
    if isinstance(stmt, ast.Expr):
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
    total = [0] * n_values
    for expr in _stmt_evaled_exprs(stmt):
        total = _add_counts(
            total, _count_sentinels(expr, sentinel_to_index, n_values)
        )
    return total


def _mark_eager_block(stmts, sentinel_to_index, eager):
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            _mark_eager_expr(stmt.test, sentinel_to_index, eager)
            if _if_has_complete_else(stmt):
                n = len(eager)
                branch_flags = []
                for body in _if_branch_bodies(stmt):
                    flags = [False] * n
                    _mark_eager_block(body, sentinel_to_index, flags)
                    branch_flags.append(flags)
                for i in range(n):
                    if all(flags[i] for flags in branch_flags):
                        eager[i] = True
            continue
        for expr in _stmt_evaled_exprs(stmt):
            _mark_eager_expr(expr, sentinel_to_index, eager)


def _analyze_template_block(lines, n_values, include_row=False):
    n = n_values + 1 if include_row else n_values
    eager = [False] * n
    weights = [0] * n
    if not lines:
        if include_row:
            return eager[:n_values], weights[:n_values], False, 0
        return eager, weights
    sentinels = ["_red_val_{}_".format(i) for i in range(n_values)]
    sentinel_to_index = {name: i for i, name in enumerate(sentinels)}
    if include_row:
        sentinel_to_index["_red_row_"] = n_values
    kwargs = {"result": "_red_result_", "row": "_red_row_"}
    for i, name in enumerate(sentinels):
        kwargs["value{}".format(i)] = name
    rendered = "\n".join(line % kwargs for line in lines)
    tree = ast.parse(rendered)
    _mark_eager_block(tree.body, sentinel_to_index, eager)
    weights = _weight_block(tree.body, sentinel_to_index, n)
    if include_row:
        return (
            eager[:n_values],
            weights[:n_values],
            eager[n_values],
            weights[n_values],
        )
    return eager, weights


@lru_cache(maxsize=1024)
def _template_info(prepare_lines, reduce_lines, n_values):
    # Templates embed per-compile naive names and user constants, so the
    # key space is unbounded; bound the cache instead of using a plain dict.
    init_eager, init_weight, init_row_eager, _ = _analyze_template_block(
        prepare_lines, n_values, include_row=True
    )
    reduce_eager, reduce_weight, reduce_row_eager, _ = _analyze_template_block(
        reduce_lines, n_values, include_row=True
    )
    return (
        init_eager,
        init_weight,
        reduce_eager,
        reduce_weight,
        init_row_eager,
        reduce_row_eager,
    )


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
        if tree is not None:
            self.tree = tree
        else:
            self.tree = ast.parse(code, mode="eval").body


class ReducerRecord(object):
    __slots__ = [
        "slot",
        "where_code",
        "value_codes",
        "not_none_flags",
        "prepare_first_lines",
        "reduce_lines",
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
        row_code,
    ):
        self.slot = None
        self.where_code = where_code
        self.value_codes = value_codes
        self.not_none_flags = not_none_flags
        self.prepare_first_lines = prepare_first_lines
        self.reduce_lines = reduce_lines
        self.row_code = row_code
        self.guard_chain = None

    def dedup_key(self):
        # row_code is part of identity because MaxRow/MinRow capture the piped
        # input; it now also participates in sharing.
        return (
            self.where_code,
            self.value_codes,
            self.not_none_flags,
            self.prepare_first_lines,
            self.reduce_lines,
            self.row_code,
        )


class GuardScope(object):
    __slots__ = ["reducers", "children"]

    def __init__(self):
        self.reducers = []
        self.children = {}


class SharingPlan(object):
    __slots__ = ["values", "guards", "signature", "temps", "rows"]

    def __init__(self):
        self.values = {}
        self.guards = {}
        self.signature = None
        self.temps = {}
        self.rows = {}


def build_guard_tree(records):
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
    (
        init_eager,
        init_weight,
        reduce_eager,
        reduce_weight,
        init_row_eager,
        reduce_row_eager,
    ) = _template_info(
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
        row_eager = bool(
            init_row_eager and (False if reduce_is_empty else reduce_row_eager)
        )
        return eager, weights, row_eager
    return list(reduce_eager), list(reduce_weight), reduce_row_eager


def _collect_count_items(scope, plan, with_init, self_scope, signature, items):
    for record in scope.reducers:
        eager_flags, weights, row_eager = _eager_and_weight(record, with_init)
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
        templates = record.prepare_first_lines + record.reduce_lines
        if any("%(row)s" in line for line in templates):
            items.append(
                _CountItem(
                    plan.rows[id(record)],
                    1,
                    scope is self_scope and row_eager,
                    "row",
                    record=record,
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
        found = []
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
        for name in ready:
            remaining.remove(name)
            ordered.append(name)
    by_name = dict(temp_entries)
    return [(name, by_name[name]) for name in ordered]


def analyze_scope(scope, plan, with_init, signature, tmp_index):
    items = []
    _collect_count_items(scope, plan, with_init, scope, signature, items)
    local_temps = []
    local_i = 0
    intern = {}
    item_keys = {}  # id(item) -> structural keys; dropped when rewritten
    item_contribs = {}
    candidates = {}

    def _add_item_contributions(item):
        keys = _structural_keys(item.tree, intern)
        item_keys[id(item)] = keys
        eager_keys = set()
        if item.is_self_eager_root:
            for node in _iter_eager(item.tree):
                if _is_hoistable(node):
                    eager_keys.add(keys[id(node)][0])
        contribs = []
        for node in _iter_hoistable(item.tree):
            key, size = keys[id(node)]
            eager_flag = key in eager_keys
            contribs.append((key, item.weight, eager_flag, node))
            rec = candidates.get(key)
            if rec is None:
                rec = {
                    "size": size,
                    "count": 0,
                    "live": 0,
                    "eager_ok": 0,
                    "contributors": {},
                }
                candidates[key] = rec
            rec["count"] += item.weight
            rec["live"] += 1
            if eager_flag:
                rec["eager_ok"] += 1
            rec["contributors"][id(item)] = node
        item_contribs[id(item)] = contribs

    def _subtract_item_contributions(item):
        item_id = id(item)
        contribs = item_contribs.pop(item_id)
        del item_keys[item_id]
        for key, weight, eager_flag, _node in contribs:
            rec = candidates[key]
            rec["count"] -= weight
            rec["live"] -= 1
            if eager_flag:
                rec["eager_ok"] -= 1
            rec["contributors"].pop(item_id, None)
            if rec["live"] == 0:
                del candidates[key]

    for item in items:
        _add_item_contributions(item)
    while True:
        best = None
        best_key = None
        for key, rec in candidates.items():
            if rec["count"] < 2 or rec["eager_ok"] <= 0:
                continue
            order = (rec["count"], rec["size"], key)
            if best is None or order > best:
                best = order
                best_key = key
        if best_key is None:
            break
        rec = candidates[best_key]
        internal_name = "__cse{}_".format(local_i)
        local_i += 1
        rhs_tree = copy.deepcopy(next(iter(rec["contributors"].values())))
        mapping = {best_key: internal_name}
        contributor_ids = rec["contributors"]
        rewritten_items = []
        for item in items:
            if id(item) not in contributor_ids:
                continue
            new_tree, changed = _replace_dumps(
                item.tree, mapping, item_keys[id(item)]
            )
            if changed:
                item.tree = new_tree
                item.rewritten = True
                rewritten_items.append(item)
        for item in rewritten_items:
            _subtract_item_contributions(item)
        for item in rewritten_items:
            _add_item_contributions(item)
        items.append(
            _CountItem(
                None,
                1,
                True,
                "temp_rhs",
                tree=rhs_tree,
                rewritten=True,
            )
        )
        _add_item_contributions(items[-1])
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
            item.tree = _rename_names(item.tree, old_to_new)
        emitted = [
            (name, _rename_names(tree, old_to_new)) for name, tree in emitted
        ]

    plan.temps[id(scope)] = [
        (name, _fmt_expr(tree, rewritten=True)) for name, tree in emitted
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
        elif item.kind == "row":
            plan.rows[id(item.record)] = new_code
        else:
            plan.signature = new_code

    for child in scope.children.values():
        tmp_index = analyze_scope(child, plan, with_init, None, tmp_index)
    return tmp_index


def init_plan(records, signature):
    plan = SharingPlan()
    for record in records:
        plan.values[id(record)] = record.value_codes
        plan.rows[id(record)] = record.row_code
    plan.signature = signature
    return plan


def count_reducer_nodes(node):
    total = 1 if node.reducers else 0
    for child in node.children.values():
        total += count_reducer_nodes(child)
    return total
