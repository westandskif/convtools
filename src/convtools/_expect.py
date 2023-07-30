"""Conversions to check expected conditions or raise exception."""
from ._base import BaseConversion, ConversionException


_none = BaseConversion._none

EXPECT_TEMPLATE = """
def {converter_name}({code_args}):
    if {code_condition}:
        return data_
    raise ExpectException({error_msg})
"""


class ExpectException(ConversionException):
    pass


class Expect(BaseConversion):
    """Check condition and return the input as is or raise ExpectException.

    Args:
      condition: conversion to evaluate as condition
      error_msg: error message to pass to ExpectException
    """

    def __init__(self, conversion, condition, error_msg):
        super().__init__()
        self.conversion = self.ensure_conversion(conversion)
        self.condition = self.ensure_conversion(condition)
        self.error_msg = self.ensure_conversion(
            error_msg or "condition is not met"
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        ctx["ExpectException"] = ExpectException

        converter_name = self.gen_random_name("expect", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", self.conversion)

        with function_ctx:
            code_condition = self.condition.gen_code_and_update_ctx(
                "data_", ctx
            )
            error_msg = self.error_msg.gen_code_and_update_ctx("data_", ctx)
            code = EXPECT_TEMPLATE.format(
                converter_name=converter_name,
                code_args=function_ctx.get_def_all_args_code(),
                code_condition=code_condition,
                error_msg=error_msg,
            )
            conversion = function_ctx.gen_conversion(converter_name, code)
        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)
