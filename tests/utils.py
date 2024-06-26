from reprlib import Repr

from convtools._base import BaseConversion


_repr = Repr()
_repr.maxdict = 1000
repr = _repr.repr


def get_code_str(converter):
    if isinstance(converter, BaseConversion):
        converter = converter.gen_converter()
    return "\n".join(
        "".join(code_piece.code_parts)
        for code_piece in converter.__globals__[
            "__convtools__code_storage"
        ].key_to_code_piece.values()
    )
