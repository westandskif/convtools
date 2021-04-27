"""This module brings aggregations with various reduce functions"""
import typing
from collections import defaultdict
from functools import reduce as functools_reduce

from .base import (
    CT,
    BaseCollectionConversion,
    BaseConversion,
    Call,
    CallFunc,
    ConversionException,
    Dict,
    EscapedString,
    GetItem,
    InlineExpr,
    List,
    NaiveConversion,
    Set,
    Tuple,
    _None,
)


_none = BaseConversion._none


def call_with_params(
    callable_or_inline_expr: typing.Union[
        InlineExpr, NaiveConversion, typing.Callable
    ],
    *args,
    **kwargs,
) -> Call:
    if isinstance(callable_or_inline_expr, InlineExpr):
        return callable_or_inline_expr.pass_args(*args, **kwargs)
    elif isinstance(callable_or_inline_expr, NaiveConversion):
        if callable(callable_or_inline_expr.value):
            return callable_or_inline_expr.call(*args, **kwargs)
        raise AssertionError(
            "unexpected NaiveConversion - only wrapped callables are supported"
        )

    raise AssertionError("unexpected callable", callable_or_inline_expr)


RBT = typing.TypeVar("RBT", bound="ReduceBlock")


class ReduceBlock:
    """Represents a section of code of a single reducer"""

    var_checksum = "checksum_"
    var_expected_checksum = "expected_checksum_"

    reduce_indent = 3
    reduce_no_init_indent = 2

    def __init__(
        self,
        var_agg_data_value,
        reduce_initial,
        reduce_two,
        checksum_flag,
        unconditional_init,
    ):
        self.var_agg_data_value = var_agg_data_value
        self.reduce_initial = reduce_initial
        self.reduce_two = reduce_two
        self.checksum_flag = checksum_flag
        self.unconditional_init = unconditional_init

    def replace_var_agg_data_value(self, var_agg_data_value):
        self.reduce_initial = self.reduce_initial.replace(
            self.var_agg_data_value, var_agg_data_value
        )
        self.reduce_two = self.reduce_two.replace(
            self.var_agg_data_value, var_agg_data_value
        )
        self.var_agg_data_value = var_agg_data_value
        return self

    def union(self, reduce_block: RBT):
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        clone.reduce_initial = (
            f"{self.reduce_initial}\n{reduce_block.reduce_initial}"
        )
        clone.reduce_two = f"{self.reduce_two}\n{reduce_block.reduce_two}"
        clone.checksum_flag |= reduce_block.checksum_flag
        return clone

    def get_template_kwargs(self, no_init=False) -> typing.Dict[str, str]:
        _ = BaseConversion.indent_statements
        reduce_indent = (
            self.reduce_no_init_indent if no_init else self.reduce_indent
        )
        return {
            "var_agg_data_value": self.var_agg_data_value,
            "reduce_initial": _(self.reduce_initial, reduce_indent),
            "reduce_two": _(self.reduce_two, reduce_indent),
            "var_checksum": self.var_checksum,
            "var_expected_checksum": self.var_expected_checksum,
            "checksum_flag": self.checksum_flag,
        }

    def get_template(self, no_init=False) -> str:
        template = """
        if {var_agg_data_value} is _none:
{reduce_initial}
%(optional_checksum_code)s
        else:
{reduce_two}
"""
        no_init_template = """
{reduce_two}
"""
        optional_checksum_code = """
            if {var_agg_data_value} is not _none:
                {var_checksum} |= {checksum_flag}
                if {var_checksum} == {var_expected_checksum}:
                    break
"""
        template = no_init_template if no_init else template
        template = template % dict(
            optional_checksum_code=optional_checksum_code
            if self.checksum_flag
            else ""
        )
        return template

    def to_code(self) -> str:
        return self.get_template(no_init=False).format(
            **self.get_template_kwargs(no_init=False)
        )

    def to_no_init_code(self) -> str:
        return self.get_template(no_init=True).format(
            **self.get_template_kwargs(no_init=True)
        )

    def code_hash(self) -> str:
        code_hash = self.to_code()
        code_hash = code_hash.replace(self.var_agg_data_value, "")
        if self.checksum_flag:
            code_hash = code_hash.replace(str(self.checksum_flag), "")
        return code_hash


class ReduceConditionalBlock(ReduceBlock):
    """Represents a section of code of a single reducer with an incoming
    condition"""

    reduce_indent = 4
    reduce_no_init_indent = 3

    def __init__(self, *args, **kwargs):
        self.condition_code = kwargs.pop("condition_code")
        super().__init__(*args, **kwargs)

    def get_template(self, no_init=False):
        template = """
        if {condition_code}:
            if {var_agg_data_value} is _none:
{reduce_initial}
%(optional_checksum_code)s
            else:
{reduce_two}
"""
        no_init_template = """
        if {condition_code}:
{reduce_two}

"""
        optional_checksum_code = """
                if {var_agg_data_value} is not _none:
                    {var_checksum} |= {checksum_flag}
                    if {var_checksum} == {var_expected_checksum}:
                        break
"""
        template = no_init_template if no_init else template
        template = template % dict(
            optional_checksum_code=optional_checksum_code
            if self.checksum_flag
            else ""
        )
        return template

    def get_template_kwargs(self, no_init=False):
        template_kwargs = super().get_template_kwargs(no_init=no_init)
        template_kwargs["condition_code"] = self.condition_code
        return template_kwargs


class ReduceBlocks(typing.Generic[RBT]):
    """Represents a set of reduce blocks"""

    def __init__(self):
        self.condition_to_blocks = defaultdict(list)
        self.unconditional_init_condition_to_blocks = defaultdict(list)
        self.unconditional_init_blocks = []
        self.other_blocks = []
        self.number = 0

    def add_block(self, reduce_block: RBT):
        self.number += 1
        if isinstance(reduce_block, ReduceConditionalBlock):
            if reduce_block.unconditional_init:
                list_ = self.unconditional_init_condition_to_blocks[
                    reduce_block.condition_code
                ]
            else:
                list_ = self.condition_to_blocks[reduce_block.condition_code]
        else:
            if reduce_block.unconditional_init:
                list_ = self.unconditional_init_blocks
            else:
                list_ = self.other_blocks
        list_.append(reduce_block)

    @classmethod
    def _reduce_blocks(cls, reduce_blocks) -> typing.Optional[RBT]:
        if not reduce_blocks:
            return None
        if len(reduce_blocks) == 1:
            return reduce_blocks[0]
        return functools_reduce((lambda b1, b2: b1.union(b2)), reduce_blocks)

    def reduce_blocks(self) -> typing.Iterable[RBT]:
        blocks = []
        for blocks_ in self.condition_to_blocks.values():
            for block_ in blocks_:
                blocks.append(block_)
        for blocks_ in self.unconditional_init_condition_to_blocks.values():
            blocks.append(self._reduce_blocks(blocks_))

        block_ = self._reduce_blocks(self.unconditional_init_blocks)
        if block_:
            blocks.append(block_)

        for block_ in self.other_blocks:
            blocks.append(block_)
        return blocks

    def to_code(self) -> str:
        return "\n\n".join(block.to_code() for block in self.reduce_blocks())

    def to_no_init_code(self) -> str:
        return "\n\n".join(
            block.to_no_init_code() for block in self.reduce_blocks()
        )


GROUPER_TEMPLATE = """
def {converter_name}(data_{code_args}):
    global add_label_, get_by_label_
    _none = {var_none}
    {var_signature_to_agg_data} = defaultdict({var_agg_data_cls})
    for {var_row} in data_:
        {var_agg_data} = {var_signature_to_agg_data}[{code_signature}]
{code_reduce_blocks}

    result_ = {code_result}
    {code_sorting}
    return result_
"""
AGGREGATE_TEMPLATE = """
def {converter_name}(data_{code_args}):
    global add_label_, get_by_label_
    _none = {var_none}
    {code_init_agg_vars}
    {var_expected_checksum} = {val_expected_checksum}
    {var_checksum} = 0
    it_ = iter(data_)
    for {var_row} in it_:
{code_reduce_blocks}

    for {var_row} in it_:
{code_reduce_blocks_no_init}

    result_ = {code_result}
    {code_sorting}
    return result_
"""


RT = typing.TypeVar("RT", bound="BaseReducer")


class BaseReducer(BaseConversion, typing.Generic[RBT]):
    """Base of a reduce operation to be used during the aggregation"""

    method_calls_override_input = True
    multi_step_calculation = True

    expressions: typing.Tuple[typing.Any, ...]
    post_conversion: typing.Optional[BaseConversion] = None
    default: typing.Any
    initial: typing.Any
    condition: typing.Optional[BaseConversion] = None
    unconditional_init: bool = False

    def filter(self, condition_conversion):
        """Defines a conversion to be used as a condition. Only true values
        will be aggregated.

        Args:
          condition_conversion (object): to be wrapped with
            :py:obj:`ensure_conversion` and used as a condition
        """
        if getattr(self, "condition", None):
            raise AssertionError("condition is already present")
        cloned_self = self.clone()
        cloned_self.condition = cloned_self.ensure_conversion(
            condition_conversion
        )
        return cloned_self

    def gen_reduce_code_block(
        self,
        var_agg_data_value: str,
        var_row: str,
        checksum_flag: int,
        ctx: dict,
    ) -> RBT:
        raise NotImplementedError

    def _set_predefined_input(self: RT, input_conversion: CT) -> RT:
        cloned_self = super()._set_predefined_input(input_conversion)
        cloned_self.expressions = tuple(
            expr.set_predefined_input(input_conversion)
            for expr in self.expressions
        )
        return cloned_self

    def _add_dependency(self, dep):
        if isinstance(dep, BaseReducer):
            raise ValueError("nested aggregation", self.__dict__)
        return super()._add_dependency(dep)

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        del code_input
        agg_data_item = ctx["_reduce_id_to_var"][self.number]
        processed_agg_data_item = agg_data_item
        if self.post_conversion:
            processed_agg_data_item = (
                self.post_conversion.gen_code_and_update_ctx(
                    agg_data_item, ctx
                )
            )

        if hasattr(self, "default"):
            default_value = self.default
        elif hasattr(self, "initial"):
            default_value = self.initial
        else:
            raise AssertionError

        default_value_code = default_value.gen_code_and_update_ctx("", ctx)
        return EscapedString(
            f"({default_value_code} "
            f"if {agg_data_item} is _none "
            f"else {processed_agg_data_item})"
        ).gen_code_and_update_ctx("", ctx)


class MultiStatementReducer(BaseReducer):
    """Defines the reduce operation, which is based on multiple python
    statements, to be used during the aggregation"""

    prepare_first: typing.Tuple[str, ...]
    reduce: typing.Tuple[str, ...]

    def __init__(self, *expressions, initial=_none, default=_none):
        super().__init__()
        self.expressions = tuple(
            self.ensure_conversion(expr)
            for expr in (
                self.expressions
                if hasattr(self, "expressions") and not expressions
                else expressions
            )
        )
        if default is not _none:
            self.default = default
        if hasattr(self, "default"):
            self.default = (
                self.ensure_conversion(self.default).call()
                if callable(self.default)
                else self.ensure_conversion(self.default)
            )

        if initial is not _none:
            self.initial = initial
        if hasattr(self, "initial"):
            self.initial = (
                self.ensure_conversion(self.initial).call()
                if callable(self.initial)
                else self.ensure_conversion(self.initial)
            )

        if not hasattr(self, "initial") and not hasattr(self, "default"):
            raise ValueError("both initial and default are none")
        if not hasattr(self, "initial") and not hasattr(self, "prepare_first"):
            raise ValueError("both initial and prepare_first are none")

    def _format_statements(
        self,
        var_agg_data_value,
        var_row,
        statements,
        args,
        ctx,
    ):
        if not statements:
            statements = []
        if not statements:
            statements.append("pass")

        code = "\n".join(
            [
                statement % dict(result=var_agg_data_value, row=var_row)
                for statement in statements
            ]
        )
        return code.format(
            *(arg.gen_code_and_update_ctx(var_row, ctx) for arg in args)
        )

    def gen_reduce_code_block(
        self,
        var_agg_data_value: str,
        var_row: str,
        checksum_flag: int,
        ctx: dict,
    ) -> RBT:
        if hasattr(self, "initial"):
            reduce_initial = self._format_statements(
                var_agg_data_value,
                var_row,
                self.reduce,
                (self.initial,) + self.expressions,
                ctx,
            )
        elif hasattr(self, "prepare_first"):
            reduce_initial = self._format_statements(
                var_agg_data_value,
                var_row,
                self.prepare_first,
                self.expressions,
                ctx,
            )
        else:
            raise AssertionError

        reduce_two = self._format_statements(
            var_agg_data_value,
            var_row,
            self.reduce,
            (EscapedString(var_agg_data_value),) + self.expressions,
            ctx,
        )

        kwargs = dict(
            var_agg_data_value=var_agg_data_value,
            reduce_initial=reduce_initial,
            reduce_two=reduce_two,
            checksum_flag=checksum_flag,
        )

        if self.condition is not None:
            kwargs["condition_code"] = self.condition.gen_code_and_update_ctx(
                var_row, ctx
            )

        block_cls = (
            ReduceBlock if self.condition is None else ReduceConditionalBlock
        )
        return block_cls(unconditional_init=self.unconditional_init, **kwargs)


class Reduce(BaseReducer):
    """Defines the reduce operation, which is based on a callable /  to be used
    during the aggregation"""

    def __init__(
        self,
        to_call_with_2_args: typing.Union[typing.Callable, InlineExpr],
        *expressions: typing.Tuple[typing.Any, ...],
        initial: typing.Union[_None, typing.Callable, typing.Any] = _none,
        prepare_first: typing.Union[
            _None, typing.Callable, InlineExpr
        ] = _none,
        default: typing.Union[_None, typing.Callable, typing.Any] = _none,
        unconditional_init: bool = False,
    ):
        """
        Args:
          to_call_with_2_args: defines the reduce function/expression
          expressions: args to be passed to `to_call_with_2_args` after the
            aggregation value
          initial: defined the very first item to be passed to
            `to_call_with_2_args` item. If callable, then the result of a call
            is used.
          prepare_first: defines the reduce function/expression to be called
            on the first item to prepare it for subsequent calls of
            `to_call_with_2_args`
          default: defines the value to be returned when there was nothing to
            reduce in a group (e.g. the current reduce operation has filtered
            out some rows, while an adjacent reduce operation has got
            something to reduce, forming a group). If callable, then the result
            of a call is used.
          unconditional_init: tells whether the first call initializes the
            aggregation value OR there is a condition for that
        """
        super().__init__()
        self.to_call_with_2_args = self.ensure_conversion(to_call_with_2_args)
        self.expressions = tuple(
            self.ensure_conversion(expr) for expr in expressions
        )
        if initial is not _none:
            self.initial = (
                self.ensure_conversion(initial).call()
                if callable(initial)
                or isinstance(initial, NaiveConversion)
                and callable(initial.value)
                else self.ensure_conversion(initial)
            )
        if default is not _none:
            self.default = (
                self.ensure_conversion(default).call()
                if callable(default)
                or isinstance(default, NaiveConversion)
                and callable(default.value)
                else self.ensure_conversion(default)
            )

        if prepare_first is not _none:
            self.prepare_first = self.ensure_conversion(prepare_first)

        if not hasattr(self, "initial") and not hasattr(self, "default"):
            raise ValueError("both initial and default are none")
        if not hasattr(self, "initial") and not hasattr(self, "prepare_first"):
            raise ValueError("both initial and prepare_first are none")
        self.unconditional_init = unconditional_init

    def gen_reduce_code_block(
        self,
        var_agg_data_value: str,
        var_row: str,
        checksum_flag: int,
        ctx: dict,
    ) -> RBT:
        if hasattr(self, "initial"):
            initial_conversion = call_with_params(
                self.to_call_with_2_args,
                self.initial,
                *self.expressions,
            )
        elif hasattr(self, "prepare_first"):
            initial_conversion = call_with_params(
                self.prepare_first, *self.expressions
            )
        else:
            raise AssertionError

        reduce_initial = "{var_agg_data_value} = {code}".format(
            var_agg_data_value=var_agg_data_value,
            code=initial_conversion.gen_code_and_update_ctx(var_row, ctx),
        )
        reduce_two = "{var_agg_data_value} = {code}".format(
            var_agg_data_value=var_agg_data_value,
            code=call_with_params(
                self.to_call_with_2_args,
                EscapedString(var_agg_data_value),
                *self.expressions,
            ).gen_code_and_update_ctx(var_row, ctx),
        )
        kwargs = dict(
            var_agg_data_value=var_agg_data_value,
            reduce_initial=reduce_initial,
            reduce_two=reduce_two,
            checksum_flag=checksum_flag,
        )

        if self.condition is not None:
            kwargs["condition_code"] = self.condition.gen_code_and_update_ctx(
                var_row, ctx
            )

        block_cls = (
            ReduceBlock if self.condition is None else ReduceConditionalBlock
        )
        return block_cls(unconditional_init=self.unconditional_init, **kwargs)


class GroupBy(BaseConversion):
    """Generates the function which aggregates the data, grouping by
    conversions, specified in `__init__` method and returns list of items in a
    format defined by the parameter passed to ``aggregate`` method.

    If no group keys are passed, then it returns just a single value, defined
    by the parameter passed to ``aggregate`` method.

    Current optimizations:
     * piping like ``c.group_by(...).aggregate().pipe(...)`` won't run
       the aggregation twice, this is handled as 2 statements
     * using the same reduce clause twice (e.g. one used as an argument
       for some function calls) won't result in calculating this reduce twice
    """

    def __init__(self, *by: typing.Tuple[BaseConversion, ...]):
        """Takes any number of conversions to group by

        Args:
          by (tuple): each item is to be wrapped with
            :py:obj:`ensure_conversion`.  Each is to resolve to a hashable
            object to allow using such tuples as keys. If nothing is passed,
            aggregate the input into a single object.
        """
        super().__init__()
        self.by = [self.ensure_conversion(by_) for by_ in by]
        self.agg_items: typing.List[BaseReducer] = []
        self.reducer_result = None
        self.sort_key = False
        self.sort_key_reverse = None
        self.aggregate_mode = len(self.by) == 0

    def prepare_reducer(self, reducer) -> BaseConversion:
        reducer = self.ensure_conversion(reducer)
        if isinstance(reducer, NaiveConversion):
            raise AssertionError("unexpected reducer type", type(reducer))
        return reducer

    def aggregate(
        self, reducer: typing.Union[dict, list, set, tuple, BaseConversion]
    ) -> BaseConversion:
        """Takes the conversion which defines the desired output of
        aggregation"""
        if self.agg_items:
            raise AssertionError("aggregate has already been called")
        self_clone = self.clone()
        reducer = self_clone.reducer_result = self.prepare_reducer(reducer)
        reduce_items = []

        if isinstance(reducer, Dict):
            reduce_items = [i for k_v in reducer.key_value_pairs for i in k_v]
        elif isinstance(reducer, (List, Tuple, Set)):
            reduce_items = list(reducer.items)
        elif isinstance(reducer, BaseConversion):
            reduce_items = [reducer]
        else:
            raise AssertionError("unhandled reducer type", type(reducer))
        self_clone.ensure_conversion(reducer)

        agg_items = self_clone.agg_items = []
        for reduce_item in reduce_items:
            agg_items.extend(reduce_item.get_dependencies(types=BaseReducer))

        return self_clone

    def filter(self, condition_conv, cast=_none) -> BaseConversion:
        """Same as :py:obj:`convtools.base.BaseComprehensionConversion.filter`.
        The only exception is that it works with results, not initial items."""
        cast = list if cast is self._none else cast
        return super().filter(condition_conv, cast=cast)

    def sort(self, key=None, reverse=False) -> "GroupBy":
        """Same as :py:obj:`convtools.base.BaseComprehensionConversion.sort`.
        The only exception is that it works with results, not initial items."""
        if self.sort_key is not False:
            raise AssertionError("sort has already been called")
        self_clone = self.clone()
        self_clone.sort_key = key
        self_clone.sort_key_reverse = reverse
        return self_clone

    def _gen_reducer_result_item(
        self,
        item,
        var_signature,
        var_row,
        signature_code_items,
        ctx,
    ) -> BaseConversion:
        code_item = item.gen_code_and_update_ctx(var_row, ctx)
        for code_index, code_signature_item in enumerate(signature_code_items):
            if code_signature_item in code_item:
                code_signature_item_getter = (
                    EscapedString(var_signature).item(code_index)
                    if len(signature_code_items) > 1
                    else EscapedString(var_signature)
                ).gen_code_and_update_ctx("", ctx)

                code_item = code_item.replace(
                    code_signature_item,
                    code_signature_item_getter,
                )
        if var_row in code_item:
            raise ConversionException(
                "failed to find such field in group by fields"
            )
        return EscapedString(code_item)

    def _rebuild_reducer_result(
        self,
        var_signature_to_agg_data,
        var_signature,
        var_agg_data,
        var_row,
        signature_code_items,
        ctx,
    ) -> BaseConversion:
        if isinstance(self.reducer_result, Dict):
            new_key_value_pairs = []
            for k_v in self.reducer_result.key_value_pairs:
                new_key_value_pairs.append(
                    tuple(
                        self._gen_reducer_result_item(
                            i,
                            var_signature,
                            var_row,
                            signature_code_items,
                            ctx,
                        )
                        for i in k_v
                    )
                )
            code_reducer_result = Dict(
                *new_key_value_pairs
            ).gen_code_and_update_ctx("", ctx)

        elif isinstance(self.reducer_result, BaseCollectionConversion):
            code_reducer_result = self.reducer_result.__class__(
                *(
                    self._gen_reducer_result_item(
                        i,
                        var_signature,
                        var_row,
                        signature_code_items,
                        ctx,
                    )
                    for i in self.reducer_result.items
                )
            ).gen_code_and_update_ctx("", ctx)
        elif isinstance(self.reducer_result, BaseConversion):
            code_reducer_result = self._gen_reducer_result_item(
                self.reducer_result,
                var_signature,
                var_row,
                signature_code_items,
                ctx,
            ).gen_code_and_update_ctx("", ctx)
        else:
            raise AssertionError(
                "unsupported reducer result", self.reducer_result
            )

        if self.aggregate_mode:
            return EscapedString(f"{code_reducer_result}")
        return EscapedString(
            f"[{code_reducer_result} "
            f"for {var_signature}, {var_agg_data} "
            f"in {var_signature_to_agg_data}.items()]"
        )

    def _gen_agg_data_container(self, number_of_reducers, initial_val=_none):
        attrs = []
        init_lines = []
        for i in range(number_of_reducers):
            attr = "v%d" % i
            attrs.append("'%s'" % attr)
            init_lines.append(f"        self.{attr} = _none")

        agg_data_container_code = (
            "class AggData:\n    __slots__ = [{}]\n    def __init__(self):\n{}"
        ).format(
            ", ".join(attrs),
            "\n".join(init_lines) if init_lines else "        pass",
        )
        ctx = {"_none": initial_val, "__name__": "_convtools_agg"}
        exec(agg_data_container_code, ctx, ctx)
        return ctx["AggData"]

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        aggregate_mode = len(self.by) == 0

        var_row = "row_"
        var_signature = "signature_"
        var_signature_to_agg_data = "signature_to_agg_data_"
        var_agg_data = "agg_data_"
        var_agg_data_cls = self.gen_name("AggData", ctx, self)

        signature_code_items = [
            by_.gen_code_and_update_ctx(var_row, ctx) for by_ in self.by
        ]
        if len(signature_code_items) == 1:
            code_signature = signature_code_items[0]
        else:
            code_signature = f"({','.join(signature_code_items)},)"

        expected_checksum = 0
        reduce_blocks: ReduceBlocks = ReduceBlocks()
        var_agg_data_values = []
        code_signature_to_agg_index: typing.Dict[str, int] = {}
        reduce_id_to_var = ctx.setdefault("_reduce_id_to_var", {})

        def gen_agg_data_value(value_index):
            if aggregate_mode:
                return EscapedString(
                    f"{var_agg_data}v{value_index}_"
                ).gen_code_and_update_ctx("", ctx)
            else:
                return (
                    EscapedString(var_agg_data)
                    .attr(f"v{value_index}")
                    .gen_code_and_update_ctx("", ctx)
                )

        for agg_index, agg_item in enumerate(self.agg_items):
            checksum_flag = 1 << agg_index if self.aggregate_mode else 0
            reduce_block = agg_item.gen_reduce_code_block(
                gen_agg_data_value(agg_index),
                var_row,
                checksum_flag,
                ctx,
            )
            code_hash = reduce_block.code_hash()

            if code_hash in code_signature_to_agg_index:
                reduce_block_index = code_signature_to_agg_index[code_hash]
            else:
                reduce_block_index = reduce_blocks.number
                code_signature_to_agg_index[code_hash] = reduce_block_index

                expected_checksum |= checksum_flag
                # updating var_agg_data_value because multiple reducers may be
                # skipped because of de-duplication
                reduce_block.replace_var_agg_data_value(
                    gen_agg_data_value(reduce_block_index)
                )
                reduce_blocks.add_block(reduce_block)
                var_agg_data_values.append(reduce_block.var_agg_data_value)

            reduce_id_to_var[agg_item.number] = gen_agg_data_value(
                reduce_block_index
            )

        ctx.update({"defaultdict": defaultdict})

        if aggregate_mode:
            code_init_agg_vars = "{} = _none".format(
                " = ".join(var_agg_data_values)
            )
        else:
            ctx[var_agg_data_cls] = self._gen_agg_data_container(
                reduce_blocks.number, self._none
            )

        code_result = self._rebuild_reducer_result(
            var_signature_to_agg_data,
            var_signature,
            var_agg_data,
            var_row,
            signature_code_items,
            ctx,
        ).gen_code_and_update_ctx("", ctx)

        if self.sort_key is not False:
            code_sorting = (
                EscapedString("result_")
                .call_method(
                    "sort", key=self.sort_key, reverse=self.sort_key_reverse
                )
                .gen_code_and_update_ctx("", ctx)
            )
        else:
            code_sorting = ""

        agg_template_kwargs = dict(
            code_args=self.get_args_def_code(as_kwargs=False),
            var_none=NaiveConversion(self._none).gen_code_and_update_ctx(
                "", ctx
            ),
            code_reduce_blocks=reduce_blocks.to_code(),
            code_result=code_result,
            code_sorting=code_sorting,
            var_row=var_row,
        )

        if self.aggregate_mode:
            converter_name = self.gen_name("aggregate", ctx, self)
            grouper_code = AGGREGATE_TEMPLATE.format(
                converter_name=converter_name,
                code_init_agg_vars=code_init_agg_vars,
                code_reduce_blocks_no_init=reduce_blocks.to_no_init_code(),
                var_expected_checksum=ReduceBlock.var_expected_checksum,
                val_expected_checksum=expected_checksum,
                var_checksum=ReduceBlock.var_checksum,
                **agg_template_kwargs,
            )
        else:
            converter_name = self.gen_name("group_by", ctx, self)
            grouper_code = GROUPER_TEMPLATE.format(
                converter_name=converter_name,
                var_signature_to_agg_data=var_signature_to_agg_data,
                var_agg_data_cls=var_agg_data_cls,
                var_agg_data=var_agg_data,
                code_signature=code_signature,
                **agg_template_kwargs,
            )

        group_data_func = self._code_to_converter(
            converter_name=converter_name,
            code=grouper_code,
            ctx=ctx,
        )
        return CallFunc(
            group_data_func, GetItem(), *self.get_args_as_func_args()
        ).gen_code_and_update_ctx(code_input, ctx)


def Aggregate(*args, **kwargs) -> BaseConversion:
    """Shortcut for ``GroupBy().aggregate(*args, **kwargs)``"""
    return GroupBy().aggregate(*args, **kwargs)


class SumReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = ({0} or 0)",)
    reduce = ("%(result)s = {0} + ({1} or 0)",)
    default = 0
    unconditional_init = True


class SumOrNoneReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = (
        "if {1} is None:",
        "    %(result)s = None",
        "elif {0} is not None:",
        "    %(result)s = {0} + {1}",
    )
    default = None
    unconditional_init = True


class MaxReducer(MultiStatementReducer):
    prepare_first = (
        "if {0} is not None:",
        "    %(result)s = {0}",
    )
    reduce = (
        "if {1} is not None and {1} > {0}:",
        "    %(result)s = {1}",
    )
    default = None


class MinReducer(MultiStatementReducer):
    prepare_first = (
        "if {0} is not None:",
        "    %(result)s = {0}",
    )
    reduce = (
        "if {1} is not None and {1} < {0}:",
        "    %(result)s = {1}",
    )
    default = None


class CountReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = 1",)
    reduce = ("%(result)s = {0} + 1",)
    default = 0
    unconditional_init = True


class CountDistinctReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {{ {0} }}",)
    reduce = ("%(result)s.add({1})",)
    default = 0
    unconditional_init = True
    post_conversion = InlineExpr("{set_} and len({set_}) or 0").pass_args(
        set_=GetItem()
    )


class FirstReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = ()
    default = None
    unconditional_init = True


class LastReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = ("%(result)s = {1}",)
    default = None
    unconditional_init = True


class MaxRowReducer(MultiStatementReducer):
    """Reducer which finds an item with max value of the expression and returns
    this item"""

    prepare_first = (
        "if {0} is not None:",
        "    %(result)s = ({0}, %(row)s)",
    )
    reduce = (
        "if {1} is not None and {0}[0] < {1}:",
        "    %(result)s = ({1}, %(row)s)",
    )
    default = None
    post_conversion = GetItem(1)


class MinRowReducer(MaxRowReducer):
    reduce = (
        "if {1} is not None and {0}[0] > {1}:",
        "    %(result)s = ({1}, %(row)s)",
    )


class ArrayReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = [{0}]",)
    reduce = ("%(result)s.append({1})",)
    default = None
    unconditional_init = True


class ArrayDistinctReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {{ {0}: None }}",)
    reduce = ("%(result)s[{1}] = None",)
    post_conversion = InlineExpr("list({0})").pass_args(GetItem())
    default = None
    unconditional_init = True


class BaseDictReducer(MultiStatementReducer):
    """This reducer accepts 2 expressions:

    - the first one is used to calculate keys of the resulting dict
    - the second one is used to calculate values to be reduced and put as the
      final value, under the certain key.

    Effectively dict reducers allow for double grouping: the first one on the
    top level, the second one on DictReducer level.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # for backward compatibility with versions <= 0.8
        if len(self.expressions) == 1:
            expr = self.expressions[0]
            if isinstance(expr, (Tuple, List)) and len(expr.items) == 2:
                self.expressions = tuple(expr.items)
        if len(self.expressions) != 2:
            raise ValueError("invalid dict reducer input: two values expected")


class DictReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: {1} }}",)
    reduce = ("%(result)s[{1}] = {2}",)
    default = None
    unconditional_init = True


class DictArrayReducer(BaseDictReducer):
    prepare_first = (
        "%(result)s = _d = defaultdict(list)",
        "_d[{0}].append({1})",
    )
    reduce = ("%(result)s[{1}].append({2})",)
    post_conversion = InlineExpr("dict({})").pass_args(GetItem())
    default = None
    unconditional_init = True


class DictArrayDistinctReducer(BaseDictReducer):
    """Dict reducer where dict values are lists of distinct values"""

    prepare_first = (
        "%(result)s = _d = defaultdict(dict)",
        "_d[{0}][{1}] = None",
    )
    reduce = ("%(result)s[{1}][{2}] = None",)
    post_conversion = InlineExpr(
        "{{k_: list(v_) for k_, v_ in {}.items()}}"
    ).pass_args(GetItem())
    default = None
    unconditional_init = True


class DictSumReducer(BaseDictReducer):
    prepare_first = (
        "%(result)s = _d = defaultdict(int)",
        "_d[{0}] = {1} or 0",
    )
    reduce = ("%(result)s[{1}] = {0}[{1}] + ({2} or 0)",)
    post_conversion = InlineExpr("dict({})").pass_args(GetItem())
    default = None
    unconditional_init = True


class DictSumOrNoneReducer(BaseDictReducer):
    """Dict reducer where dict values are either numbers or None if there's
    been at least one None value within the group"""

    prepare_first = ("%(result)s = _d = defaultdict(int)", "_d[{0}] = {1}")
    reduce = (
        "if {2} is None:",
        "    %(result)s[{1}] = None",
        "elif {0}[{1}] is not None:",
        "    %(result)s[{1}] = {0}[{1}] + {2}",
    )
    post_conversion = InlineExpr("dict({})").pass_args(GetItem())
    default = None
    unconditional_init = True


class DictMaxReducer(BaseDictReducer):
    prepare_first = (
        "if {1} is not None:",
        "    %(result)s = {{ {0}: {1} }}",
    )
    reduce = (
        "if {2} is not None and ({1} not in {0} or {2} > {0}[{1}]):",
        "    %(result)s[{1}] = {2}",
    )
    default = None


class DictMinReducer(DictMaxReducer):
    reduce = (
        "if {2} is not None and ({1} not in {0} or {2} < {0}[{1}]):",
        "    %(result)s[{1}] = {2}",
    )


class DictCountReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: 1 }}",)
    reduce = (
        "if {1} not in {0}:",
        "    %(result)s[{1}] = 1",
        "else:",
        "    %(result)s[{1}] = {0}[{1}] + 1",
    )
    default = None
    unconditional_init = True


class DictCountDistinctReducer(BaseDictReducer):
    """Dict reducer where dict values are numbers of distinct values per
    group"""

    prepare_first = ("%(result)s = {{ {0}: {{ {1} }} }}",)
    reduce = (
        "if {1} not in {0}:",
        "    %(result)s[{1}] = {{ {2} }}",
        "else:",
        "    %(result)s[{1}].add({2})",
    )
    post_conversion = InlineExpr(
        "{{ k_: len(v_) for k_, v_ in {}.items() }}"
    ).pass_args(GetItem())
    default = None
    unconditional_init = True


class DictFirstReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: {1} }}",)
    reduce = ("if {1} not in {0}:", "    %(result)s[{1}] = {2}")
    default = None
    unconditional_init = True


class DictLastReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: {1} }}",)
    reduce = ("%(result)s[{1}] = {2}",)
    default = None
    unconditional_init = True


class AverageReducer(MultiStatementReducer):
    def __init__(self, value, weight=1, *args, **kwargs):
        super().__init__(value, weight, *args, **kwargs)

    prepare_first = (
        "if {0} is not None:",
        "    %(result)s = ({1}, {0} * {1})",
    )
    reduce = (
        "if {1} is not None:",
        "    %(result)s = ({0}[0] + {2}, {0}[1] + {1} * {2})",
    )
    default = None
    post_conversion = GetItem(1) / GetItem(0)


class TopReducer(DictCountReducer):
    def __init__(self, k: int, key_conv, *args, **kwargs):
        super().__init__(key_conv, 1, *args, **kwargs)
        if not isinstance(k, int):
            raise TypeError

        if k < 1:
            raise ValueError("K must be positive integer greater than 0.")

        self.k = k

    @property
    def post_conversion(self):
        return InlineExpr(
            "[k for k,v in sorted((v,k) for k,v in {data}.items())[:-{k}:-1]]"
        ).pass_args(data=GetItem(), k=self.k + 1)


class ModeReducer(DictCountReducer):
    def __init__(self, conv, *args, **kwargs):
        super().__init__(conv, conv, *args, **kwargs)

    post_conversion = InlineExpr(
        "sorted(((v,k) for k,v in {data}.items()))[-1][1]"
    ).pass_args(data=GetItem())


class MedianReducer(ArrayReducer):
    @property
    def post_conversion(self):
        import statistics

        return CallFunc(statistics.median, GetItem())


class ReduceFuncs:
    """Exposes the list of reduce functions"""

    # pylint: disable=invalid-name

    #: Calculates the sum, skips false values
    Sum = SumReducer
    #: Calculates the sum, any ``None`` makes the total sum ``None``
    SumOrNone = SumOrNoneReducer

    #: Finds max value, skips ``None``
    Max = MaxReducer
    #: Finds a row with max value, skips ``None``
    MaxRow = MaxRowReducer

    #: Finds min value, skips ``None``
    Min = MinReducer
    #: Finds a row with min value, skips ``None``
    MinRow = MinRowReducer

    #: Counts objects
    Count = CountReducer
    #: Counts distinct values
    CountDistinct = CountDistinctReducer

    #: Stores the first value per group
    First = FirstReducer
    #: Stores the last value per group
    Last = LastReducer

    #: Calculates the arithmetic mean.
    Average = AverageReducer
    #: Calculates the median value.
    Median = MedianReducer
    #: Calculates the most common value.
    #: In case of multiple values, returns the last of them.
    Mode = ModeReducer
    #: Returns a list of the approximately most frequent values.
    #: The resulting list is sorted in descending order of values frequency.
    TopK = TopReducer

    #: Aggregates values into array
    Array = ArrayReducer
    #: Aggregates distinct values into array, preserves order
    ArrayDistinct = ArrayDistinctReducer

    #: Aggregates values into dict; dict values are last values per group
    Dict = DictReducer
    #: Aggregates values into dict; dict values are lists of group values
    DictArray = DictArrayReducer
    #: Aggregates values into dict; dict values are lists of unique group
    #: values preserves order
    DictArrayDistinct = DictArrayDistinctReducer
    #: Aggregates values into dict; dict values are sums of group values,
    #: skipping ``None``
    DictSum = DictSumReducer
    #: Aggregates values into dict; dict values are sums of group values,
    #: any ``None`` makes the total sum ``None``
    DictSumOrNone = DictSumOrNoneReducer
    #: Aggregates values into dict; dict values are max group values
    DictMax = DictMaxReducer
    #: Aggregates values into dict; dict values are min group values
    DictMin = DictMinReducer
    #: Aggregates values into dict; dict values are numbers of values in groups
    DictCount = DictCountReducer
    #: Aggregates values into dict; dict values are numbers of unique values
    #: in groups
    DictCountDistinct = DictCountDistinctReducer
    #: Aggregates values into dict; dict values are first values per group
    DictFirst = DictFirstReducer
    #: Aggregates values into dict; dict values are last values per group
    DictLast = DictLastReducer
