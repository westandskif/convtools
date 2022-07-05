"""
This module brings join functionality to the library
"""
import typing as t
from itertools import chain

from .aggregations import Aggregate, ReduceFuncs
from .base import (
    And,
    BaseConversion,
    CallFunc,
    Eq,
    GeneratorComp,
    If,
    InlineExpr,
    InputArg,
    LabelConversion,
    LazyEscapedString,
    NaiveConversion,
    Namespace,
    This,
    Tuple,
)
from .columns import ColumnRef


class JoinException(Exception):
    pass


class JoinCondition(LazyEscapedString):
    NAME: str

    def __init__(self):
        super().__init__(self.NAME)

    def col(self, column_name: str) -> BaseConversion:
        return self.pipe(ColumnRef(column_name, id_=self.NAME))


class LeftJoinCondition(JoinCondition):
    NAME = "left_row"


class RightJoinCondition(JoinCondition):
    NAME = "right_row"


class _JoinConditions:
    """A helper object to analyze join conditions"""

    LEFT = LeftJoinCondition()
    RIGHT = RightJoinCondition()
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

        if isinstance(condition, Namespace):
            condition = condition.conversion

        if isinstance(condition, NaiveConversion) and condition.value is True:
            return join_conditions

        if isinstance(condition, Eq):
            join_conditions.consume_eq(condition)
        elif isinstance(condition, And):
            join_conditions.consume_and(condition)
        else:
            join_conditions.consume_other(condition)

        return join_conditions

    @classmethod
    def _get_join_deps(cls, conv: "BaseConversion") -> t.Set[str]:
        return {
            dep.name
            for dep in conv.get_dependencies(types=LazyEscapedString)
            if dep.name in cls._ANY
        }

    def consume_eq(self, eq_conversion: "Eq"):
        if not isinstance(eq_conversion, Eq) or len(eq_conversion.args) <= 1:
            raise AssertionError

        if len(eq_conversion.args) > 2:
            for i in range(len(eq_conversion.args) - 1):
                self.consume_eq(
                    Eq(eq_conversion.args[i], eq_conversion.args[i + 1])
                )
            return

        first_deps, second_deps = map(self._get_join_deps, eq_conversion.args)
        if len(first_deps) > 1 or len(second_deps) > 1:
            return self.inner_loop_conditions.append(eq_conversion)

        if len(first_deps.union(second_deps)) == 2:
            if self.LEFT_NAME in first_deps:
                left_idx, right_idx = 0, 1
            else:
                left_idx, right_idx = 1, 0
            self.left_row_hashers.append(eq_conversion.args[left_idx])
            self.right_row_hashers.append(eq_conversion.args[right_idx])
        else:
            all_args = first_deps.union(second_deps)
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


class JoinConversion(BaseConversion):
    """Generates conversion which joins left_conversion and right_conversion
    using condition. The result is a generator of joined pairs

    Args:
      left_conversion (BaseConversion): left collection to join
      right_conversion (BaseConversion): right collection to join
      condition (BaseConversion): join condition. If is True, results in cross
        join
      how (str): one of the following: ``"inner"``, ``"left"``, ``"right"``,
        ``"outer"``
    """

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.LABEL_USAGE
        | BaseConversion.ContentTypes.NONE_USAGE
    )

    def __init__(
        self,
        left_conversion: BaseConversion,
        right_conversion: BaseConversion,
        condition: BaseConversion,
        how="inner",
    ):
        super().__init__()
        self.left_conversion = self.ensure_conversion(left_conversion)
        self.right_conversion = self.ensure_conversion(right_conversion)

        # hiding left & right LazyEscapedString from parents not to affect
        # parent function args
        self.condition = self.ensure_conversion(
            Namespace(
                condition,
                name_to_code={
                    _JoinConditions.LEFT_NAME: None,
                    _JoinConditions.RIGHT_NAME: None,
                },
            )
        )
        self.how = self.validate_how(how)

    @classmethod
    def validate_how(cls, how: str):
        how = how.lower()
        if how not in ("inner", "left", "right", "outer", "full"):
            raise ValueError(how)
        if how == "full":
            how = "outer"
        return how

    def _gen_code_and_update_ctx(self, code_input, ctx):
        converter_name = self.gen_name("join", ctx, (self, code_input))
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)

        with function_ctx:
            join_conditions = _JoinConditions.from_condition(
                self.condition, how=self.how
            )
            pre_filter = join_conditions.pre_filter
            inner_loop_conditions = join_conditions.inner_loop_conditions
            if self.how == "right":
                swapped_left_and_right = True
                left_conversion = self.right_conversion
                right_conversion = self.left_conversion
                right_collection_filters = (
                    join_conditions.left_collection_filters
                )
                right_row_filters = join_conditions.left_row_filters
                right_row_hashers = join_conditions.left_row_hashers
                left_collection_filters = (
                    join_conditions.right_collection_filters
                )
                left_row_filters = join_conditions.right_row_filters
                left_row_hashers = join_conditions.right_row_hashers
            else:
                swapped_left_and_right = False
                left_conversion = self.left_conversion
                right_conversion = self.right_conversion
                left_collection_filters = (
                    join_conditions.left_collection_filters
                )
                left_row_filters = join_conditions.left_row_filters
                left_row_hashers = join_conditions.left_row_hashers
                right_collection_filters = (
                    join_conditions.right_collection_filters
                )
                right_row_filters = join_conditions.right_row_filters
                right_row_hashers = join_conditions.right_row_hashers

            del join_conditions

            right_collection: "BaseConversion" = InputArg("right_")
            if right_collection_filters:
                right_collection = right_collection.pipe(
                    GeneratorComp(
                        This(),
                        where=Namespace(
                            And(*right_collection_filters),
                            name_to_code={
                                _JoinConditions.LEFT_NAME: True,
                                _JoinConditions.RIGHT_NAME: True,
                            },
                        ),
                    )
                )
            if self.how == "outer" or not left_row_hashers:
                right_collection = right_collection.as_type(list)

            right_collection = right_collection.add_label("right_collection")

            left_collection: BaseConversion = InputArg("left_")
            if left_collection_filters:
                left_collection = left_collection.pipe(
                    GeneratorComp(
                        This(),
                        where=Namespace(
                            And(*left_collection_filters),
                            name_to_code={
                                _JoinConditions.LEFT_NAME: True,
                                _JoinConditions.RIGHT_NAME: True,
                            },
                        ),
                    )
                )

            inner_loop_condition: "t.Optional[Namespace]" = None
            all_inner_loop_conditions = list(
                chain(
                    left_row_filters,
                    right_row_filters,
                    inner_loop_conditions,
                )
            )
            if all_inner_loop_conditions:
                inner_loop_condition = Namespace(
                    And(*all_inner_loop_conditions),
                    name_to_code={
                        _JoinConditions.LEFT_NAME: "right_item"
                        if swapped_left_and_right
                        else "left_item",
                        _JoinConditions.RIGHT_NAME: "left_item"
                        if swapped_left_and_right
                        else "right_item",
                    },
                )

            if left_row_hashers:
                left_row_conv_to_hash = (
                    Tuple(*left_row_hashers)
                    if len(left_row_hashers) > 1
                    else left_row_hashers[0]
                )
                right_row_conv_to_hash = (
                    Tuple(*right_row_hashers)
                    if len(right_row_hashers) > 1
                    else right_row_hashers[0]
                )

                right_collection_conversion = right_collection.pipe(
                    Aggregate(
                        ReduceFuncs.DictArray(
                            Namespace(
                                right_row_conv_to_hash,
                                {
                                    _JoinConditions.LEFT_NAME: True,
                                    _JoinConditions.RIGHT_NAME: True,
                                },
                            ),
                            This(),
                            default=dict,
                        )
                    ),
                    label_output="hash_to_items",
                )
                right_items = (
                    InlineExpr("left_item")
                    .pipe(
                        Namespace(
                            left_row_conv_to_hash,
                            {
                                _JoinConditions.LEFT_NAME: True,
                                _JoinConditions.RIGHT_NAME: True,
                            },
                        )
                    )
                    .pipe(
                        If(
                            This().in_(LabelConversion("hash_to_items")),
                            LabelConversion("hash_to_items").item(This()),
                            NaiveConversion(()),
                        )
                    )
                )
            else:
                right_collection_conversion = right_collection
                right_items = LabelConversion("right_collection")

            if self.how == "inner":
                conv = right_collection_conversion.pipe(
                    left_collection.pipe(
                        InlineExpr(
                            "((left_item, right_item)"
                            + " for left_item in {left_items}"
                            + " for right_item in {right_items}"
                            + (
                                " if {condition}"
                                if inner_loop_condition
                                else ""
                            )
                            + ")"
                        ).pass_args(
                            left_items=This(),
                            right_items=right_items,
                            condition=inner_loop_condition,
                        ),
                    ),
                )
            else:

                if swapped_left_and_right:

                    def _left_joiner(left_to_right_ones_gen):
                        none_ = object()
                        for left_item, right_ones in left_to_right_ones_gen:
                            right_item = next(right_ones, none_)
                            if right_item is none_:
                                yield None, left_item
                            else:
                                yield right_item, left_item
                                for right_item in right_ones:
                                    yield right_item, left_item

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
                            "(left_item, (right_item "
                            "for right_item in {right_items}"
                            + (
                                " if {condition}"
                                if inner_loop_condition
                                else ""
                            )
                            + "))"
                            + " for left_item in {left_items}"
                        ).pass_args(
                            left_items=This(),
                            right_items=right_items,
                            condition=inner_loop_condition,
                        ),
                    )
                ).pipe(left_joiner)

            if self.how == "outer":

                def _add_right_part(left_join_gen, right_collection):
                    yielded_right_ids = set()
                    for left_right in left_join_gen:
                        yielded_right_ids.add(id(left_right[1]))
                        yield left_right

                    yield from (
                        (None, right)
                        for right in right_collection
                        if id(right) not in yielded_right_ids
                    )

                conv = conv.pipe(
                    _add_right_part,
                    right_collection=LabelConversion("right_collection"),
                )
            if pre_filter:
                conv = If(
                    And(*pre_filter),
                    conv,
                    CallFunc(list),
                )

            code_join = conv.gen_code_and_update_ctx("___TEST___", ctx)

            if "___TEST___" in code_join:
                raise AssertionError(
                    "join conversion has a bug, please submit an issue"
                )

            function_ctx.add_arg("data_", This())
            code_left = left_conversion.gen_code_and_update_ctx("data_", ctx)
            code_right = right_conversion.gen_code_and_update_ctx("data_", ctx)
            code = f"""
def {converter_name}({function_ctx.get_def_all_args_code()}):
    left_ = {code_left}
    right_ = {code_right}
    return {code_join}
        """
            join_conversion = function_ctx.gen_conversion(converter_name, code)

        join_conversion.depends_on(self)
        return function_ctx.call_with_all_args(
            join_conversion
        ).gen_code_and_update_ctx(code_input, ctx)
