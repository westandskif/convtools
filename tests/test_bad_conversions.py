from itertools import chain

import pytest

from convtools import conversion as c
from convtools.base import BaseConversion, Code


class BadDropWhile(BaseConversion):
    """convtools implementation of :py:obj:`itertools.dropwhile`"""

    def __init__(self, condition):
        super().__init__()
        self.condition = self.ensure_conversion(condition)
        self.filter_results_conditions = None
        self.cast = self._none

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_name("_", ctx, ("take_while", self, code_input))
        converter_name = f"drop_while{suffix}"
        var_chain = f"chain{suffix}"
        var_it = f"it{suffix}"
        var_item = f"item{suffix}"

        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)
        with namespace_ctx:
            condition_code = self.condition.gen_code_and_update_ctx(
                var_item, ctx
            )

            code = Code()
            code.add_line(
                f"def {converter_name}({var_it},{var_chain}{code_args}):", 1
            )
            code.add_line(f"{var_it} = iter({var_it})", 0)
            code.add_line(f"for {var_item} in {var_it}:", 1)
            code.add_line(f"if not ({condition_code}):", 1)
            code.add_line("break", -2)
            code.add_line("else:", 1)
            code.add_line("return ()", -1)
            code.add_line(f"return {var_chain}(({var_item},), {var_it})", -1)
            self._code_to_converter(converter_name, code.to_string(0), ctx)
            return (
                c.escaped_string(converter_name)
                .call(
                    c.this,
                    c.naive(chain),
                    *positional_args_as_conversions,
                    **keyword_args_as_conversions,
                )
                .gen_code_and_update_ctx(code_input, ctx)
            )


def test_bad_namespace_usage():
    with pytest.raises(
        Exception, match="rendering prevented by parent NamespaceCtx"
    ):
        assert BadDropWhile(c.this < 100).gen_converter()

    with pytest.raises(
        Exception, match="rendering prevented by parent NamespaceCtx"
    ):
        assert BadDropWhile(c.this < c.input_arg("abc")).gen_converter()
