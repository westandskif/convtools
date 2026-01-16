"""Join conversions."""

from collections.abc import Sized
from itertools import chain, repeat
from typing import Set

from ._aggregations import Aggregate, ReduceFuncs
from ._base import (
    And,
    BaseConversion,
    CallFunc,
    Eq,
    EscapedString,
    If,
    LazyEscapedString,
    ListComp,
    NaiveConversion,
    Namespace,
    This,
    Tuple_,
)
from ._columns import ColumnRef
from ._utils import Code


_none = BaseConversion._none


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
    """A helper object to analyze join conditions."""

    LEFT = LeftJoinCondition()
    RIGHT = RightJoinCondition()
    LEFT_NAME = LEFT.name
    RIGHT_NAME = RIGHT.name
    _ANY = {LEFT_NAME, RIGHT_NAME}

    def __init__(self, how="inner", swapped=False):
        if how == "right":
            raise AssertionError(
                "initialize via from_condition; it should have replaced right with left"
            )
        self.pre_filter = []
        self.inner_loop_conditions = []
        self.left_collection_filters = []
        self.left_row_hashers = []
        self.right_collection_filters = []
        self.right_row_hashers = []

        self.how = how
        self.swapped = swapped

        self.inner_join = how == "inner"
        self.left_join = how in {"left", "full"}
        self.full_join = how == "full"
        if not self.inner_join and not self.left_join:
            raise AssertionError

    def _add_hashers(self, left, right):
        if self.swapped:
            self.right_row_hashers.append(left)
            self.left_row_hashers.append(right)
        else:
            self.left_row_hashers.append(left)
            self.right_row_hashers.append(right)

    def _add_left_filter(self, filter_conv, external_call=True):
        if self.swapped and external_call:
            return self._add_right_filter(filter_conv, external_call=False)

        if self.left_join:
            self.inner_loop_conditions.append(filter_conv)
        else:
            self.left_collection_filters.append(filter_conv)

    def _add_right_filter(self, filter_conv, external_call=True):
        if self.swapped and external_call:
            return self._add_left_filter(filter_conv, external_call=False)

        if self.full_join:
            self.inner_loop_conditions.append(filter_conv)
        else:
            self.right_collection_filters.append(filter_conv)

    @classmethod
    def from_condition(cls, condition, how="inner") -> "_JoinConditions":
        join_conditions = (
            cls(how="left", swapped=True) if how == "right" else cls(how)
        )

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
    def _get_join_deps(cls, conv: "BaseConversion") -> Set[str]:
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
            self._add_hashers(
                eq_conversion.args[left_idx], eq_conversion.args[right_idx]
            )
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

    def wrap_with_namespace(self, conversion, left=None, right=None):
        name_to_code = {}
        if left is not None:
            name_to_code[
                self.RIGHT_NAME if self.swapped else self.LEFT_NAME
            ] = left
        if right is not None:
            name_to_code[
                self.LEFT_NAME if self.swapped else self.RIGHT_NAME
            ] = right

        return Namespace(conversion, name_to_code)


class JoinConversion(BaseConversion):
    """Join results of two conversions as generated of joined pairs.

    Args:
      left_conversion (BaseConversion): left collection to join
      right_conversion (BaseConversion): right collection to join
      condition (BaseConversion): join condition. If is True, results in cross
        join
      how (str): one of the following: ``"inner"``, ``"left"``, ``"right"``,
        ``"full"``
    """

    self_content_type = (
        BaseConversion.self_content_type
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
    def validate_how(
        cls,
        how: str,
        _how_choices=frozenset(["inner", "left", "right", "full", "outer"]),
    ):
        how = how.lower()
        if how not in _how_choices:
            raise ValueError(how)
        if how == "outer":
            how = "full"
        return how

    @staticmethod
    def _yield_pair(swapped: bool) -> str:
        """Return yield statement for a matched pair."""
        if swapped:
            return "yield right_item, left_item"
        return "yield left_item, right_item"

    @staticmethod
    def _yield_left_with_none(swapped: bool) -> str:
        """Return yield statement for unmatched left item."""
        if swapped:
            return "yield None, left_item"
        return "yield left_item, None"

    @staticmethod
    def _wrap_for_full_join(conv, join_conditions, **namespace_kwargs):
        """Wrap conversion to handle (idx, item) tuples in full joins.

        For full joins, right items are stored as (idx, item) tuples to track
        matched items. This helper extracts the item before applying namespace.
        """
        wrapped = join_conditions.wrap_with_namespace(conv, **namespace_kwargs)
        if join_conditions.full_join:
            return This.item(1).pipe(wrapped)
        return wrapped

    @classmethod
    def _build_inner_loop_filter(cls, join_conditions):
        """Build filter for inner loop conditions, handling full join tuples."""
        if not join_conditions.inner_loop_conditions:
            return None
        return cls._wrap_for_full_join(
            And(*join_conditions.inner_loop_conditions),
            join_conditions,
            left="left_item",
            right=True,
        )

    @staticmethod
    def _maybe_track_right_index(code, join_conditions):
        """Track right item index for full joins."""
        if not join_conditions.full_join:
            raise AssertionError
        code.add_line("yielded_right_indices.add(right_idx)", 0)

    def _gen_hash_join_code(self, code, ctx, join_conditions):
        """Generate hash join code. Returns initial_right for full join yield."""
        c_left_key_to_hash = join_conditions.wrap_with_namespace(
            (
                Tuple_(*join_conditions.left_row_hashers)
                if len(join_conditions.left_row_hashers) > 1
                else join_conditions.left_row_hashers[0]
            ),
            left=True,
        )
        c_right_hasher = (
            Tuple_(*join_conditions.right_row_hashers)
            if len(join_conditions.right_row_hashers) > 1
            else join_conditions.right_row_hashers[0]
        )
        c_right_key_to_hash = self._wrap_for_full_join(
            c_right_hasher, join_conditions, right=True
        )
        if join_conditions.full_join:
            code.add_line(
                "right_enumerated_ = list(enumerate(right_))", 0
            )
            right_input = EscapedString("right_enumerated_")
        else:
            right_input = EscapedString("right_")
        where_clause = (
            self._wrap_for_full_join(
                And(*join_conditions.right_collection_filters),
                join_conditions,
                right=True,
            )
            if join_conditions.right_collection_filters
            else None
        )
        code.add_line(
            "hash_to_right_items = %s"
            % right_input.pipe(
                Aggregate(
                    ReduceFuncs.DictArray(
                        c_right_key_to_hash,
                        This,
                        default=NaiveConversion({}),
                        where=where_clause,
                    )
                )
            ).gen_code_and_update_ctx(
                "right_enumerated_"
                if join_conditions.full_join
                else "right_",
                ctx,
            ),
            0,
        )
        code.add_line("del right_", 0)
        if join_conditions.full_join:
            code.add_line("del right_enumerated_", 0)
            initial_right = "(enum_item for items in hash_to_right_items.values() for enum_item in items)"
        else:
            initial_right = "(item for items in hash_to_right_items.values() for item in items)"

        code.add_line("for left_item in left_:", 1)
        code.add_line(
            "left_key = %s"
            % c_left_key_to_hash.gen_code_and_update_ctx("left_item", ctx),
            0,
        )

        c_left_key = EscapedString("left_key")
        c_hash_to_right_items = EscapedString("hash_to_right_items")

        inner_loop_filter = self._build_inner_loop_filter(join_conditions)
        code.add_line(
            "right_items = %s"
            % If(
                c_left_key.in_(c_hash_to_right_items),
                c_hash_to_right_items.item(c_left_key).pipe(
                    This.filter(inner_loop_filter)
                    if inner_loop_filter
                    else This
                ),
                Tuple_(),
            )
            .pipe(iter if join_conditions.left_join else This)
            .gen_code_and_update_ctx(None, ctx),
            0,
        )
        return initial_right

    def _gen_nested_loop_join_code(self, code, ctx, join_conditions):
        """Generate nested loop join code. Returns initial_right for full join yield."""
        if join_conditions.right_collection_filters:
            code.add_line(
                "right_ = %s"
                % ListComp(
                    This,
                    join_conditions.wrap_with_namespace(
                        And(*join_conditions.right_collection_filters),
                        right=True,
                    ),
                    _none,
                ).gen_code_and_update_ctx("right_", ctx),
                0,
            )
        else:
            code.add_line(
                "right_ = %s"
                % If(
                    CallFunc(isinstance, This, Sized),
                    This,
                    This.pipe(list),
                ).gen_code_and_update_ctx("right_", ctx),
                0,
            )

        if join_conditions.full_join:
            # For full joins, enumerate right items to track by index
            code.add_line(
                "right_enumerated_ = list(enumerate(right_))", 0
            )
            initial_right = "right_enumerated_"
            right_input_var = "right_enumerated_"
        else:
            initial_right = "right_"
            right_input_var = "right_"
        inner_loop_filter = self._build_inner_loop_filter(join_conditions)

        code.add_line("for left_item in left_:", 1)
        code.add_line(
            "right_items = %s"
            % (
                This.filter(inner_loop_filter)
                if inner_loop_filter
                else This
            )
            .pipe(iter if join_conditions.left_join else This)
            .gen_code_and_update_ctx(right_input_var, ctx),
            0,
        )
        return initial_right

    def _gen_yield_statements(self, code, join_conditions):
        """Generate yield statements for matched pairs."""
        if join_conditions.left_join:
            if join_conditions.full_join:
                # For full joins, right_items contains (idx, item) tuples
                code.add_line(
                    "right_enum = next(right_items, _none)", 0
                )
                code.add_line("if right_enum is _none:", 1)
                code.add_line(
                    self._yield_left_with_none(join_conditions.swapped), -1
                )
                code.add_line("else:", 1)
                code.add_line("right_idx, right_item = right_enum", 0)
                self._maybe_track_right_index(code, join_conditions)
                code.add_line(
                    self._yield_pair(join_conditions.swapped), 0
                )
                code.add_line(
                    "for right_idx, right_item in right_items:",
                    1,
                )
                self._maybe_track_right_index(code, join_conditions)
                code.add_line(
                    self._yield_pair(join_conditions.swapped), -3
                )
            else:
                code.add_line(
                    "right_item = next(right_items, _none)", 0
                )
                code.add_line("if right_item is _none:", 1)
                code.add_line(
                    self._yield_left_with_none(join_conditions.swapped), -1
                )
                code.add_line("else:", 1)
                code.add_line(
                    self._yield_pair(join_conditions.swapped), 0
                )
                code.add_line(
                    "for right_item in right_items:",
                    1,
                )
                code.add_line(
                    self._yield_pair(join_conditions.swapped), -3
                )

        else:
            code.add_line("for right_item in right_items:", 1)
            code.add_line(
                self._yield_pair(join_conditions.swapped), -2
            )

    def gen_code_and_update_ctx(self, code_input, ctx):
        join_conditions = _JoinConditions.from_condition(
            self.condition, how=self.how
        )

        suffix = self.gen_random_name("", ctx)
        converter_name = f"join{suffix}"
        code = Code()
        function_ctx = self.condition.as_function_ctx(ctx, optimize_naive=True)

        if join_conditions.swapped:
            function_ctx.add_arg("left_", self.right_conversion)
            function_ctx.add_arg("right_", self.left_conversion)
        else:
            function_ctx.add_arg("left_", self.left_conversion)
            function_ctx.add_arg("right_", self.right_conversion)

        function_ctx.add_arg("_none", EscapedString("_none"))

        with function_ctx:
            code.add_line("def placeholder", 1)

            if join_conditions.left_collection_filters:
                code.add_line(
                    "left_ = %s"
                    % This.filter(
                        join_conditions.wrap_with_namespace(
                            And(*join_conditions.left_collection_filters),
                            left=True,
                        )
                    ).gen_code_and_update_ctx("left_", ctx),
                    0,
                )

            if join_conditions.full_join:
                code.add_line("yielded_right_indices = set()", 0)

            if join_conditions.right_row_hashers:
                initial_right = self._gen_hash_join_code(
                    code, ctx, join_conditions
                )
            else:
                initial_right = self._gen_nested_loop_join_code(
                    code, ctx, join_conditions
                )

            self._gen_yield_statements(code, join_conditions)

            if join_conditions.full_join:
                code.add_line(
                    "yield from ("
                    "(None, right_item) "
                    f"for right_idx, right_item in {initial_right} "
                    "if right_idx not in yielded_right_indices)",
                    0,
                )

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )
        c_result = function_ctx.call_with_all_args(conversion)

        if join_conditions.pre_filter:
            if join_conditions.inner_join:
                c_result = If(
                    And(*join_conditions.pre_filter),
                    c_result,
                    Tuple_().pipe(iter),
                )
            elif join_conditions.full_join:
                c_result = If(
                    And(*join_conditions.pre_filter),
                    c_result,
                    CallFunc(
                        chain,
                        CallFunc(zip, self.left_conversion, repeat(None)),
                        CallFunc(zip, repeat(None), self.right_conversion),
                    ),
                )
            else:
                c_result = If(
                    And(*join_conditions.pre_filter),
                    c_result,
                    (
                        CallFunc(zip, repeat(None), self.right_conversion)
                        if join_conditions.swapped
                        else CallFunc(zip, self.left_conversion, repeat(None))
                    ),
                )

        return c_result.gen_code_and_update_ctx(code_input, ctx)
