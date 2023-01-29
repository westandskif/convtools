"""
The main module exposing public API (via conversion object)
"""
from itertools import repeat

from .aggregations import (
    Aggregate,
    BaseReducer,
    GroupBy,
    Reduce,
    ReduceFuncs,
    ReducerDispatcher,
)
from .base import (
    And,
    ApplyFunc,
    BaseConversion,
    CallFunc,
    CodeGenerationOptionsCtx,
    ConversionException,
    ConverterOptionsCtx,
    Dict,
    DictComp,
    DropWhile,
    Eq,
    EscapedString,
    GeneratorComp,
    GetAttr,
    GetItem,
    If,
    IfMultiple,
    InlineExpr,
    InputArg,
    LabelConversion,
    List,
    ListComp,
    NaiveConversion,
    Not,
    OptionalCollectionItem,
    Or,
    Set,
    SetComp,
    SortConversion,
    TakeWhile,
    This,
    Tuple,
    TupleComp,
    ensure_conversion,
)
from .chunks import ChunkBy, ChunkByCondition
from .columns import ColumnRef
from .cumulative import Cumulative
from .joins import JoinConversion, _JoinConditions
from .mutations import Mutations


__all__ = ["conversion", "Conversion"]

_none = BaseConversion._none


class Conversion:
    """The object, which exposes public API

    .. code-block:: python

      from convtools import conversion as c

      convert = c.aggregate(
          c.ReduceFuncs.DictSum(
              c.item("name"),
              c.item("value")
          )
      ).gen_converter(debug=True)

      assert convert([
          {"name": "Bob", "value": 10},
          {"name": "Bob", "value": 7},
          {"name": "Ron", "value": 3},
      ]) == {'Bob': 17, 'Ron': 3}

    """

    ConversionException = ConversionException  # pylint: disable=invalid-name
    BaseConversion = BaseConversion  # pylint: disable=invalid-name
    OptionsCtx = ConverterOptionsCtx  # pylint: disable=invalid-name
    CodeGenerationOptionsCtx = (  # pylint: disable=invalid-name
        CodeGenerationOptionsCtx
    )

    ReduceFuncs = ReduceFuncs  # pylint: disable=invalid-name
    #: Shortcut to `Mutations`
    Mut = Mutations  # pylint: disable=invalid-name

    and_ = And
    or_ = Or
    not_ = Not
    if_ = If
    if_multiple = IfMultiple
    eq = Eq

    this = This

    #: Shortcut to :py:obj:`convtools.base.BaseConversion.and_then`
    and_then = This.and_then

    naive = NaiveConversion
    item = GetItem
    attr = GetAttr
    call_func = staticmethod(CallFunc)
    apply_func = staticmethod(ApplyFunc)
    __call__ = staticmethod(ensure_conversion)

    call = This.call
    apply = This.apply

    tap = This.tap
    iter_mut = This.iter_mut
    iter_windows = This.iter_windows
    iter_unique = This.iter_unique
    flatten = This.flatten

    filter = This.filter
    sort = SortConversion

    #: Shortcut to `InputArg`
    input_arg = InputArg
    label = LabelConversion
    inline_expr = InlineExpr
    escaped_string = EscapedString

    #: Shortcut to ``List``
    list = List
    tuple = Tuple
    set = Set
    dict = Dict
    optional = OptionalCollectionItem

    group_by = GroupBy
    aggregate = staticmethod(Aggregate)

    join = JoinConversion
    LEFT = _JoinConditions.LEFT
    RIGHT = _JoinConditions.RIGHT

    col = ColumnRef

    take_while = TakeWhile
    drop_while = DropWhile

    chunk_by = ChunkBy
    chunk_by_condition = ChunkByCondition
    CHUNK = ChunkByCondition.CHUNK

    breakpoint = This.breakpoint
    date_trunc = This.date_trunc
    datetime_trunc = This.datetime_trunc

    PREV = Cumulative.PREV
    cumulative = This.cumulative
    cumulative_reset = This.cumulative_reset

    date_parse = This.date_parse
    datetime_parse = This.datetime_parse

    def iter(self, item, *, where=None):
        return GeneratorComp(item, where, _none)

    generator_comp = iter

    def list_comp(self, item, *, where=None):
        return ListComp(item, where, _none)

    def tuple_comp(self, item, *, where=None):
        return TupleComp(item, where, _none)

    def set_comp(self, item, *, where=None):
        return SetComp(item, where, _none)

    def dict_comp(self, key, value, *, where=None):
        return DictComp(key, value, where, _none)

    def reduce(self, to_call_with_2_args, *args, **kwargs):
        if (
            isinstance(to_call_with_2_args, type)
            and issubclass(to_call_with_2_args, BaseReducer)
            or isinstance(to_call_with_2_args, ReducerDispatcher)
        ):
            return to_call_with_2_args(*args, **kwargs)
        return Reduce(to_call_with_2_args, *args, **kwargs)

    def zip(self, *args, **kwargs):
        """Conversion which calls :py:obj:`zip` on conversions.

        Args:
          args: conversions to zip - returns tuples
          kwargs: named conversions to zip - returns dicts

        """
        if args and kwargs:
            raise ValueError("pass either args or kwargs")
        if args:
            return CallFunc(zip, *args)

        return CallFunc(zip, *kwargs.values()).iter(
            {name: self.item(index) for index, name in enumerate(kwargs)}
        )

    def repeat(self, obj, times=None):
        """shortcut to call :py:obj:`itertools.repeat`"""
        args = () if times is None else (times,)
        return CallFunc(repeat, obj, *args)

    def min(self, arg, *args):
        """c.call_func(min, ...) shortcut"""
        return CallFunc(min, arg, *args)

    def max(self, arg, *args):
        """c.call_func(max, ...) shortcut"""
        return CallFunc(max, arg, *args)


conversion = Conversion()
