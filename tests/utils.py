from reprlib import Repr

from convtools._base import BaseConversion


class _StrictCtx(dict):
    """Test-only ctx that allows only declared or generated keys."""

    def _allowed(self, key):
        if key in BaseConversion.FIXED_CTX_NAMES:
            return True
        generated = dict.get(self, BaseConversion.GENERATED_NAMES)
        return generated is not None and key in generated

    def __setitem__(self, key, value):
        if not self._allowed(key):
            raise AssertionError(f"unregistered ctx key {key!r}")
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        if not self._allowed(key):
            raise AssertionError(f"unregistered ctx key {key!r}")
        dict.__delitem__(self, key)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def update(self, *args, **kwargs):
        raise AssertionError("ctx.update is not allowed")

    def __or__(self, other):
        raise AssertionError("ctx | is not allowed")

    def __ior__(self, other):
        raise AssertionError("ctx |= is not allowed")

    def pop(self, *args, **kwargs):
        raise AssertionError("ctx.pop is not allowed")

    def popitem(self):
        raise AssertionError("ctx.popitem is not allowed")

    def clear(self):
        raise AssertionError("ctx.clear is not allowed")


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
