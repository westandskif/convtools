"""Defines sorting conversions."""

from operator import attrgetter, itemgetter
from typing import Any, Callable

from ._base import (
    BaseConversion,
    EscapedString,
    GetAttr,
    GetItem,
    InputArg,
    NaiveConversion,
)
from ._utils import Code


class ReversedOrdering:
    """Wrapper which reverses lt, lte and gt, gte."""

    __slots__ = ["v"]

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        return other.v < self.v

    def __gt__(self, other):
        return other.v > self.v  # pragma: no cover

    def __eq__(self, other):
        return other.v == self.v

    def __le__(self, other):
        return other.v <= self.v  # pragma: no cover

    def __ge__(self, other):
        return other.v >= self.v  # pragma: no cover


class SortingKeyConversion(BaseConversion):
    """Generates sorting key lambda."""

    def __init__(self, keys, common_conv=None):
        super().__init__()
        self.common_conv = (
            None
            if common_conv is None
            else self.ensure_conversion(common_conv)
        )
        self.keys = [self.ensure_conversion(key) for key in keys]

    _any_ordering_hints = (
        BaseConversion.OutputHints.ORDERING_NONE_FIRST
        | BaseConversion.OutputHints.ORDERING_NONE_LAST
        | BaseConversion.OutputHints.ORDERING_DESC
    )

    def try_get_key_or_index(self, key):
        if isinstance(key, GetAttr):
            getter_type = "attr"
        elif isinstance(key, GetItem):
            getter_type = "item"
        else:
            return None

        if (
            key.default is not None
            or len(key.indexes) != 1
            or not key.indexes_are_simple
            or key.has_hint(self._any_ordering_hints)
        ):
            return None

        index = key.indexes[0]
        if isinstance(index, NaiveConversion):
            return index.value, getter_type
        if isinstance(index, InputArg):
            return index, getter_type

    def _gen_code_and_update_ctx(self, code_input, ctx):
        getter_type = None
        indexes = []
        if self.common_conv is None:
            for key in self.keys:
                value = self.try_get_key_or_index(key)
                if value is None:
                    break
                key_or_index, getter_type_ = value

                if getter_type is None:
                    getter_type = getter_type_
                elif getter_type != getter_type_:
                    break

                indexes.append(key_or_index)

            else:
                f: "Callable[[Any], Any]"
                if getter_type == "item":
                    name = "operator_itemgetter"
                    f = itemgetter
                else:
                    name = "operator_attrgetter"
                    f = attrgetter
                ctx[name] = f
                return (
                    EscapedString(name)
                    .call(*indexes)
                    .gen_code_and_update_ctx(code_input, ctx)
                )

        ctx["ReversedOrdering"] = ReversedOrdering
        wrapper_name = self.gen_random_name("sorting_key_wrapper", ctx)
        converter_name = self.gen_random_name("sorting_key", ctx)
        function_ctx = self.as_function_ctx(ctx)

        with function_ctx:
            code = Code()
            code.add_line("def placeholder", 1)

            code.add_line(f"def {converter_name}(data_):", 1)
            if self.common_conv is not None:
                code.add_line(
                    "data_ = {}".format(
                        self.common_conv.gen_code_and_update_ctx("data_", ctx)
                    ),
                    0,
                )
            code_pieces = []
            for key in self.keys:
                item_code = key.gen_code_and_update_ctx("data_", ctx)

                if key.has_hint(self.OutputHints.ORDERING_NONE_FIRST):
                    code_pieces.append(f"{item_code} is not None")

                if key.has_hint(self.OutputHints.ORDERING_NONE_LAST):
                    code_pieces.append(f"{item_code} is None")

                if key.has_hint(self.OutputHints.ORDERING_DESC):
                    code_pieces.append(f"ReversedOrdering({item_code})")
                else:
                    code_pieces.append(f"{item_code}")

            sorting_key_code = ", ".join(code_pieces)

            code.add_line(
                "return {}".format(
                    f"({sorting_key_code})"
                    if len(code_pieces) > 1
                    else sorting_key_code
                ),
                -1,
            )
            code.add_line(f"return {converter_name}", -1)

            code.lines_info[0] = (
                0,
                f"def {wrapper_name}({function_ctx.get_def_all_args_code()}):",
            )

        conversion = function_ctx.gen_conversion(
            wrapper_name, code.to_string(0)
        )

        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


class SortConversion(BaseConversion):
    """Shortcut for CallFunc(sorted, self, key=key, reverse=reverse)."""

    def __init__(self, key=None, reverse=False):
        """Initialize SortConversion.

        # --8<-- [start:sort_args_docs]

        Args:
          key: callable or conversion/tuple of conversions to form a sorting
            key, to be passed to :py:obj:`sorted`
          reverse (bool): to be passed to :py:obj:`sorted`
        # --8<-- [end:sort_args_docs]

        >>> c.this.sort(key=lambda x: x["a"])

        >>> c.this.sort(key=c.item("a"))

        >>> c.this.sort(
        >>>     key=(
        >>>         c.item("a"),
        >>>         c.item("b").desc(none_last=True),
        >>>         c.item("c").asc(none_first=True)
        >>>     ),
        >>> )
        """
        super().__init__()
        self.sorted_kwargs = {}
        if key is not None:
            if callable(key):
                self.sorted_kwargs["key"] = self.ensure_conversion(key)
            else:
                self.sorted_kwargs["key"] = self.ensure_conversion(
                    SortingKeyConversion(
                        (key if isinstance(key, tuple) else (key,))
                    )
                )
        if reverse:
            self.sorted_kwargs["reverse"] = self.ensure_conversion(reverse)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return (
            EscapedString("sorted")
            .call(EscapedString(code_input), **self.sorted_kwargs)
            .gen_code_and_update_ctx("NOT_NEEDED_OR_BUG", ctx)
        )
