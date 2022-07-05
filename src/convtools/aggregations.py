"""This module brings aggregations with various reduce functions"""
import typing as t
from collections import defaultdict
from decimal import Decimal
from math import ceil

from .base import (
    CT,
    BaseConversion,
    CallFunc,
    CodeGenerationOptionsCtx,
    ConversionException,
    EscapedString,
    FilterConversion,
    GetItem,
    If,
    InlineExpr,
    List,
    NaiveConversion,
    This,
    Tuple,
    _None,
    ensure_conversion,
)
from .utils import Code


_none = BaseConversion._none
RBT = t.TypeVar("RBT", bound="ReduceBlock")


class ReduceBlock:
    """Represents a section of code of a single reducer"""

    var_checksum = "checksum_"
    var_expected_checksum = "expected_checksum_"

    def __init__(
        self,
        reduce_initial: t.Iterable[str],
        reduce_two: t.Iterable[str],
        reducer_code_input: str,
        var_agg_data_value: str,
        checksum_flag: int,
        unconditional_init: bool,
    ):
        self.reduce_initial = {var_agg_data_value: reduce_initial}
        self.reduce_two = {var_agg_data_value: reduce_two}
        self.reducer_code_input = reducer_code_input
        self.condition_code = None
        self.unconditional_init = unconditional_init
        self.checksum_flag = checksum_flag

    def consume(self: RBT, reduce_block: RBT) -> RBT:
        if (
            self.condition_code != reduce_block.condition_code
            or not self.unconditional_init
            or not reduce_block.unconditional_init
        ):
            raise AssertionError

        for k, v in reduce_block.reduce_initial.items():
            if k in self.reduce_initial:
                raise AssertionError
            self.reduce_initial[k] = v

        for k, v in reduce_block.reduce_two.items():
            if k in self.reduce_two:
                raise AssertionError
            self.reduce_two[k] = v

        self.checksum_flag |= reduce_block.checksum_flag
        return self

    def iter_reduce_lines(self, lines_info_dict) -> t.Iterable[str]:
        for var_agg_data_value, lines in lines_info_dict.items():
            template_kwargs = {
                "result": var_agg_data_value,
                "input": self.reducer_code_input,
            }
            yield from (line % template_kwargs for line in lines)

    def iter_reduce_initial_lines(self) -> t.Iterable[str]:
        yield from self.iter_reduce_lines(self.reduce_initial)

    def iter_reduce_two_lines(self) -> t.Iterable[str]:
        yield from self.iter_reduce_lines(self.reduce_two)

    def as_key(self):
        return (
            self.condition_code,
            self.unconditional_init,
            self.reducer_code_input,
            tuple(
                line
                for lines in self.reduce_initial.values()
                for line in lines
            ),
            tuple(
                line for lines in self.reduce_two.values() for line in lines
            ),
        )


class ReduceConditionalBlock(ReduceBlock):
    """Represents a section of code of a single reducer with an incoming
    condition"""

    def __init__(self, *args, **kwargs):
        condition_code = kwargs.pop("condition_code")
        super().__init__(*args, **kwargs)
        self.condition_code = condition_code


class ReduceBlocks(t.Generic[RBT]):
    """Represents a set of reduce blocks"""

    def __init__(self):
        self.condition_to_blocks = {}
        self.other_blocks = []
        self.number = 0

    def add_block(self, reduce_block: RBT):
        self.number += 1

        if reduce_block.unconditional_init:
            condition = (
                reduce_block.condition_code
                if isinstance(reduce_block, ReduceConditionalBlock)
                else None
            )

            if condition in self.condition_to_blocks:
                self.condition_to_blocks[condition].consume(reduce_block)
            else:
                self.condition_to_blocks[condition] = reduce_block

        else:
            return self.other_blocks.append(reduce_block)

    def iter_blocks(self) -> t.Iterable[RBT]:
        yield from self.condition_to_blocks.values()
        yield from self.other_blocks

    def gen_group_by_code(
        self,
        var_row,
        var_agg_data,
        var_signature_to_agg_data,
        code_signature,
    ) -> Code:
        code = Code()
        code.add_line(f"for {var_row} in data_:", 1)
        code.add_line(
            f"{var_agg_data} = {var_signature_to_agg_data}[{code_signature}]",
            0,
        )

        for block in self.iter_blocks():
            reduce_initial_lines = list(block.iter_reduce_initial_lines())
            reduce_two_lines = list(block.iter_reduce_two_lines())
            any_var_agg_data_value = next(iter(block.reduce_initial))

            if block.condition_code:
                code.add_line(f"if {block.condition_code}:", 1)

            code.add_line(f"if {any_var_agg_data_value} is _none:", 1)
            for line in reduce_initial_lines:
                code.add_line(line, 0)
            code.incr_indent_level(-1)

            if reduce_two_lines:
                code.add_line("else:", 1)
                for line in reduce_two_lines:
                    code.add_line(line, 0)
                code.incr_indent_level(-1)

            if block.condition_code:
                code.incr_indent_level(-1)
        return code

    def gen_aggregate_code(
        self,
        var_row,
        var_checksum,
        var_expected_checksum,
    ) -> Code:
        first_phase_code = Code()
        second_phase_code = Code()

        needs_sum_checking = False

        reduce_blocks = list(self.iter_blocks())
        is_single_block = len(reduce_blocks) == 1
        for block in reduce_blocks:
            reduce_initial_lines = list(block.iter_reduce_initial_lines())
            reduce_two_lines = list(block.iter_reduce_two_lines())
            any_var_agg_data_value = next(iter(block.reduce_initial))

            init_phase_needs_else = not (
                is_single_block and block.unconditional_init
            )

            if block.condition_code:
                first_phase_code.add_line(f"if {block.condition_code}:", 1)

            first_phase_code.add_line(
                f"if {any_var_agg_data_value} is _none:", 1
            )
            for line in reduce_initial_lines:
                first_phase_code.add_line(line, 0)

            if is_single_block:
                if block.unconditional_init:
                    first_phase_code.add_line("break", 0)
                else:
                    first_phase_code.add_line(
                        f"if {any_var_agg_data_value} is not _none:", 1
                    )
                    first_phase_code.add_line("break", -1)

            else:
                if block.unconditional_init:
                    first_phase_code.add_line(
                        f"{var_checksum} |= {block.checksum_flag}", 0
                    )
                else:
                    first_phase_code.add_line(
                        f"if {any_var_agg_data_value} is not _none:", 1
                    )
                    first_phase_code.add_line(
                        f"{var_checksum} |= {block.checksum_flag}", -1
                    )
                needs_sum_checking = True

            first_phase_code.incr_indent_level(-1)

            if init_phase_needs_else and reduce_two_lines:
                first_phase_code.add_line("else:", 1)
                for line in reduce_two_lines:
                    first_phase_code.add_line(line, 0)
                first_phase_code.incr_indent_level(-1)

            if block.condition_code:
                first_phase_code.incr_indent_level(-1)

            if reduce_two_lines:
                if block.condition_code:
                    second_phase_code.add_line(
                        f"if {block.condition_code}:", 1
                    )

                for line in reduce_two_lines:
                    second_phase_code.add_line(line, 0)

                if block.condition_code:
                    second_phase_code.incr_indent_level(-1)

        resulting_code = Code()

        resulting_code.add_line("it_ = iter(data_)", 0)
        resulting_code.add_line(f"for {var_row} in it_:", 1)

        resulting_code.add_code(first_phase_code)
        if needs_sum_checking:
            resulting_code.add_line(
                f"if {var_checksum} == {var_expected_checksum}: break", 0
            )
        resulting_code.incr_indent_level(-1)

        if second_phase_code.has_lines():
            resulting_code.add_line("", 0)
            resulting_code.add_line(f"for {var_row} in it_:", 1)

            resulting_code.add_code(second_phase_code)
            resulting_code.incr_indent_level(-1)
        return resulting_code


GROUPER_TEMPLATE = """
def {converter_name}({code_args}):
    {var_signature_to_agg_data} = defaultdict({var_agg_data_cls})

{code_group_by}

{code_result}
"""
AGGREGATE_TEMPLATE = """
def {converter_name}({code_args}):
    {code_init_agg_vars}
    {var_expected_checksum} = {val_expected_checksum}
    {var_checksum} = 0

{code_aggregate}

{code_result}
"""


RT = t.TypeVar("RT", bound="BaseReducer")


class BaseReducer(BaseConversion, t.Generic[RBT, CT]):
    """Base of a reduce operation to be used during the aggregation"""

    expressions: t.Tuple[t.Any, ...]
    post_conversion: t.Optional[BaseConversion] = None
    default: t.Any
    where: t.Optional[BaseConversion] = None
    unconditional_init: bool = False

    self_content_type = (
        (
            BaseConversion.self_content_type
            & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
        )
        | BaseConversion.ContentTypes.REDUCER
        | BaseConversion.ContentTypes.NONE_USAGE
    )

    def __init__(self, default, initial):
        super().__init__()

        self.default, self.initial = self.prepare_default_n_initial(
            default, initial
        )
        self.conversion = self.ensure_conversion(
            If(
                This().is_(EscapedString("_none")),
                self.default,
                (
                    self.post_conversion
                    if self.post_conversion is not None
                    else This()
                ),
            )
        )

    def gen_reduce_code_block(
        self,
        var_agg_data_value: str,
        reducer_code_input: str,
        checksum_flag: int,
        ctx: dict,
    ) -> RBT:
        raise NotImplementedError

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        if (
            CodeGenerationOptionsCtx.get_option_value("reducers_run_stage")
            == "collecting_reducer_inputs"
        ):
            reducer_result_code = self.gen_name(
                "rrc_", ctx, (self, code_input)
            )
            reducer_inputs_info = ctx["_reducer_inputs_info"][-1]
            reducer_inputs_info[(code_input, reducer_result_code)].append(self)
            return self.conversion.gen_code_and_update_ctx(
                reducer_result_code, ctx
            )

        raise AssertionError("reducers cannot be used outside of aggregations")

    def prepare_default_n_initial(self, default, initial):
        if default is _none:
            try:
                default = self.default
            except AttributeError:
                pass

        if initial is _none and hasattr(self, "initial"):
            initial = self.initial
        if initial is not _none:
            initial = self.ensure_conversion(initial)
            if initial.is_itself_callable_like():
                initial = initial.call_like()

            if default is _none and initial.ignores_input():
                default = initial

        if default is _none:
            raise ValueError("default is not provided")

        default = self.ensure_conversion(default)
        if default.is_itself_callable_like():
            default = default.call_like()

        return default, initial


class MultiStatementReducer(BaseReducer):
    """Defines the reduce operation, which is based on multiple python
    statements, to be used during the aggregation"""

    base_condition_code: "t.Optional[str]" = None
    prepare_first: t.Tuple[str, ...]
    reduce: t.Tuple[str, ...]

    def __init__(self, *expressions, initial=_none, default=_none, where=None):
        super().__init__(default, initial)
        self.where = None if where is None else self.ensure_conversion(where)

        self.expressions = tuple(
            self.ensure_conversion(expr)
            for expr in (
                self.expressions
                if hasattr(self, "expressions") and not expressions
                else expressions
            )
        )

    def _format_statements(
        self,
        statements,
        args,
        reducer_code_input,
        ctx,
        prev_result="%(result)s",
    ):
        code_args = tuple(
            arg.gen_code_and_update_ctx(reducer_code_input, ctx)
            for arg in args
        )
        return [
            statement.format(*code_args, prev_result=prev_result)
            for statement in statements
        ]

    def gen_reduce_code_block(
        self,
        var_agg_data_value: str,
        reducer_code_input: str,
        checksum_flag: int,
        ctx: dict,
    ) -> RBT:
        if self.initial is _none:
            reduce_initial = self._format_statements(
                (
                    self.prepare_first(ctx)
                    if callable(self.prepare_first)
                    else self.prepare_first
                ),
                self.expressions,
                reducer_code_input,
                ctx,
            )
        else:
            reduce_initial = self._format_statements(
                (self.reduce(ctx) if callable(self.reduce) else self.reduce),
                self.expressions,
                reducer_code_input,
                ctx,
                prev_result=self.initial.gen_code_and_update_ctx(
                    reducer_code_input, ctx
                ),
            )

        reduce_two = self._format_statements(
            (self.reduce(ctx) if callable(self.reduce) else self.reduce),
            self.expressions,
            reducer_code_input,
            ctx,
        )

        kwargs = {
            "reduce_initial": reduce_initial,
            "reduce_two": reduce_two,
            "reducer_code_input": reducer_code_input,
            "var_agg_data_value": var_agg_data_value,
            "checksum_flag": checksum_flag,
            "unconditional_init": self.unconditional_init,
        }
        if self.where is not None:
            condition_code = self.where.gen_code_and_update_ctx(
                reducer_code_input, ctx
            )
            if condition_code != "True":
                kwargs["condition_code"] = condition_code

        if self.base_condition_code:
            base_condition_code = self._format_statements(
                [self.base_condition_code],
                self.expressions,
                reducer_code_input,
                ctx,
            )[0]
            if "condition_code" in kwargs:
                kwargs[
                    "condition_code"
                ] = f"{base_condition_code} and {kwargs['condition_code']}"
            else:
                kwargs["condition_code"] = base_condition_code

        block_cls = (
            ReduceConditionalBlock
            if "condition_code" in kwargs
            else ReduceBlock
        )
        return block_cls(**kwargs)


class Reduce(BaseReducer):
    """Defines the reduce operation, which is based on a callable / expression
    to be used during the aggregation"""

    initial: t.Any

    def __init__(
        self,
        to_call_with_2_args: t.Union[t.Callable, InlineExpr],
        *expressions: t.Tuple[t.Any, ...],
        initial: t.Union[_None, t.Callable, InlineExpr, t.Any],
        default: t.Union[_None, t.Callable, t.Any] = _none,
        unconditional_init: bool = False,
        where=None,
    ):
        """
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
        """
        super().__init__(default, initial)
        self.where = None if where is None else self.ensure_conversion(where)
        self.to_call_with_2_args = self.ensure_conversion(to_call_with_2_args)
        self.expressions = tuple(
            self.ensure_conversion(expr) for expr in expressions
        )
        self.unconditional_init = unconditional_init

    def gen_reduce_code_block(
        self,
        var_agg_data_value: str,
        reducer_code_input: str,
        checksum_flag: int,
        ctx: dict,
    ) -> RBT:
        _ = self.to_call_with_2_args.call_like(
            self.initial,
            *self.expressions,
        ).gen_code_and_update_ctx(reducer_code_input, ctx)
        reduce_initial = [f"%(result)s = {_}"]
        _ = self.to_call_with_2_args.call_like(
            EscapedString("%(result)s"),
            *self.expressions,
        ).gen_code_and_update_ctx(reducer_code_input, ctx)
        reduce_two = [f"%(result)s = {_}"]

        kwargs = {
            "reduce_initial": reduce_initial,
            "reduce_two": reduce_two,
            "reducer_code_input": reducer_code_input,
            "var_agg_data_value": var_agg_data_value,
            "checksum_flag": checksum_flag,
            "unconditional_init": self.unconditional_init,
        }
        if self.where is not None:
            condition_code = self.where.gen_code_and_update_ctx(
                reducer_code_input, ctx
            )
            if condition_code != "True":
                kwargs["condition_code"] = condition_code

        block_cls = (
            ReduceConditionalBlock
            if "condition_code" in kwargs
            else ReduceBlock
        )

        return block_cls(**kwargs)


class GroupBy(BaseConversion, t.Generic[RBT, CT]):
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

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.AGGREGATION
        | BaseConversion.ContentTypes.NONE_USAGE
    )

    def __init__(self, *by: t.Tuple[BaseConversion, ...]):
        """Takes any number of conversions to group by

        Args:
          by (tuple): each item is to be wrapped with
            :py:obj:`ensure_conversion`.  Each is to resolve to a hashable
            object to allow using such tuples as keys. If nothing is passed,
            aggregate the input into a single object.
        """
        super().__init__()
        self.by = [self.ensure_conversion(by_) for by_ in by]
        self.agg_result: t.Optional[BaseConversion] = None
        self.aggregate_mode = len(self.by) == 0
        self.filter_conversion = None
        self.filter_cast = None

    def aggregate(
        self, reducer: t.Union[dict, list, set, tuple, BaseConversion]
    ) -> "GroupBy":
        """Takes the conversion which defines the desired output of
        aggregation"""
        self_clone = self.clone()
        self_clone.agg_result = self_clone.ensure_conversion(reducer)
        self_clone.contents = self_clone.contents & ~self.ContentTypes.REDUCER

        if isinstance(self_clone.agg_result, NaiveConversion):
            raise AssertionError("unexpected reducer type", type(reducer))

        self_clone.number_of_input_uses = 1
        return self_clone

    def filter(
        self, condition_conv, cast=BaseConversion._none
    ) -> "BaseConversion":
        if cast is self._none:
            cast = list
        if self.aggregate_mode or self.filter_conversion is not None:
            return super().filter(condition_conv, cast=cast)
        self_clone = self.clone()
        self_clone.filter_conversion = self_clone.ensure_conversion(
            condition_conv
        )
        self_clone.filter_cast = cast
        self_clone.number_of_input_uses = 1
        return self_clone

    def _gen_agg_data_container(self, container_name, number_of_reducers, ctx):
        attrs = [f"v{i}" for i in range(number_of_reducers)]

        code = Code()
        code.add_line(f"class {container_name}:", 1)
        _ = ",".join(f"'{attr}'" for attr in attrs)
        code.add_line(f"__slots__ = [{_}]", 0)
        code.add_line("def __init__(self, _none=__none__):", 1)
        if attrs:
            for attr in attrs:
                code.add_line(f"self.{attr} = _none", 0)
        else:
            code.add_line("pass", 0)
        return self.compile_converter(container_name, code.to_string(0), ctx)

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        if self.agg_result is None:
            raise AssertionError("aggregate hasn't been called")
        aggregate_mode = len(self.by) == 0
        suffix = self.gen_name("_", ctx, self)
        var_row = f"row{suffix}"
        var_signature = f"signature{suffix}"
        var_signature_to_agg_data = f"signature_to_agg_data{suffix}"
        var_agg_data = f"agg_data{suffix}"
        var_agg_data_cls = f"AggData{suffix}"

        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        with function_ctx:

            signature_code_items = [
                by_.gen_code_and_update_ctx(var_row, ctx) for by_ in self.by
            ]
            replacements = {}

            # remembering code replacements for group by keys
            if len(signature_code_items) == 1:
                code_signature = signature_code_items[0]
                replacements[code_signature] = var_signature
            else:
                code_signature = f"({','.join(signature_code_items)},)"
                replacements.update(
                    {
                        code: f"{var_signature}[{index}]"
                        for index, (code, by_) in enumerate(
                            zip(signature_code_items, self.by)
                        )
                    }
                )

            # collecting inputs of reducers and reducers themselves
            with CodeGenerationOptionsCtx() as options:
                options.reducers_run_stage = "collecting_reducer_inputs"
                if "_reducer_inputs_info" not in ctx:
                    ctx["_reducer_inputs_info"] = []
                ctx["_reducer_inputs_info"].append(defaultdict(list))

                code_agg_result = self.agg_result.gen_code_and_update_ctx(
                    var_row, ctx
                )

                reducer_inputs_info = ctx["_reducer_inputs_info"].pop()

            def gen_agg_data_value(value_index):
                if aggregate_mode:
                    return f"{var_agg_data}_v{value_index}"
                else:
                    return f"{var_agg_data}.v{value_index}"

            expected_checksum = 0
            var_agg_data_values = []

            blocks: "t.List[RBT]" = []
            key_to_index: "t.Dict[t.Any, int]" = {}
            # reusing same reducers, remembering code replacements for reducers
            for (
                reducer_code_input,
                reducer_result_code,
            ), reducers in reducer_inputs_info.items():
                for reducer in reducers:
                    reduce_block_index = len(blocks)
                    checksum_flag = (
                        1 << reduce_block_index if self.aggregate_mode else 0
                    )
                    var_agg_data_value = gen_agg_data_value(reduce_block_index)
                    reduce_block = reducer.gen_reduce_code_block(
                        var_agg_data_value,
                        reducer_code_input,
                        checksum_flag,
                        ctx,
                    )

                    key = reduce_block.as_key()
                    if key in key_to_index:
                        reduce_block_index = key_to_index[key]
                    else:
                        key_to_index[key] = len(blocks)
                        blocks.append(reduce_block)
                        var_agg_data_values.append(var_agg_data_value)
                        expected_checksum |= checksum_flag

                    replacements[reducer_result_code] = gen_agg_data_value(
                        reduce_block_index
                    )

            reduce_blocks: ReduceBlocks = ReduceBlocks()
            for block in blocks:
                reduce_blocks.add_block(block)

            ctx.update({"defaultdict": defaultdict})

            if aggregate_mode:
                _ = " = ".join(var_agg_data_values)
                code_init_agg_vars = f"{_} = _none"
            else:
                ctx[var_agg_data_cls] = self._gen_agg_data_container(
                    var_agg_data_cls, reduce_blocks.number, ctx
                )

            # used by SortedArrayReducer
            ctx["ListSortedOnceWrapper"] = ListSortedOnceWrapper

            for code_from, code_to in replacements.items():
                code_agg_result = self.replace_word(
                    code_agg_result, code_from, code_to
                )

            if var_row in code_agg_result:
                raise ConversionException(
                    "something other than a group by key or a "
                    "reducer was used",
                    code_agg_result,
                )
            if self.aggregate_mode:
                code_agg_result = f"    return {code_agg_result}"
            else:
                if self.filter_conversion is None:
                    code_agg_result = (
                        f"    return [{code_agg_result} "
                        f"for {var_signature}, {var_agg_data} "
                        f"in {var_signature_to_agg_data}.items()]"
                    )
                else:
                    code_filtered_result = FilterConversion(
                        self.filter_conversion,
                        self.filter_cast,
                    ).gen_code_and_update_ctx("result_", ctx)
                    code_agg_result = (
                        f"    result_ = ({code_agg_result} "
                        f"for {var_signature}, {var_agg_data} "
                        f"in {var_signature_to_agg_data}.items())\n"
                        f"    filtered_result_ = {code_filtered_result}\n"
                    ) + (
                        "    yield from filtered_result_"
                        if self.filter_cast is None
                        else "    return filtered_result_"
                    )

            function_ctx.add_arg("data_", This())

            agg_template_kwargs = dict(
                code_args=function_ctx.get_def_all_args_code(),
                code_result=code_agg_result,
                var_row=var_row,
                expected_checksum=expected_checksum,
            )

            if self.aggregate_mode:
                converter_name = f"aggregate{suffix}"
                grouper_code = AGGREGATE_TEMPLATE.format(
                    converter_name=converter_name,
                    code_init_agg_vars=code_init_agg_vars,
                    var_expected_checksum=ReduceBlock.var_expected_checksum,
                    val_expected_checksum=expected_checksum,
                    var_checksum=ReduceBlock.var_checksum,
                    code_aggregate=reduce_blocks.gen_aggregate_code(
                        var_row=var_row,
                        var_checksum=ReduceBlock.var_checksum,
                        var_expected_checksum=expected_checksum,
                    ).to_string(
                        base_indent_level=1,
                    ),
                    **agg_template_kwargs,
                )
            else:
                converter_name = f"group_by{suffix}"
                grouper_code = GROUPER_TEMPLATE.format(
                    converter_name=converter_name,
                    var_signature_to_agg_data=var_signature_to_agg_data,
                    var_agg_data_cls=var_agg_data_cls,
                    var_agg_data=var_agg_data,
                    code_signature=code_signature,
                    code_group_by=reduce_blocks.gen_group_by_code(
                        var_row=var_row,
                        var_agg_data=var_agg_data,
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
    """Shortcut for ``GroupBy().aggregate(*args, **kwargs)``"""
    return GroupBy().aggregate(*args, **kwargs)


class ReducerDispatcher:
    pass


class SumReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = ({0} or 0)",)
    reduce = ("%(result)s = {prev_result} + ({0} or 0)",)
    default = NaiveConversion(0)
    unconditional_init = True


class FastSumReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = ({0} or 0)",)
    reduce = ("%(result)s = {prev_result} + {0}",)
    default = NaiveConversion(0)
    unconditional_init = True


class SumReducerDispatcher(ReducerDispatcher):
    def __call__(self, expression, *args, **kwargs):
        expression = ensure_conversion(expression)
        if expression.output_hints & expression.OutputHints.NOT_NONE:
            return FastSumReducer(expression, *args, **kwargs)
        return SumReducer(expression, *args, **kwargs)


class SumOrNoneReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = (
        "if {0} is None:",
        "    %(result)s = None",
        "elif %(result)s is not None:",
        "    %(result)s = {prev_result} + {0}",
    )
    default = NaiveConversion(None)
    unconditional_init = True


class MaxReducer(MultiStatementReducer):
    base_condition_code = "{0} is not None"
    prepare_first = ("%(result)s = {0}",)
    reduce = (
        "if {0} > %(result)s:",
        "    %(result)s = {0}",
    )
    default = NaiveConversion(None)
    unconditional_init = True


class MinReducer(MultiStatementReducer):
    base_condition_code = "{0} is not None"
    prepare_first = ("%(result)s = {0}",)
    reduce = (
        "if {0} < %(result)s:",
        "    %(result)s = {0}",
    )
    default = NaiveConversion(None)
    unconditional_init = True


class CountReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = 1",)
    reduce = ("%(result)s = {prev_result} + 1",)
    default = NaiveConversion(0)
    unconditional_init = True


class CountDistinctReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {{ {0} }}",)
    reduce = ("%(result)s.add({0})",)
    default = NaiveConversion(0)
    unconditional_init = True
    post_conversion = CallFunc(len, This())


class FirstReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = ()
    default = NaiveConversion(None)
    unconditional_init = True


class LastReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = ("%(result)s = {0}",)
    default = NaiveConversion(None)
    unconditional_init = True


class MaxRowReducer(MultiStatementReducer):
    """Reducer which finds an item with max value of the expression and returns
    this item"""

    base_condition_code = "{0} is not None"
    prepare_first = ("%(result)s = ({0}, %(input)s)",)
    reduce = (
        "if %(result)s[0] < {0}:",
        "    %(result)s = ({0}, %(input)s)",
    )
    default = NaiveConversion(None)
    post_conversion = GetItem(1)
    unconditional_init = True


class MinRowReducer(MaxRowReducer):
    reduce = (
        "if %(result)s[0] > {0}:",
        "    %(result)s = ({0}, %(input)s)",
    )


class ArrayReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = [{0}]",)
    reduce = ("%(result)s.append({0})",)
    default = NaiveConversion(None)
    unconditional_init = True


class ListSortedOnceWrapper:
    """Wraps a list, exposes append method only. Once the list is filled up, it
    is sorted (only once) in-place and is returned when get method called."""

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


class SortedArrayReducer(MultiStatementReducer):
    """Array reducer which sorts the list just once in the end"""

    reduce = ("%(result)s.append({0})",)
    default = NaiveConversion(None)
    unconditional_init = True

    def __init__(self, *args, key=None, reverse=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = self.ensure_conversion(key)
        self.reverse = self.ensure_conversion(reverse)

    def prepare_first(self, ctx):
        key_code = self.key.gen_code_and_update_ctx("{0}", ctx)
        reverse_code = self.reverse.gen_code_and_update_ctx("{0}", ctx)
        return (
            "%(result)s = ListSortedOnceWrapper("
            f"[{{0}}], {key_code}, {reverse_code})",
        )

    @property
    def post_conversion(self):
        return This().call_method("get")


class ArrayDistinctReducer(MultiStatementReducer):
    prepare_first = ("%(result)s = {{ {0}: None }}",)
    reduce = ("%(result)s[{0}] = None",)
    post_conversion = InlineExpr("list({0})").pass_args(This())
    default = NaiveConversion(None)
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
    reduce = ("%(result)s[{0}] = {1}",)
    default = NaiveConversion(None)
    unconditional_init = True


lock_default_dict_conversion = InlineExpr(
    'setattr({this_}, "default_factory", None) or {this_}'
).pass_args(this_=This())


class DictArrayReducer(BaseDictReducer):
    prepare_first = (
        "%(result)s = _d = defaultdict(list)",
        "_d[{0}].append({1})",
    )
    reduce = ("%(result)s[{0}].append({1})",)
    post_conversion = lock_default_dict_conversion
    default = NaiveConversion(None)
    unconditional_init = True


class DictArrayDistinctReducer(BaseDictReducer):
    """Dict reducer where dict values are lists of distinct values"""

    prepare_first = (
        "%(result)s = _d = defaultdict(dict)",
        "_d[{0}][{1}] = None",
    )
    reduce = ("%(result)s[{0}][{1}] = None",)
    post_conversion = InlineExpr(
        "{{k_: list(v_) for k_, v_ in {}.items()}}"
    ).pass_args(This())
    default = NaiveConversion(None)
    unconditional_init = True


class DictSumReducer(BaseDictReducer):
    prepare_first = (
        "%(result)s = _d = defaultdict(int)",
        "_d[{0}] = {1} or 0",
    )
    reduce = ("%(result)s[{0}] = {prev_result}[{0}] + ({1} or 0)",)
    post_conversion = lock_default_dict_conversion
    default = NaiveConversion(None)
    unconditional_init = True


class DictSumOrNoneReducer(BaseDictReducer):
    """Dict reducer where dict values are either numbers or None if there's
    been at least one None value within the group"""

    prepare_first = ("%(result)s = _d = defaultdict(int)", "_d[{0}] = {1}")
    reduce = (
        "if {1} is None:",
        "    %(result)s[{0}] = None",
        "elif %(result)s[{0}] is not None:",
        "    %(result)s[{0}] = {prev_result}[{0}] + {1}",
    )
    post_conversion = lock_default_dict_conversion
    default = NaiveConversion(None)
    unconditional_init = True


class DictMaxReducer(BaseDictReducer):
    """DictMax reducer which takes first positional item as keys and
    accumulates max value of second positional item"""

    base_condition_code = "{1} is not None"
    prepare_first = ("%(result)s = {{ {0}: {1} }}",)
    reduce = (
        "if {0} not in %(result)s or {1} > %(result)s[{0}]:",
        "    %(result)s[{0}] = {1}",
    )
    default = NaiveConversion(None)
    unconditional_init = True


class DictMinReducer(DictMaxReducer):
    reduce = (
        "if {0} not in %(result)s or {1} < %(result)s[{0}]:",
        "    %(result)s[{0}] = {1}",
    )


class DictCountReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: 1 }}",)
    reduce = (
        "if {0} not in %(result)s:",
        "    %(result)s[{0}] = 1",
        "else:",
        "    %(result)s[{0}] = {prev_result}[{0}] + 1",
    )
    default = NaiveConversion(None)
    unconditional_init = True


class DictCountDistinctReducer(BaseDictReducer):
    """Dict reducer where dict values are numbers of distinct values per
    group"""

    prepare_first = ("%(result)s = {{ {0}: {{ {1} }} }}",)
    reduce = (
        "if {0} not in %(result)s:",
        "    %(result)s[{0}] = {{ {1} }}",
        "else:",
        "    %(result)s[{0}].add({1})",
    )
    post_conversion = InlineExpr(
        "{{ k_: len(v_) for k_, v_ in {}.items() }}"
    ).pass_args(This())
    default = NaiveConversion(None)
    unconditional_init = True


class DictFirstReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: {1} }}",)
    reduce = ("if {0} not in %(result)s:", "    %(result)s[{0}] = {1}")
    default = NaiveConversion(None)
    unconditional_init = True


class DictLastReducer(BaseDictReducer):
    prepare_first = ("%(result)s = {{ {0}: {1} }}",)
    reduce = ("%(result)s[{0}] = {1}",)
    default = NaiveConversion(None)
    unconditional_init = True


class AverageReducerDispatcher(ReducerDispatcher):
    """Dispatcher which chooses between weighted and simple averages"""

    sum_reducer_dispatcher = SumReducerDispatcher()

    def __call__(
        self, value, weight=1, default=None, where=None
    ) -> "BaseConversion":
        """
        Calculates the arithmetic mean or weighted mean.
        """
        if isinstance(weight, (int, float, Decimal)) and weight == 1:
            return If(
                CountReducer(where=where),
                (
                    self.sum_reducer_dispatcher(value, where=where)
                    / CountReducer(where=where)
                ),
                default,
            )
        return If(
            self.sum_reducer_dispatcher(weight, where=where),
            (
                self.sum_reducer_dispatcher(value * weight, where=where)
                / self.sum_reducer_dispatcher(weight, where=where)
            ),
            default,
        )


class TopReducer(DictCountReducer):
    """
    Returns a list of the most frequent values.
    The resulting list is sorted in descending order of values frequency.
    """

    def __init__(self, k: int, key_conv, *args, **kwargs):
        if not isinstance(k, int):
            raise TypeError("K must be an integer.")

        if k < 1:
            raise ValueError("K must be a positive integer greater than 0.")

        self.k = k
        super().__init__(key_conv, 1, *args, **kwargs)

    @property
    def post_conversion(self):
        return InlineExpr(
            "[k for k,v in sorted((v,k) for k,v in {data}.items())[:-{k}:-1]]"
        ).pass_args(data=This(), k=self.k + 1)


class ModeReducer(DictCountReducer):
    def __init__(self, conv, *args, **kwargs):
        super().__init__(conv, conv, *args, **kwargs)

    post_conversion = InlineExpr(
        "sorted(((v,k) for k,v in {data}.items()))[-1][1]"
    ).pass_args(data=This())


class PercentileReducer(SortedArrayReducer):
    """Calculates percentile (floats from 0 to 100 inclusive)

    >>> c.ReduceFuncs.Percentile(95, c.item("amount"))
    >>> c.ReduceFuncs.Percentile(95, c.item("amount"), interpolation="lower")

    interpolation options:
      * "linear"
      * "lower"
      * "higher"
      * "midpoint"
      * "nearest"
    """

    interpolation_to_method: "t.Dict[str, t.Callable]" = {}

    def __init__(
        self, percentile: float, conv, *args, interpolation="linear", **kwargs
    ):
        """

        Args:
         * interpolation: one of
           #. "linear"
           #. "lower"
           #. "higher"
           #. "midpoint"
           #. "nearest"
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
    def percentile_linear(data, quantile):
        max_index = len(data) - 1
        index = max_index * quantile
        left_index = int(index)
        left_value = data[left_index]
        if left_index == max_index:
            return left_value

        return left_value + (data[left_index + 1] - left_value) * (
            index - left_index
        )

    @staticmethod
    def percentile_lower(data, quantile):
        return data[int((len(data) - 1) * quantile)]

    @staticmethod
    def percentile_higher(data, quantile):
        return data[ceil((len(data) - 1) * quantile)]

    @staticmethod
    def percentile_midpoint(data, quantile):
        index = (len(data) - 1) * quantile
        left_index = int(index)
        if left_index == index:
            return data[left_index]

        left_value = data[left_index]
        return left_value + (data[left_index + 1] - left_value) * 0.5

    @staticmethod
    def percentile_nearest(data, quantile):
        index = (len(data) - 1) * quantile
        left_index = int(index)
        if index - left_index > 0.5:
            return data[left_index + 1]
        else:
            return data[left_index]

    @property
    def post_conversion(self):
        return CallFunc(
            self.method, super().post_conversion, self.percentile * 0.01
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
    """Exposes the list of reduce functions"""

    # pylint: disable=invalid-name

    #: Calculates the sum, skips false values
    Sum = SumReducerDispatcher()
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

    #: Calculates the arithmetic mean or weighted mean.
    Average = AverageReducerDispatcher()
    #: Calculates the median value.
    Median = MedianReducer
    #: Calculates percentile: floats in [0, 100]
    Percentile = PercentileReducer
    #: Calculates the most common value.
    #: In case of multiple values, returns the last of them.
    Mode = ModeReducer
    #: Returns a list of the most frequent values.
    #: The resulting list is sorted in descending order of values frequency.
    TopK = TopReducer

    #: Aggregates values into array
    Array = ArrayReducer
    #: Aggregates distinct values into array, preserves order
    ArrayDistinct = ArrayDistinctReducer
    #: Aggregates values into array, sorting them in the end
    ArraySorted = SortedArrayReducer

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
