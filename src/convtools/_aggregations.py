"""Define aggregations with various reduce functions."""
import typing as t
import warnings
from collections import defaultdict
from decimal import Decimal
from itertools import chain
from math import ceil

from ._base import (
    BaseConversion,
    CallFunc,
    ConversionException,
    ConverterOptionsCtx,
    EscapedString,
    GeneratorItem,
    GetItem,
    If,
    InlineExpr,
    LazyEscapedString,
    List,
    ListComp,
    NaiveConversion,
    Namespace,
    NamespaceCtx,
    This,
    Tuple,
    _None,
    _none,
)
from ._heuristics import Weights
from ._utils import Code


class ReduceCode:
    """Merge and store code of reducers."""

    def __init__(self):
        self.value_to_name: "t.Dict[str, str]" = {}
        self.condition_to_child: "t.Dict[str, ReduceCode]" = {}
        self.key_to_reduce_lines = {}

    def add_assignment(self, value):
        if value in self.value_to_name:
            return self.value_to_name[value]

        new_name = self.value_to_name[value] = f"_r{len(self.value_to_name)}_"
        return new_name

    def use_expression(self, value):
        if value in self.value_to_name:
            return self.value_to_name[value]
        return value

    def add_condition(self, condition):
        if condition in self.condition_to_child:
            return self.condition_to_child[condition]
        reduce_code = self.condition_to_child[condition] = ReduceCode()
        return reduce_code

    def add_reduce_lines(
        self, var_agg_data_value, prepare_first_lines, reduce_lines
    ) -> str:
        key = "".join(
            line.replace(var_agg_data_value, "")
            for line in chain(prepare_first_lines, reduce_lines)
        )
        if key in self.key_to_reduce_lines:
            return self.key_to_reduce_lines[key][0]

        self.key_to_reduce_lines[key] = (
            var_agg_data_value,
            prepare_first_lines,
            reduce_lines,
        )
        return var_agg_data_value


class ReduceManager:
    """Build group by / aggregate code."""

    __slots__ = [
        "var_row",
        "var_agg_data",
        "aggregate_mode",
        "number",
        "reduce_code",
        "used_indexes",
    ]

    def __init__(self, var_row, var_agg_data, aggregate_mode):
        self.var_row = var_row
        self.var_agg_data = var_agg_data
        self.aggregate_mode = aggregate_mode
        self.number = 0
        self.reduce_code = ReduceCode()
        self.used_indexes = []

    def gen_group_by_code(self, var_signature_to_agg_data, code_signature):
        code = Code()
        code.add_line(f"for {self.var_row} in data_:", 1)
        code.add_line(
            f"{self.var_agg_data} = {var_signature_to_agg_data}[{code_signature}]",
            0,
        )
        self.add_group_by_code(code, self.reduce_code)
        return code

    def gen_aggregate_code(self):
        var_init_checksum = "checksum_"
        code = Code()
        code.add_line(f"{var_init_checksum} = 0", 0)
        code.add_line("it_ = iter(data_)", 0)
        code.add_line(f"for {self.var_row} in it_:", 1)
        checksum = self.add_group_by_code(
            code, self.reduce_code, var_init_checksum=var_init_checksum
        )
        code.add_line(f"if {var_init_checksum} == {checksum}:", 1)
        if ConverterOptionsCtx.get_option_value("debug"):
            code.add_line(
                "globals()['__BROKEN_EARLY__'] = True  # DEBUG ONLY",
                0,
            )
        code.add_line("break", -2)

        ref = code.get_ref()
        code.add_line(f"for {self.var_row} in it_:", 1)
        if self.add_aggregate_stage2_code(code, self.reduce_code) == 0:
            code.cut_to_ref(ref)
        return code

    def fmt_agg_data_value(self, index):
        return (
            f"{self.var_agg_data}_v{index}"
            if self.aggregate_mode
            else f"{self.var_agg_data}.v{index}"
        )

    def gen_agg_data_value(self):
        index = self.number
        self.number += 1
        return index, self.fmt_agg_data_value(index)

    def gen_group_by_data_container(self, grouper, container_name, ctx):
        attrs = [f"v{i}" for i in self.used_indexes]

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
        return ctx[
            grouper.compile_converter(container_name, code.to_string(0), ctx)
        ]

    def gen_init_aggregate_vars(self):
        vars_code = " = ".join(
            [self.fmt_agg_data_value(index) for index in self.used_indexes]
        )
        return f"{vars_code} = _none"

    def add_group_by_code(
        self,
        code: Code,
        reduce_code: ReduceCode,
        delegated_conditions=(),
        var_init_checksum=None,
    ):
        checksum = 0
        initial_indent_level = code.indent_level

        if delegated_conditions and (
            reduce_code.value_to_name
            or reduce_code.key_to_reduce_lines
            or len(reduce_code.condition_to_child) > 1
        ):
            code.add_line(f"if {' and '.join(delegated_conditions)}:", 1)
            delegated_conditions = ()

        for value, name in reduce_code.value_to_name.items():
            code.add_line(f"{name} = {value}", 0)

        if reduce_code.key_to_reduce_lines:
            var_agg_data_value = next(
                iter(reduce_code.key_to_reduce_lines.values())
            )[0]
            code.add_line(f"if {var_agg_data_value} is _none:", 1)

            if var_init_checksum:
                code.add_line(f"{var_init_checksum} += 1", 0)
            checksum += 1

            for item in reduce_code.key_to_reduce_lines.values():
                for line in item[1]:  # prepare_first_lines
                    code.add_line(line, 0)

            code.incr_indent_level(-1)
            code.add_line("else:", 1)

            lines_before = len(code.lines_info)
            for item in reduce_code.key_to_reduce_lines.values():
                for line in item[2]:  # reduce_lines
                    code.add_line(line, 0)
            if lines_before == len(code.lines_info):
                code.add_line("pass", 0)

            code.incr_indent_level(-1)

        for condition, child in reduce_code.condition_to_child.items():
            checksum += self.add_group_by_code(
                code,
                child,
                delegated_conditions=(*delegated_conditions, condition),
                var_init_checksum=var_init_checksum,
            )

        code.indent_level = initial_indent_level
        return checksum

    def add_aggregate_stage2_code(
        self, code: Code, reduce_code: ReduceCode, delegated_conditions=()
    ):
        initial_indent_level = code.indent_level
        checksum = 0
        add_pass_if_line_number = -1

        if delegated_conditions and (
            reduce_code.value_to_name
            or reduce_code.key_to_reduce_lines
            or len(reduce_code.condition_to_child) > 1
        ):
            code.add_line(f"if {' and '.join(delegated_conditions)}:", 1)
            add_pass_if_line_number = len(code.lines_info)
            delegated_conditions = ()

        for value, name in reduce_code.value_to_name.items():
            code.add_line(f"{name} = {value}", 0)

        if reduce_code.key_to_reduce_lines:
            for item in reduce_code.key_to_reduce_lines.values():
                if item[2]:
                    checksum += 1
                for line in item[2]:  # reduce_lines
                    code.add_line(line, 0)

        for condition, child in reduce_code.condition_to_child.items():
            checksum += self.add_aggregate_stage2_code(
                code,
                child,
                delegated_conditions=(*delegated_conditions, condition),
            )

        if add_pass_if_line_number == len(code.lines_info):
            code.add_line("pass", -1)

        code.indent_level = initial_indent_level
        return checksum


class BaseReducer(BaseConversion):
    """Base reduce operation to be used during the aggregation."""

    _expressions: t.Sequence[BaseConversion]

    default: t.Union[_None, BaseConversion] = _none
    initial: t.Union[_None, BaseConversion] = _none
    internals_are_public: bool
    values_use_times: t.Tuple[int, ...]
    works_with_not_none_only: t.Tuple[int, ...]
    prepare_first_lines: t.Union[
        t.Tuple[str, ...], t.Callable[[], t.Tuple[str, ...]]
    ]
    reduce_lines: t.Union[t.Tuple[str, ...], t.Callable[[], t.Tuple[str, ...]]]
    where: t.Union[_None, BaseConversion]

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
        post_conversion = self.get_option("post_conversion", None, None)
        self.conversion = self.ensure_conversion(
            If(
                This.is_(EscapedString("_none")),
                self.default,
                (post_conversion if post_conversion is not None else This),
            )
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

    def get_option(self, name, ctx, default=_none):
        if default is _none:
            option_value = getattr(self, name)
        else:
            option_value = getattr(self, name, default)
        if callable(option_value):
            return option_value(ctx)
        return option_value

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        reduce_manager: ReduceManager = ctx["current_reduce_manager"][-1]
        index, proposed_code_input = reduce_manager.gen_agg_data_value()
        new_code_input = self.update_reduce_code(
            reduce_manager.reduce_code,
            proposed_code_input,
            reduce_manager.var_row,
            code_input,
            ctx,
        )
        if proposed_code_input == new_code_input:
            reduce_manager.used_indexes.append(index)

        return self.conversion.gen_code_and_update_ctx(new_code_input, ctx)

    def update_reduce_code(
        self,
        reduce_code: ReduceCode,
        var_agg_data_value,
        var_row,
        reducer_code_input,
        ctx,
    ):
        if not isinstance(self.where, _None):
            reduce_code = reduce_code.add_condition(
                self.where.gen_code_and_update_ctx(var_row, ctx)
            )

        kwargs = {
            "result": var_agg_data_value,
            "row": var_row,
            # "value0", "value1", etc.
        }
        works_with_not_none_only = self.get_option(
            "works_with_not_none_only", ctx
        )
        values_use_times = self.get_option("values_use_times", ctx)

        prev_reduce_code = reduce_code
        for index, expression in enumerate(self.expressions):
            expression_code = expression.gen_code_and_update_ctx(
                reducer_code_input, ctx
            )
            none_check_needed = works_with_not_none_only[
                index
            ] and not expression.has_hint(BaseConversion.OutputHints.NOT_NONE)
            if (
                none_check_needed + values_use_times[index] > 1
                and expression is not This
            ):
                prev_reduce_code.add_assignment(expression_code)

            expression_code = prev_reduce_code.use_expression(expression_code)

            if none_check_needed:
                reduce_code = reduce_code.add_condition(
                    f"{expression_code} is not None"
                )

            kwargs[f"value{index}"] = expression_code

        reduce_lines = self.get_option("reduce_lines", ctx)

        if not isinstance(self.initial, _None) and self.internals_are_public:
            prepare_first_lines = (
                f"%(result)s = {self.initial.gen_code_and_update_ctx(var_row, ctx)}",
                *reduce_lines,
            )
        else:
            prepare_first_lines = self.get_option("prepare_first_lines", ctx)

        new_agg_data_value = reduce_code.add_reduce_lines(
            var_agg_data_value,
            tuple(line % kwargs for line in prepare_first_lines),
            tuple(line % kwargs for line in reduce_lines),
        )
        return new_agg_data_value


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
                isinstance(expr, (Tuple, List))
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
    values_use_times = (1,)
    works_with_not_none_only = (False,)

    def prepare_first_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s = %(value0)s",)
        return ("%(result)s = %(value0)s or 0",)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s += %(value0)s",)
        return ("%(result)s += %(value0)s or 0",)


class SumOrNoneReducer(SingleExpressionReducer):
    """Take a sum. If at least one None is met, the result is None."""

    default = NaiveConversion(None)
    internals_are_public = True
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)

    def values_use_times(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (1,)
        return (2,)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s += %(value0)s",)
        return (
            "if %(value0)s is None:",
            "    %(result)s = None",
            "elif %(result)s is not None:",
            "    %(result)s += %(value0)s",
        )


class MaxReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = True
    values_use_times = (2,)
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = %(value0)s",)
    reduce_lines = (
        "if %(result)s < %(value0)s:",
        "    %(result)s = %(value0)s",
    )


class MinReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = True
    values_use_times = (2,)
    works_with_not_none_only = (True,)
    prepare_first_lines = ("%(result)s = %(value0)s",)
    reduce_lines = (
        "if %(result)s > %(value0)s:",
        "    %(result)s = %(value0)s",
    )


class CountReducer(OptionalExpressionReducer):
    """Counts objects.

    It accepts either zero or one expression as an argument:
      - if zero expressions passed: counts number of rows
      - one expression: counts not None values of the evaluated expression
    """

    default = NaiveConversion(0)
    internals_are_public = True
    values_use_times = (0,)
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
    values_use_times = (1,)
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = {%(value0)s}",)
    reduce_lines = ("%(result)s.add(%(value0)s)",)
    post_conversion = CallFunc(len, This)


class FirstReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (1,)
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)
    reduce_lines = ()


class LastReducer(SingleExpressionReducer):
    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (1,)
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)
    reduce_lines = ("%(result)s = %(value0)s",)


class MaxRowReducer(SingleExpressionReducer):
    """Return a row with a max value of an argument."""

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (2,)
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
    values_use_times = (2,)
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
    default = NaiveConversion(None)
    internals_are_public = True
    values_use_times = (1,)
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = [%(value0)s]",)
    reduce_lines = ("%(result)s.append(%(value0)s)",)


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


class SortedArrayReducer(SingleExpressionReducer):
    """Reduce values to a sorted array."""

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (1,)
    works_with_not_none_only = (False,)
    reduce_lines = ("%(result)s.append(%(value0)s)",)
    post_conversion = This.call_method("get")

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
    values_use_times = (1,)
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = { %(value0)s: None }",)
    reduce_lines = ("%(result)s[%(value0)s] = None",)
    post_conversion = This.as_type(list)


class DictReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument.
    Values: defined by the second argument, reduced with Last.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (1, 1)
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
    values_use_times = (1, 1)
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
    values_use_times = (1, 1)
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
    values_use_times = (1, 1)
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

    def values_use_times(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (1, 1)
        return (2, 2)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return ("%(result)s[%(value0)s] += %(value1)s",)
        return (
            "if %(value1)s is None:",
            "    %(result)s[%(value0)s] = None",
            "elif %(result)s[%(value0)s] is not None:",
            "    %(result)s[%(value0)s] += %(value1)s",
        )


class DictMaxReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with Max.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (1, 1)
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (False, False)
        return (False, True)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        return (
            "if %(value0)s not in %(result)s or %(value1)s > %(result)s[%(value0)s]:",
            "    %(result)s[%(value0)s] = %(value1)s",
        )


class DictMinReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with Min.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (1, 1)
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        if self.expressions[1].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (False, False)
        return (False, True)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        return (
            "if %(value0)s not in %(result)s or %(value1)s < %(result)s[%(value0)s]:",
            "    %(result)s[%(value0)s] = %(value1)s",
        )


class DictCountReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument (optional), reduced with Count.
       * counts rows if no 2nd arg is passed
       * counts non None values if 2nd arg is passed
    """

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (2, 0)
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
                isinstance(expr, (Tuple, List))
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
    values_use_times = (2, 1)
    works_with_not_none_only = (False, False)
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


class DictFirstReducer(BaseDictReducer):
    """Reduce two values to a dict.

    Keys: defined by the first argument
    Values: defined by the second argument, reduced with First.
    """

    default = NaiveConversion(None)
    internals_are_public = False
    values_use_times = (2, 1)
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
    values_use_times = (1, 1)
    works_with_not_none_only = (False, False)
    prepare_first_lines = ("%(result)s = { %(value0)s: %(value1)s }",)
    reduce_lines = ("%(result)s[%(value0)s] = %(value1)s",)


class ReducerDispatcher:
    def __call__(self, *args, **kwargs) -> "BaseConversion":
        raise NotImplementedError


class AverageReducerDispatcher(ReducerDispatcher):
    """Calculates weighted average (default weight is 0)."""

    def __call__(
        self, value, weight=1, default=None, where=None
    ) -> "BaseConversion":
        if isinstance(weight, (int, float, Decimal)) and weight == 1:
            return If(
                CountReducer(where=where),
                (SumReducer(value, where=where) / CountReducer(where=where)),
                default,
            )
        return If(
            SumReducer(weight, where=where),
            (
                SumReducer(value * weight, where=where)
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
        super().__init__(key_conv, *args, **kwargs)

    def post_conversion(self, ctx):  # pylint: disable=unused-argument
        return InlineExpr(
            "[key for key, value in sorted((v, k) for k, v in {data}.items())[:-{k}:-1]]"
        ).pass_args(data=This, k=self.k + 1)


class ModeReducer(DictCountReducer):
    def __init__(self, conv, *args, **kwargs):
        super().__init__(conv, conv, *args, **kwargs)

    # TODO: check how MaxRow performs here
    post_conversion = InlineExpr(
        "sorted({data}.items(), key=lambda x: x[1])[-1][0]"
    ).pass_args(data=This)


class PercentileReducer(SortedArrayReducer):
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

    interpolation_to_method: t.ClassVar[t.Dict[str, t.Callable]] = {}

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

    def post_conversion(self, ctx):  # pylint: disable=unused-argument
        return CallFunc(
            self.method,
            This.call_method("get"),
            self.percentile * 0.01,
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
        self, reducer: t.Union[dict, list, set, tuple, BaseConversion]
    ) -> "Grouper":
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

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        ctx["defaultdict"] = defaultdict
        ctx["ListSortedOnceWrapper"] = ListSortedOnceWrapper

        suffix = self.gen_random_name("_", ctx)
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
                ctx[
                    var_agg_data_cls
                ] = reduce_manager.gen_group_by_data_container(
                    self, var_agg_data_cls, ctx
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
        to_call_with_2_args: t.Union[t.Callable, InlineExpr],
        *expressions: t.Tuple[t.Any, ...],
        initial: t.Union[_None, t.Callable, InlineExpr, t.Any],
        default: t.Union[_None, t.Callable, t.Any] = _none,
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

    def values_use_times(self, ctx):  # pylint: disable=unused-argument
        return (1,) * len(self.expressions)

    def works_with_not_none_only(self, ctx):  # pylint: disable=unused-argument
        return (False,) * len(self.expressions)

    def reduce_lines(self, ctx):
        _ = self.to_call_with_2_args.call_like(
            EscapedString("%(result)s"),
            *self.expressions,
        ).gen_code_and_update_ctx("%(row)s", ctx)
        return (f"%(result)s = {_}",)
