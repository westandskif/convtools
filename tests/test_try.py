import pytest

from convtools import conversion as c


def test_try():
    converter = (
        c.iter(
            c.try_(c.item("a"))
            .except_(KeyError, re_raise_if=c.this.and_(c.EXCEPTION), value=-1)
            .except_(TypeError, value=-2)
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter([{}]) == [-1]

    assert converter([None]) == [-2]

    with pytest.raises(KeyError):
        converter([{"b": 1}])

    assert c.try_(c.this).execute(10) == 10

    with pytest.raises(IndexError):
        c.try_(c.item(0)).except_(
            IndexError,
            None,
            re_raise_if=c.call_func(isinstance, c.EXCEPTION, IndexError),
        ).execute([])

    result = (
        c.try_(c.item(0))
        .except_(
            IndexError,
            (c.this, c.EXCEPTION),
        )
        .execute([])
    )
    assert result[0] == [] and result[1].args[0] == "list index out of range"

    assert (
        c.try_(
            c.try_(
                c.this / 0,
            ).except_((ZeroDivisionError,), -1, re_raise_if=c.this + None)
        )
        .except_(TypeError, value=c.this)
        .execute(10, debug=True)
        == 10
    )
