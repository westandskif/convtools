import pytest

from convtools import conversion as c


class ExceptionA(Exception):
    pass


class ExceptionAA(ExceptionA):
    pass


class ExceptionB(Exception):
    pass


def f_a(x):
    raise ExceptionA


def f_aa(x):
    raise ExceptionAA


def f_b(x):
    raise ExceptionB


def f(x):
    return x * 10


def test_try_multiple():
    assert (
        c.try_multiple(
            (c.call_func(f_a, c.this), ExceptionA),
            (c.call_func(f_aa, c.this), ExceptionA),
            default=-1,
        ).execute(1)
        == -1
    )
    assert (
        c.try_multiple(
            (c.call_func(f_a, c.this), ExceptionA),
            (c.call_func(f_aa, c.this), ExceptionA),
            (c.call_func(f_b, c.this), ExceptionB),
            (c.call_func(f_b, c.this), Exception),
            (c.call_func(f, c.this), ()),
        ).execute(1)
        == 10
    )
    with pytest.raises(ExceptionAA):
        assert c.try_multiple(
            (c.call_func(f_a, c.this), ExceptionA),
            (c.call_func(f_aa, c.this), ExceptionA),
        ).execute(1)

    with pytest.raises(ValueError):
        c.try_multiple()
