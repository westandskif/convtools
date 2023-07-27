"""Run multiple conversions until success, while catching exceptions."""
from typing import Any, Sequence, Tuple, Type, Union

from ._base import BaseConversion, NaiveConversion, This, ensure_conversion
from ._utils import Code


_none = BaseConversion._none

OneOrManyExceptions = Union[Exception, Tuple[Type[Exception], ...]]


class _TryMultiple(BaseConversion):
    """Run multiple conversions until success, while catching exceptions."""

    def __init__(
        self,
        conversion_exc_pairs: Sequence[Tuple[Any, OneOrManyExceptions]],
        default: Any,
    ):
        if not conversion_exc_pairs:
            raise ValueError("unsupported number of conversion_exc_pairs")
        super().__init__()
        self.conversion_exc_pairs = [
            (
                self.ensure_conversion(conversion),
                NaiveConversion(exc),
            )
            for conversion, exc in conversion_exc_pairs
        ]
        self.default = (
            None if default is _none else self.ensure_conversion(default)
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        converter_name = self.gen_random_name("try_multiple", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This())
        with function_ctx:
            code = Code()
            code.add_line("def placeholder", 1)
            last_index = len(self.conversion_exc_pairs) - 1
            for index, (conversion, exc) in enumerate(
                self.conversion_exc_pairs
            ):
                code_expr = conversion.gen_code_and_update_ctx("data_", ctx)

                if index != last_index or self.default is not None:
                    code.add_line("try:", 1)
                    code.add_line(f"return {code_expr}", -1)
                    code.add_line(
                        f"except {exc.gen_code_and_update_ctx(None, ctx)}:", 1
                    )
                    code.add_line("pass", -1)

                if index == last_index:
                    if self.default is None:
                        code.add_line(f"return {code_expr}", -1)
                    else:
                        code.add_line(
                            f'return {self.default.gen_code_and_update_ctx("data_", ctx)}',
                            -1,
                        )

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )

        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


def try_multiple(
    *conversion_exc_pairs: Tuple[Any, OneOrManyExceptions],
    default: Any = _none,
) -> BaseConversion:
    """Multiple conversions are run until success, while catching exceptions.

    It runs multiple conversions, catches exceptions except for the last one.
    If default is provided, it catches the last one too.

    Args:
      conversion_exc_pairs: sequence of tuples ({conversion or value},
        {exception type or types for isinstance check})
      default: value to return in case if every conversion failed

    """
    if len(conversion_exc_pairs) == 1 and default is _none:
        return ensure_conversion(conversion_exc_pairs[0][0])
    return _TryMultiple(conversion_exc_pairs, default)
