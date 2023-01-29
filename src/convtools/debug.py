"""Provides conversions which simplify debug"""
import pdb
import sys

from .base import BaseConversion, ensure_conversion


if "pydevd" in sys.modules:  # pragma: no cover

    def debug_func(obj):
        import pydevd  # type: ignore # pylint: disable=import-outside-toplevel

        pydevd.settrace()
        return obj

elif sys.version_info[:2] < (3, 7):  # pragma: no cover

    def debug_func(obj):
        pdb.set_trace()  # pylint: disable=forgotten-debug-statement
        return obj

else:  # pragma: no cover

    def debug_func(obj):
        breakpoint()  # pylint: disable=undefined-variable,forgotten-debug-statement # noqa: F821,E501
        return obj


class Breakpoint(BaseConversion):
    """Defines the conversion which wraps another one and puts a breakpoint
    after it"""

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.BREAKPOINT
    ) & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    debug_func = staticmethod(debug_func)

    def __init__(self, to_debug):
        super().__init__()
        self.conversion = self.ensure_conversion(
            ensure_conversion(to_debug).pipe(self.debug_func)
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)
