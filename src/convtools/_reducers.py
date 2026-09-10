"""Built-in reducers and the Reduce primitive."""

import warnings
from collections import deque
from decimal import Decimal
from math import ceil
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Sequence,
    Tuple,
    Union,
    cast,
)

from ._base import (
    BaseConversion,
    CallFunc,
    DictComp,
    EscapedString,
    GetItem,
    If,
    InlineExpr,
    List_,
    ListComp,
    NaiveConversion,
    This,
    Tuple_,
    _None,
    _none,
)
from ._reducer_sharing import ReducerRecord

if TYPE_CHECKING:
    from ._aggregations import ReduceManager


class BaseReducer(BaseConversion):
    """Base reduce operation to be used during the aggregation.

    A callable ``initial`` is called per group and must return a new object
    each time (like ``defaultdict``'s factory); the reducer may then
    accumulate in place.
    """

    _expressions: Sequence[BaseConversion]

    default: Union[_None, BaseConversion] = _none
    initial: Union[_None, BaseConversion] = _none
    owns_accumulator = False
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
                self.owns_accumulator = True

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
        reduce_manager: "ReduceManager" = ctx["current_reduce_manager"][-1]

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
        not_none = self.expressions[0].has_hint(
            BaseConversion.OutputHints.NOT_NONE
        )
        if self.owns_accumulator:
            if not_none:
                return ("%(result)s += %(value0)s",)
            return ("%(result)s += %(value0)s or 0",)
        if not_none:
            return ("%(result)s = %(result)s + %(value0)s",)
        return ("%(result)s = %(result)s + (%(value0)s or 0)",)


class SumOrNoneReducer(SingleExpressionReducer):
    """Take a sum. If at least one None is met, the result is None."""

    default = NaiveConversion(None)
    internals_are_public = True
    works_with_not_none_only = (False,)
    prepare_first_lines = ("%(result)s = %(value0)s",)

    def reduce_lines(self, ctx):  # pylint: disable=unused-argument
        if self.owns_accumulator:
            add = "%(result)s += %(value0)s"
        else:
            add = "%(result)s = %(result)s + %(value0)s"
        if self.expressions[0].has_hint(BaseConversion.OutputHints.NOT_NONE):
            return (add,)
        return (
            "if %(value0)s is None:",
            "    %(result)s = None",
            "elif %(result)s is not None:",
            f"    {add}",
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
            return (
                "%(result)s[%(value0)s] = %(result)s[%(value0)s] + %(value1)s",
            )
        return (
            "%(result)s[%(value0)s] = %(result)s[%(value0)s]"
            " + (%(value1)s or 0)",
        )


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
            return (
                "%(result)s[%(value0)s] = %(result)s[%(value0)s] + %(value1)s",
            )
        return (
            "if %(value1)s is None:",
            "    %(result)s[%(value0)s] = None",
            "elif %(result)s[%(value0)s] is not None:",
            "    %(result)s[%(value0)s] = %(result)s[%(value0)s] + %(value1)s",
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


class WeightedAverageReducer(BaseDictReducer):
    """Weighted mean: ``[sum(value * weight), sum(weight)]``."""

    default = NaiveConversion(None)
    internals_are_public = False
    works_with_not_none_only = (True, True)
    prepare_first_lines = (
        "%(result)s = [%(value0)s * %(value1)s, %(value1)s]",
    )
    reduce_lines = (
        "%(result)s[0] = %(result)s[0] + %(value0)s * %(value1)s",
        "%(result)s[1] = %(result)s[1] + %(value1)s",
    )

    def post_conversion(self, ctx):  # pylint: disable=unused-argument
        return If(This.item(1), This.item(0) / This.item(1), None)


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
        reducer = WeightedAverageReducer(value, weight, where=where)
        if default is not None:
            return If(reducer.is_not(None), reducer, default)
        return reducer


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
        return data[round(index)]

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

    #: Sums values, treating `None` (and other falsy values) as `0`;
    #: default is `0`. Summing lists/tuples uses `result = result +
    #: value` (never mutates the first row's object) and is O(n^2);
    #: pass `initial=list` for linear in-place list accumulation
    #: (`Sum` still treats empty lists as `0`, which then raises).
    Sum = SumReducer
    #: Sums values; any `None` makes the result `None`. Summing
    #: lists/tuples uses `result = result + value` (never mutates the
    #: first row's object) and is O(n^2); pass `initial=list` for
    #: linear in-place list accumulation.
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
    #: mean; both forms skip rows where value (or weight) is `None`.
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
    #: Builds a dict whose values are sums per key, treating `None` as
    #: `0`. Summing lists/tuples per key uses `result[k] = result[k] +
    #: value` and is O(n^2); `initial=` is ignored (use `DictArray` to
    #: collect lists per key).
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
