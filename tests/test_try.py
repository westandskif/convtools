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


def test_try_except_tracks_input_arg_dependencies():
    # Mode 1: deps from the new except_ clause must land on the returned Try
    converter = (
        c.try_(c.item("a"))
        .except_(KeyError, c.input_arg("fallback"))
        .gen_converter()
    )
    assert converter({}, fallback=-1) == -1
    assert converter({"a": 5}, fallback=-1) == 5

    # Mode 2: chained except_ must re-register prior clause deps
    conv = (
        c.try_(c.item("a"))
        .except_(KeyError, c.input_arg("fb1"))
        .except_(TypeError, c.input_arg("fb2"))
        .gen_converter()
    )
    assert conv({}, fb1=-1, fb2=-2) == -1
    assert conv(None, fb1=-1, fb2=-2) == -2
    assert conv({"a": 5}, fb1=-1, fb2=-2) == 5

    # re_raise_if with an input arg must also be tracked
    strict_conv = (
        c.try_(c.item("a"))
        .except_(KeyError, -1, re_raise_if=c.input_arg("strict"))
        .gen_converter()
    )
    assert strict_conv({}, strict=False) == -1
    with pytest.raises(KeyError):
        strict_conv({}, strict=True)
