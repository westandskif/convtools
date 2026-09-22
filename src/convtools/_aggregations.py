"""Define aggregations with various reduce functions."""

import ast
from collections import defaultdict
from typing import Union

from ._base import (
    BaseConversion,
    ConversionException,
    ConverterOptionsCtx,
    GeneratorItem,
    LazyEscapedString,
    ListComp,
    Namespace,
    NamespaceCtx,
    This,
    _None,
    _none,
)
from ._heuristics import Weights
from ._reducer_sharing import (
    _fmt_expr,
    _structural_keys,
    analyze_scope,
    build_guard_tree,
    count_reducer_nodes,
    init_plan,
)
from ._reducers import (
    BaseReducer,
    ListSortedOnceWrapper,
    WelfordAccumulator,
    WelfordCovarianceAccumulator,
)
from ._utils import PY_VERSION, Code, ast_unparse


def _analyze_or_unshared(
    root, records, with_init, signature, signature_tree=None
):
    """Share eager expressions; fall back to the unshared plan on overflow."""
    plan = init_plan(records, signature, signature_tree)
    try:
        analyze_scope(root, plan, with_init, signature is not None, 0)
    except RecursionError:
        # the first attempt may have rewritten signature_tree in place
        return init_plan(records, signature)
    return plan


_DISPLAY_ATOMS = (
    ast.Dict,
    ast.List,
    ast.Set,
    ast.DictComp,
    ast.ListComp,
    ast.SetComp,
)


_STRING_TEMPLATES = tuple(
    getattr(ast, name)
    for name in ("JoinedStr", "TemplateStr")
    if hasattr(ast, name)
)
_INTERPOLATIONS = tuple(
    getattr(ast, name)
    for name in ("FormattedValue", "Interpolation")
    if hasattr(ast, name)
)


class _ReplaceKeys(ast.NodeTransformer):
    """Replace subtrees equal to a group_by key with the signature ref.

    Scope-aware: inside a lambda / comprehension, a key whose free names
    the binder rebinds is not that key. ``free_names`` collects names read
    outside any binder that rebinds them; with no keys given, the visitor
    only collects them.
    """

    def __init__(
        self, keys=None, key_to_index=None, key_names=(), var_signature=None
    ):
        self.keys = keys
        self.key_to_index = key_to_index
        self.key_names = key_names
        self.var_signature = var_signature
        self.shadowed = frozenset()
        self.free_names = set()
        self.changed = False

    def visit(self, node):
        if isinstance(node, ast.expr):
            index = (
                self.key_to_index.get(self.keys[id(node)][0])
                if self.key_to_index
                else None
            )
            if index is not None and not (
                self.key_names[index] & self.shadowed
            ):
                self.changed = True
                signature = ast.Name(id=self.var_signature, ctx=ast.Load())
                if len(self.key_names) == 1:
                    return signature
                slice_: ast.AST = ast.Constant(value=index, kind=None)
                if PY_VERSION < (3, 9):
                    slice_ = ast.Index(value=slice_)  # pragma: no cover
                return ast.Subscript(
                    value=signature, slice=slice_, ctx=ast.Load()
                )
            if isinstance(node, _STRING_TEMPLATES):
                return self._visit_string_template(node)
            if isinstance(node, ast.Lambda):
                return self._visit_lambda(node)
            if isinstance(
                node,
                (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
            ):
                return self._visit_comprehension(node)
            if isinstance(node, ast.Name) and node.id not in self.shadowed:
                self.free_names.add(node.id)
        return self.generic_visit(node)

    def _visit_string_template(self, node):
        # literal segments are not expressions; only interpolated values are
        for part in node.values:
            if isinstance(part, _INTERPOLATIONS):
                changed, self.changed = self.changed, False
                part.value = self.visit(part.value)
                if self.changed and hasattr(part, "str"):
                    # 3.14 unparses an Interpolation from its source text
                    part.str = ast_unparse(part.value)
                self.changed = self.changed or changed
                if part.format_spec is not None:
                    self._visit_string_template(part.format_spec)
        return node

    def _visit_lambda(self, node):
        args = node.args
        args.defaults = [self.visit(d) for d in args.defaults]
        args.kw_defaults = [
            d if d is None else self.visit(d) for d in args.kw_defaults
        ]
        bound = [
            arg.arg
            for arg in getattr(args, "posonlyargs", [])
            + args.args
            + args.kwonlyargs
        ]
        bound.extend(arg.arg for arg in (args.vararg, args.kwarg) if arg)
        outer = self.shadowed
        self.shadowed = outer.union(bound)
        node.body = self.visit(node.body)
        self.shadowed = outer
        return node

    def _visit_comprehension(self, node):
        generators = node.generators
        # only the first iter is evaluated in the enclosing scope
        generators[0].iter = self.visit(generators[0].iter)
        outer = self.shadowed
        self.shadowed = outer.union(
            name.id
            for gen in generators
            for name in ast.walk(gen.target)
            if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store)
        )
        for i, gen in enumerate(generators):
            gen.target = self.visit(gen.target)
            if i:
                gen.iter = self.visit(gen.iter)
            gen.ifs = [self.visit(if_) for if_ in gen.ifs]
        if isinstance(node, ast.DictComp):
            node.key = self.visit(node.key)
            node.value = self.visit(node.value)
        else:
            node.elt = self.visit(node.elt)
        self.shadowed = outer
        return node


def _free_names(tree):
    collector = _ReplaceKeys()
    collector.visit(tree)
    return frozenset(collector.free_names)


class ReduceManager:
    """Build group by / aggregate code."""

    __slots__ = [
        "var_row",
        "var_agg_data",
        "aggregate_mode",
        "records",
        "dedup",
        "label_writes",
        "label_external_reads",
        "reducer_label_writes",
        "reducer_label_reads",
        "accepts_reducers",
    ]

    def __init__(self, var_row, var_agg_data, aggregate_mode):
        self.var_row = var_row
        self.var_agg_data = var_agg_data
        self.aggregate_mode = aggregate_mode
        self.records = []
        self.dedup = {}
        self.label_writes = set()
        self.label_external_reads = set()
        self.reducer_label_writes = None
        self.reducer_label_reads = None
        self.accepts_reducers = False

    def note_label_read(self, name):
        if self.reducer_label_reads is not None:
            self.reducer_label_reads.add(name)

    def note_label_write(self, name):
        if self.reducer_label_writes is not None:
            self.reducer_label_writes.add(name)

    def gen_agg_data_value(self):
        return self.fmt_agg_data_value(len(self.records))

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
                chain.append("({}) is not None".format(code))
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
        kwargs = {
            "result": record.slot,
            "row": plan.rows[id(record)].code,
        }
        for i, item in enumerate(plan.values[id(record)]):
            kwargs["value{}".format(i)] = item.code
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
            item = plan.guards.get(id(child))
            code.add_line(
                "if {}:".format(guard if item is None else item.code), 1
            )
            self._emit_scope(code, child, plan, with_init)
            code.incr_indent_level(-1)

    def gen_group_by_code(
        self, var_signature_to_agg_data, code_signature, signature_tree
    ):
        root = build_guard_tree(self.records)
        plan = _analyze_or_unshared(
            root, self.records, True, code_signature, signature_tree
        )
        code = Code()
        code.add_line("for {} in data_:".format(self.var_row), 1)

        def _assign_agg_data():
            code.add_line(
                "{} = {}[{}]".format(
                    self.var_agg_data,
                    var_signature_to_agg_data,
                    plan.signature.code,
                ),
                0,
            )

        self._emit_scope(code, root, plan, True, after_temps=_assign_agg_data)
        return code

    def gen_aggregate_code(self):
        code = Code()
        if not self.records:
            return code
        with_init_root = build_guard_tree(self.records)
        with_init_plan = _analyze_or_unshared(
            with_init_root, self.records, True, None
        )
        expected_checksum = count_reducer_nodes(with_init_root)

        reduce_records = [r for r in self.records if r.reduce_lines]
        reduce_root = (
            build_guard_tree(reduce_records) if reduce_records else None
        )
        reduce_plan = None
        if reduce_root is not None:
            reduce_plan = _analyze_or_unshared(
                reduce_root, reduce_records, False, None
            )

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
        attrs = ["v{}".format(index) for index, _ in enumerate(self.records)]
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
                self.fmt_agg_data_value(index)
                for index, _ in enumerate(self.records)
            ]
        )
        return "{} = _none".format(vars_code)


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
     * using the same reducer twice won't result in double calculation
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

        if "grouper_function_by_id" not in ctx:
            ctx["grouper_function_by_id"] = {}
        cached = ctx["grouper_function_by_id"].get(id(self))
        if cached is not None:
            conversion = cached[1]
            function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
            function_ctx.add_arg("data_", This())
            return function_ctx.call_with_all_args(
                conversion
            ).gen_code_and_update_ctx(code_input, ctx)

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
                reduce_manager.accepts_reducers = True
                try:
                    code_agg_result = self.reducer.gen_code_and_update_ctx(
                        var_row, ctx
                    )
                finally:
                    reduce_manager.accepts_reducers = False

                by_is_single = len(self.by) == 1
                code_signatures = [
                    by_.gen_code_and_update_ctx(var_row, ctx)
                    for by_ in self.by
                ]
                code_signature = (
                    code_signatures[0]
                    if by_is_single
                    else f"({', '.join(code_signatures)})"
                )

                key_trees = [
                    ast.parse(code_by, mode="eval").body
                    for code_by in code_signatures
                ]
                result_tree = ast.parse(code_agg_result, mode="eval").body
                intern: dict = {}
                key_to_index: dict = {}
                for index, key_tree in enumerate(key_trees):
                    key_to_index.setdefault(
                        _structural_keys(key_tree, intern)[id(key_tree)][0],
                        index,
                    )
                replacer = _ReplaceKeys(
                    _structural_keys(result_tree, intern),
                    key_to_index,
                    [_free_names(key_tree) for key_tree in key_trees],
                    var_signature,
                )
                result_tree = replacer.visit(result_tree)

                if var_row in replacer.free_names:
                    raise ConversionException(
                        "something other than group_by keys and reducers have been used",
                        _fmt_expr(result_tree),
                    )
                if replacer.changed:
                    # display atoms splice safely without outer parentheses
                    code_agg_result = (
                        ast_unparse(result_tree)
                        if isinstance(result_tree, _DISPLAY_ATOMS)
                        else _fmt_expr(result_tree)
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
                            signature_tree=(
                                key_trees[0]
                                if by_is_single
                                else ast.Tuple(elts=key_trees, ctx=ast.Load())
                            ),
                        ).to_string(base_indent_level=1),
                        **agg_template_kwargs,
                    )

                conversion = function_ctx.gen_conversion(
                    converter_name, grouper_code
                )
            finally:
                ctx["current_reduce_manager"].pop()
                if not ctx["current_reduce_manager"]:
                    del ctx["current_reduce_manager"]

        ctx["grouper_function_by_id"][id(self)] = (self, conversion)
        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


def Aggregate(  # pylint:disable=invalid-name
    *args, **kwargs
) -> BaseConversion:
    """Shortcut for `GroupBy().aggregate(*args, **kwargs)`."""
    return GroupBy().aggregate(*args, **kwargs)
