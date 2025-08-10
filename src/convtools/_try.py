"""Conversions for exception handling."""

from typing import Optional, Tuple

from ._base import BaseConversion, LazyEscapedString, Namespace, This
from ._utils import Code


_none = BaseConversion._none


class Try(BaseConversion):
    """Conversion wrapper to handle exceptions.

    >>> c.try_(c.item("a")).except_(
    >>>     KeyError,
    >>>     -1,
    >>>     re_raise_if=c.EXCEPTION.attr("args").pipe(len) != 0,
    >>> )
    """

    EXCEPTION = LazyEscapedString("exc_")

    def __init__(self, conv):
        super().__init__()
        self._conv = self.ensure_conversion(conv)
        self._exc_def: "Tuple[BaseConversion, ...]" = ()
        self._value: "Tuple[BaseConversion, ...]" = ()
        self._re_raise_if: "Tuple[Optional[BaseConversion], ...]" = ()

    def except_(self, exc_def, value, re_raise_if=None):
        """Defines exceptions to catch.

        Args:
          exc_def: exception class or tuple of exceptions classes to be caught
          value: value to return if the exc_def is caught and re-raising is not
            triggered
          re_raise_if (optional): conversion, if it evaluates to true, the
            caught exception is re-raised

        Both value and re_raise_if can either work with input data as usual or
        reference the caught exception as c.EXCEPTION.
        """
        new_self = Try(self._conv)
        new_self._exc_def = (  # pylint: disable=protected-access
            self._exc_def + (self.ensure_conversion(exc_def),)
        )
        new_self._value = self._value + (  # pylint: disable=protected-access
            self.ensure_conversion(
                Namespace(
                    value,
                    {self.EXCEPTION.name: "exc_"},
                )
            ),
        )
        new_self._re_raise_if = (  # pylint: disable=protected-access
            self._re_raise_if
            + (
                (
                    None
                    if re_raise_if is None
                    else self.ensure_conversion(
                        Namespace(
                            re_raise_if,
                            {self.EXCEPTION.name: "exc_"},
                        )
                    )
                ),
            )
        )  # pylint: disable=protected-access
        return new_self

    def gen_code_and_update_ctx(self, code_input, ctx):
        if not self._exc_def:
            return self._conv.gen_code_and_update_ctx(code_input, ctx)

        function_ctx = self.as_function_ctx(ctx)
        function_ctx.add_arg("data_", This)
        converter_name = self.gen_random_name("except_", ctx)
        code = Code()
        code.add_line("def placeholder:", 1)
        with function_ctx:
            code.add_line("try:", 1)
            code.add_line(
                "return {}".format(
                    self._conv.gen_code_and_update_ctx("data_", ctx)
                ),
                -1,
            )
            for exc_def, value, re_raise_if in zip(
                self._exc_def, self._value, self._re_raise_if
            ):
                code.add_line(
                    "except {} as exc_:".format(
                        exc_def.gen_code_and_update_ctx("data_", ctx)
                    ),
                    1,
                )
                if re_raise_if is not None:
                    code.add_line(
                        "if {}:".format(
                            re_raise_if.gen_code_and_update_ctx("data_", ctx)
                        ),
                        1,
                    )
                    code.add_line("raise", -1)
                code.add_line(
                    "return {}".format(
                        value.gen_code_and_update_ctx("data_", ctx)
                    ),
                    -1,
                )

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
        return function_ctx.call_with_all_args(
            function_ctx.gen_conversion(converter_name, code.to_string(0))
        ).gen_code_and_update_ctx(code_input, ctx)
