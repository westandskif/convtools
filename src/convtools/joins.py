"""
This module brings join functionality to the library
"""
import typing
from itertools import chain

from .aggregations import Aggregate, Reduce, ReduceFuncs
from .base import (
    And,
    BaseConversion,
    Call,
    CallFunc,
    ConversionWrapper,
    Eq,
    GeneratorComp,
    GetItem,
    If,
    InlineExpr,
    InputArg,
    LabelConversion,
    NaiveConversion,
    NamedConversion,
    Tuple,
)


class JoinException(Exception):
    pass


class _JoinConditions:
    """A helper object to analyze join conditions"""

    LEFT = NamedConversion("left_row", GetItem())
    RIGHT = NamedConversion("right_row", GetItem())
    LEFT_NAME = LEFT.name
    RIGHT_NAME = RIGHT.name
    _ANY = {LEFT_NAME, RIGHT_NAME}

    def __init__(self, how="inner"):
        self.inner_loop_conditions = []
        self.left_collection_filters = []
        self.left_row_filters = []
        self.left_row_hashers = []
        self.right_collection_filters = []
        self.right_row_filters = []
        self.right_row_hashers = []
        self.pre_filter = []
        if how == "full":
            how = "outer"

        self.inner_join = how == "inner"
        self.left_join = how in {"left", "outer"}
        self.right_join = how in {"right", "outer"}
        self.outer_join = how == "outer"
        if not self.inner_join and not self.left_join and not self.right_join:
            raise AssertionError

    def _add_left_filter(self, filter_conv):
        if self.left_join:
            self.left_row_filters.append(filter_conv)
        else:
            self.left_collection_filters.append(filter_conv)

    def _add_right_filter(self, filter_conv):
        if self.right_join:
            self.right_row_filters.append(filter_conv)
        else:
            self.right_collection_filters.append(filter_conv)

    @classmethod
    def from_condition(cls, condition, **kwargs):
        join_conditions = cls(**kwargs)
        if condition is True:
            return join_conditions

        if isinstance(condition, Eq):
            join_conditions.consume_eq(condition)
        elif isinstance(condition, And):
            join_conditions.consume_and(condition)
        else:
            join_conditions.consume_other(condition)

        return join_conditions

    @classmethod
    def _get_join_deps(cls, conv) -> typing.Set[str]:
        return {
            dep.name
            for dep in conv.get_dependencies(types=NamedConversion)
            if dep.name in cls._ANY
        }

    def consume_eq(self, eq_conversion: Eq):
        if not isinstance(eq_conversion, Eq):
            raise AssertionError

        if len(eq_conversion.args) != 2:
            return self.inner_loop_conditions.append(eq_conversion)

        first_args, second_args = map(self._get_join_deps, eq_conversion.args)
        if len(first_args) > 1 or len(second_args) > 1:
            return self.inner_loop_conditions.append(eq_conversion)

        if len(first_args.union(second_args)) == 2:
            if self.LEFT_NAME in first_args:
                left_idx, right_idx = 0, 1
            else:
                left_idx, right_idx = 1, 0
            self.left_row_hashers.append(eq_conversion.args[left_idx])
            self.right_row_hashers.append(eq_conversion.args[right_idx])
        else:
            all_args = first_args.union(second_args)
            if self.LEFT_NAME in all_args:
                self._add_left_filter(eq_conversion)
            elif self.RIGHT_NAME in all_args:
                self._add_right_filter(eq_conversion)
            else:
                self.pre_filter.append(eq_conversion)

    def consume_other(self, other: BaseConversion):
        deps = self._get_join_deps(other)
        deps_length = len(deps)
        if deps_length > 1:
            self.inner_loop_conditions.append(other)
        elif deps_length == 1:
            if self.LEFT_NAME in deps:
                self._add_left_filter(other)
            else:
                self._add_right_filter(other)
        else:
            self.pre_filter.append(other)

    def consume_and(self, and_conversion: And):
        if not isinstance(and_conversion, And):
            raise AssertionError

        for arg in and_conversion.args:
            if isinstance(arg, Eq):
                self.consume_eq(arg)
            elif isinstance(arg, And):
                self.consume_and(arg)
            else:
                self.consume_other(arg)


def join(
    left_conversion: BaseConversion,
    right_conversion: BaseConversion,
    condition: BaseConversion,
    how="inner",
) -> Call:
    """Generates conversion which joins left_conversion and right_conversion
    using condition. The result is a generator of joined pairs

    Args:
      left_conversion (BaseConversion): left collection to join
      right_conversion (BaseConversion): right collection to join
      condition (BaseConversion): join condition. If is True, results in cross
        join
      how (str): one of the following: ``"inner"``, ``"left"``, ``"right"``,
        ``"outer"``

    Returns:
      BaseConversion: which processes the input and returns generator of
      joined pairs"""
    left_right_swapped = False
    if how == "right":
        left_right_swapped = True
        how = "left"
        left_conversion, right_conversion = right_conversion, left_conversion

    join_conditions = _JoinConditions.from_condition(condition, how=how)
    if condition is True:
        condition = NaiveConversion(True)

    right_collection: BaseConversion = InputArg("right")
    right_collection_filters = (
        join_conditions.left_collection_filters
        if left_right_swapped
        else join_conditions.right_collection_filters
    )
    if right_collection_filters:
        right_collection = right_collection.pipe(
            GeneratorComp(GetItem()).filter(
                And(
                    right_collection_filters[0],
                    right_collection_filters[1],
                    *right_collection_filters[2:],
                )
                if len(right_collection_filters) > 1
                else right_collection_filters[0]
            )
        )
    if join_conditions.outer_join:
        right_collection = right_collection.as_type(list)
    right_collection = right_collection.add_label("right_collection")

    left_collection: BaseConversion = InputArg("left")
    left_collection_filters = (
        join_conditions.right_collection_filters
        if left_right_swapped
        else join_conditions.left_collection_filters
    )
    if left_collection_filters:
        left_collection = left_collection.pipe(
            GeneratorComp(GetItem()).filter(
                And(
                    left_collection_filters[0],
                    left_collection_filters[1],
                    *left_collection_filters[2:],
                )
                if len(left_collection_filters) > 1
                else left_collection_filters[0]
            )
        )

    inner_loop_condition: typing.Optional[ConversionWrapper] = None
    resulting_inner_loop_conditions = list(
        chain(
            join_conditions.left_row_filters,
            join_conditions.right_row_filters,
            join_conditions.inner_loop_conditions,
        )
    )
    if resulting_inner_loop_conditions:
        if len(resulting_inner_loop_conditions) > 1:
            condition_ = And(
                resulting_inner_loop_conditions[0],
                resulting_inner_loop_conditions[1],
                *resulting_inner_loop_conditions[2:],
            )
        else:
            condition_ = resulting_inner_loop_conditions[0]
        inner_loop_condition = ConversionWrapper(
            condition_,
            name_to_code_input=(
                {
                    _JoinConditions.LEFT_NAME: "right_item",
                    _JoinConditions.RIGHT_NAME: "left_item",
                }
                if left_right_swapped
                else {
                    _JoinConditions.LEFT_NAME: "left_item",
                    _JoinConditions.RIGHT_NAME: "right_item",
                }
            ),
        )

    if join_conditions.left_row_hashers:
        left_row_conv_to_hash = (
            Tuple(*join_conditions.left_row_hashers)
            if len(join_conditions.left_row_hashers) > 1
            else join_conditions.left_row_hashers[0]
        )
        right_row_conv_to_hash = (
            Tuple(*join_conditions.right_row_hashers)
            if len(join_conditions.right_row_hashers) > 1
            else join_conditions.right_row_hashers[0]
        )

        right_collection_conversion = right_collection.pipe(
            Aggregate(
                Reduce(
                    ReduceFuncs.DictArray,
                    (right_row_conv_to_hash, GetItem()),
                    default={},
                )
            ),
            label_output="hash_to_items",
        )
        right_items = (
            InlineExpr("left_item").pipe(left_row_conv_to_hash)
        ).pipe(
            If(
                GetItem().in_(LabelConversion("hash_to_items")),
                LabelConversion("hash_to_items").item(GetItem()),
                NaiveConversion(()),
            )
        )
    else:
        right_collection_conversion = right_collection
        right_items = LabelConversion("right_collection")

    if join_conditions.inner_join:
        conv = right_collection_conversion.pipe(
            left_collection.pipe(
                InlineExpr(
                    "((left_item, right_item)"
                    + " for left_item in {left_items}"
                    + " for right_item in {right_items}"
                    + (" if {condition}" if inner_loop_condition else "")
                    + ")"
                ).pass_args(
                    left_items=GetItem(),
                    right_items=right_items,
                    condition=inner_loop_condition,
                ),
            ),
        )
    else:
        if left_right_swapped:

            def _left_joiner_swapped(left_to_right_ones_gen):
                none_ = object()
                for left_item, right_ones in left_to_right_ones_gen:
                    right_item = next(right_ones, none_)
                    if right_item is none_:
                        yield None, left_item
                    else:
                        yield right_item, left_item
                        for right_item in right_ones:
                            yield right_item, left_item

            left_joiner = _left_joiner_swapped
        else:

            def _left_joiner(left_to_right_ones_gen):
                none_ = object()
                for left_item, right_ones in left_to_right_ones_gen:
                    right_item = next(right_ones, none_)
                    if right_item is none_:
                        yield left_item, None
                    else:
                        yield left_item, right_item
                        for right_item in right_ones:
                            yield left_item, right_item

            left_joiner = _left_joiner
        conv = right_collection_conversion.pipe(
            left_collection.pipe(
                InlineExpr(
                    "(left_item, (right_item for right_item in {right_items}"
                    + (" if {condition}" if inner_loop_condition else "")
                    + "))"
                    + " for left_item in {left_items}"
                ).pass_args(
                    left_items=GetItem(),
                    right_items=right_items,
                    condition=inner_loop_condition,
                ),
            )
        ).pipe(left_joiner)

    if join_conditions.outer_join:

        def _add_right_part(left_join_gen, get_by_label_):
            yielded_right_ids = set()
            for left_right in left_join_gen:
                yielded_right_ids.add(id(left_right[1]))
                yield left_right

            yield from (
                (None, right)
                for right in get_by_label_("right_collection")
                if id(right) not in yielded_right_ids
            )

        conv = conv.pipe(
            _add_right_part,
            get_by_label_=InlineExpr("get_by_label_"),
        )
    if join_conditions.pre_filter:
        conv = If(
            (
                And(
                    join_conditions.pre_filter[0],
                    join_conditions.pre_filter[1],
                    *join_conditions.pre_filter[2:],
                )
                if len(join_conditions.pre_filter) > 1
                else join_conditions.pre_filter[0]
            ),
            conv,
            [],
        )
    converter = conv.gen_converter(
        debug=True,
        signature="left, right{}".format(
            condition.get_args_def_code(as_kwargs=False)
        ),
        converter_name="join",
    )
    join_conversion = CallFunc(
        converter,
        left_conversion,
        right_conversion,
        *condition.get_args_as_func_args(),
    )
    join_conversion.depends_on(*condition.get_args())
    return join_conversion
