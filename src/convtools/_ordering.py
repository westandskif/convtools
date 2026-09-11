"""Defines sorting conversions."""

from operator import attrgetter, index, itemgetter
from typing import Any, Callable

from ._base import (
    BaseConversion,
    EscapedString,
    GetAttr,
    GetItem,
    InputArg,
    NaiveConversion,
    ThisConversion,
    ensure_conversion,
)
from ._utils import Code


class ReversedOrdering:
    """Wrapper which reverses lt, lte and gt, gte."""

    __slots__ = ["v"]

    def __init__(self, v):
        self.v = v

    def __hash__(self):
        return hash(self.v)  # pragma: no cover

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

    def __init__(
        self,
        keys,
        common_conv=None,
        *,
        ignore_hints=False,
        desc_via_reverse=False,
    ):
        super().__init__()
        self.ignore_hints = ignore_hints
        self.desc_via_reverse = desc_via_reverse
        raw_keys = []
        for key in keys:
            ensured = ensure_conversion(key)
            if isinstance(ensured, NaiveConversion) and callable(
                ensured.value
            ):
                raise TypeError(
                    "key sequence elements should be conversions; "
                    "wrap a callable as c.call_func(f, c.this)",
                    ensured.value,
                )
            raw_keys.append(ensured)
        if common_conv is not None and len(raw_keys) == 1:
            # module-level ensure_conversion: registering common_conv on
            # self as well would double-count its input uses / weight
            self.keys = [
                self.ensure_conversion(
                    ensure_conversion(common_conv).pipe(raw_keys[0])
                )
            ]
            self.common_conv = None
        else:
            self.keys = [self.ensure_conversion(key) for key in raw_keys]
            self.common_conv = (
                None
                if common_conv is None
                else self.ensure_conversion(common_conv)
            )

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

        blocking_hints = self._any_ordering_hints
        if self.desc_via_reverse:
            blocking_hints = (
                self.OutputHints.ORDERING_NONE_FIRST
                | self.OutputHints.ORDERING_NONE_LAST
            )

        if (
            (
                key.self_conv is not BaseConversion._none
                and not isinstance(key.self_conv, ThisConversion)
            )
            or key.default is not None
            or len(key.indexes) != 1
            or not key.indexes_are_simple
            or (not self.ignore_hints and key.has_hint(blocking_hints))
        ):
            return None

        index_ = key.indexes[0]
        if getter_type == "attr":
            # attrgetter splits on dots; InputArg names are unknown here.
            if (
                isinstance(index_, NaiveConversion)
                and isinstance(index_.value, str)
                and "." not in index_.value
            ):
                return index_.value, getter_type
            return None
        if isinstance(index_, NaiveConversion):
            return index_.value, getter_type
        if isinstance(index_, InputArg):
            return index_, getter_type

    def gen_code_and_update_ctx(self, code_input, ctx):
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

        if not self.ignore_hints and not self.desc_via_reverse:
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
            key_infos = []
            last_none_i = -1
            for i, key in enumerate(self.keys):
                item_code = key.gen_code_and_update_ctx("data_", ctx)
                none_first = (not self.ignore_hints) and key.has_hint(
                    self.OutputHints.ORDERING_NONE_FIRST
                )
                none_last = (not self.ignore_hints) and key.has_hint(
                    self.OutputHints.ORDERING_NONE_LAST
                )
                desc = (not self.ignore_hints) and key.has_hint(
                    self.OutputHints.ORDERING_DESC
                )
                if none_first or none_last:
                    last_none_i = i
                key_infos.append((item_code, none_first, none_last, desc))

            code_pieces = []
            for i, (item_code, none_first, none_last, desc) in enumerate(
                key_infos
            ):
                # Bind in key order through the last none-hinted key so a
                # later none-hinted key can read labels / side effects of
                # preceding keys (hoisting only the hinted keys would run
                # them first).
                if i <= last_none_i:
                    value_code = "v{}".format(i)
                    code.add_line("{} = {}".format(value_code, item_code), 0)
                else:
                    value_code = item_code

                flip_none = self.desc_via_reverse and desc
                if none_first:
                    if flip_none:
                        code_pieces.append("{} is None".format(value_code))
                    else:
                        code_pieces.append("{} is not None".format(value_code))
                if none_last:
                    if flip_none:
                        code_pieces.append("{} is not None".format(value_code))
                    else:
                        code_pieces.append("{} is None".format(value_code))

                if desc and not self.desc_via_reverse:
                    code_pieces.append(
                        "ReversedOrdering({})".format(value_code)
                    )
                else:
                    code_pieces.append("{}".format(value_code))

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
    """Extended version of sorted(..., key=key, reverse=reverse)."""

    def __init__(self, key=None, reverse=False):
        """Initialize SortConversion.

        # --8<-- [start:sort_args_docs]

        Args:
          key: callable, or conversion / tuple or list of conversions to form
            a sorting key, to be passed to sorted. A list is a sequence of
            keys (same as a tuple); wrap with c.list(...) for a single
            composite key. A Python callable is passed to sorted as is; a
            conversion is evaluated per element as the key. Sequence elements
            must be conversions (a plain callable raises TypeError; wrap it
            as c.call_func(f, c.this)). To use a callable known only at
            runtime, wrap it: key=c.input_arg("f").call(c.this).
          reverse (bool): to be passed to sorted
        # --8<-- [end:sort_args_docs]

        >>> c.this.sort(key=lambda x: x["a"])

        >>> c.this.sort(key=c.item("a"))

        >>> c.this.sort(key=c.input_arg("f").call(c.this))

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
        self.runs = None
        self.runtime_reverse = None
        self.static_reverse = False

        conversion_keys = None
        if key is not None:
            if isinstance(key, BaseConversion):
                conversion_keys = (key,)
            elif isinstance(key, (tuple, list)):
                if len(key) == 0:
                    raise ValueError("key sequence is empty")
                conversion_keys = tuple(key)
            elif callable(key):
                self.sorted_kwargs["key"] = self.ensure_conversion(key)
            else:
                raise TypeError(
                    "key should be a callable, a conversion, or a "
                    "tuple/list of conversions",
                    key,
                )

        if conversion_keys is None:
            if reverse:
                self.sorted_kwargs["reverse"] = self.ensure_conversion(reverse)
            return

        if isinstance(reverse, BaseConversion):
            self.runtime_reverse = self.ensure_conversion(reverse)
        else:
            self.static_reverse = bool(index(reverse)) if reverse else False

        ensured_keys = [ensure_conversion(k) for k in conversion_keys]
        grouped = []
        for k in ensured_keys:
            desc_k = bool(k.has_hint(self.OutputHints.ORDERING_DESC))
            if not grouped or grouped[-1][0] != desc_k:
                grouped.append((desc_k, [k]))
            else:
                grouped[-1][1].append(k)
        self.runs = [
            (
                desc_k,
                self.ensure_conversion(
                    SortingKeyConversion(group, desc_via_reverse=True)
                ),
            )
            for desc_k, group in grouped
        ]

    def _run_reverse_expr(self, desc_k, ctx, code_input):
        if self.runtime_reverse is not None:
            ctx["operator_index"] = index
            rev_code = self.runtime_reverse.gen_code_and_update_ctx(
                code_input, ctx
            )
            expr = "bool(operator_index({}))".format(rev_code)
            if desc_k:
                return "not {}".format(expr)
            return expr
        if desc_k != self.static_reverse:
            return "True"
        return None

    def gen_code_and_update_ctx(self, code_input, ctx):
        if self.runs is None:
            return (
                EscapedString("sorted")
                .call(EscapedString(code_input), **self.sorted_kwargs)
                .gen_code_and_update_ctx("NOT_NEEDED_OR_BUG", ctx)
            )

        if len(self.runs) == 1:
            desc_k, key_conv = self.runs[0]
            kwargs = {"key": key_conv}
            rev_expr = self._run_reverse_expr(desc_k, ctx, "NOT_NEEDED_OR_BUG")
            if rev_expr is not None:
                kwargs["reverse"] = EscapedString(rev_expr)
            return (
                EscapedString("sorted")
                .call(EscapedString(code_input), **kwargs)
                .gen_code_and_update_ctx("NOT_NEEDED_OR_BUG", ctx)
            )

        wrapper_name = self.gen_random_name("sort_wrapper", ctx)
        converter_name = self.gen_random_name("sort", ctx)
        function_ctx = self.as_function_ctx(ctx)

        with function_ctx:
            code = Code()
            code.add_line("def placeholder", 1)
            code.add_line(f"def {converter_name}(data_):", 1)
            if self.runtime_reverse is not None:
                ctx["operator_index"] = index
                rev_code = self.runtime_reverse.gen_code_and_update_ctx(
                    "NOT_NEEDED_OR_BUG", ctx
                )
                code.add_line(
                    "rev_ = bool(operator_index({}))".format(rev_code),
                    0,
                )
            code.add_line("data_ = list(data_)", 0)
            for desc_k, key_conv in reversed(self.runs):
                key_code = key_conv.gen_code_and_update_ctx(
                    "NOT_NEEDED_OR_BUG", ctx
                )
                if self.runtime_reverse is not None:
                    rev_arg = "rev_" if not desc_k else "not rev_"
                    code.add_line(
                        "data_.sort(key={}, reverse={})".format(
                            key_code, rev_arg
                        ),
                        0,
                    )
                else:
                    rev_expr = self._run_reverse_expr(
                        desc_k, ctx, "NOT_NEEDED_OR_BUG"
                    )
                    if rev_expr is not None:
                        code.add_line(
                            "data_.sort(key={}, reverse={})".format(
                                key_code, rev_expr
                            ),
                            0,
                        )
                    else:
                        code.add_line(
                            "data_.sort(key={})".format(key_code),
                            0,
                        )
            code.add_line("return data_", -1)
            code.add_line(f"return {converter_name}", -1)
            code.lines_info[0] = (
                0,
                f"def {wrapper_name}({function_ctx.get_def_all_args_code()}):",
            )

        conversion = function_ctx.gen_conversion(
            wrapper_name, code.to_string(0)
        )
        return (
            function_ctx.call_with_all_args(conversion)
            .call(EscapedString(code_input))
            .gen_code_and_update_ctx("NOT_NEEDED_OR_BUG", ctx)
        )
