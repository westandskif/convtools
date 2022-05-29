import pytest

from convtools import conversion as c
from convtools.base import LazyEscapedString


def test_bad_namespace_usage():

    abc = LazyEscapedString("abc")
    conversion = c.if_(abc == 1, True, False)
    ctx = conversion._init_ctx()
    (
        positional_args_as_def_names,
        keyword_args_as_def_names,
        positional_args_as_conversions,
        keyword_args_as_conversions,
        namespace_ctx,
    ) = conversion.get_args_def_info(ctx)
    with pytest.raises(
        Exception, match="rendering prevented by parent NamespaceCtx"
    ), namespace_ctx:
        c(list(positional_args_as_conversions)).gen_code_and_update_ctx(
            "data_", ctx
        )
