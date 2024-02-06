import pytest

from convtools import conversion as c
from convtools._base import LazyEscapedString


def test_bad_namespace_usage():
    abc = LazyEscapedString("abc")
    conversion = c.if_(abc == 1, True, False)
    ctx = conversion._init_ctx()
    function_ctx = conversion.as_function_ctx(ctx)
    with (
        pytest.raises(
            Exception, match="rendering prevented by parent NamespaceCtx"
        ),
        function_ctx,
    ):
        c(list(function_ctx.args_to_pass)).gen_code_and_update_ctx(
            "data_", ctx
        )
