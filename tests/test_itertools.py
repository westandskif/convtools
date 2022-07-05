from convtools import conversion as c


def test_take_while():
    result = c.take_while(c.this < 3).as_type(list).execute(range(5))
    assert result == [0, 1, 2]

    result = (
        c.call_func(range, c.this)
        .take_while(c.this < 3)
        .as_type(list)
        .execute(5)
    )
    assert result == [0, 1, 2]

    def f():
        yield from range(5)
        raise Exception

    result = (
        c.take_while(c.this < c.input_arg("stop_before"))
        .filter(c.this >= c.input_arg("min_value"))
        .filter(c.this < c.call_func(lambda: 3), cast=list)
        .execute(f(), min_value=2, stop_before=4)
    )
    assert result == [2]

    result = c.take_while(c.this < 0).as_type(list).execute(range(10))
    assert result == []


def test_drop_while():
    result = c.drop_while(c.this < 3).as_type(list).execute(range(5))
    assert result == [3, 4]

    result = (
        c.call_func(range, c.this)
        .drop_while(c.this < c.input_arg("min_value"))
        .as_type(list)
        .execute(5, min_value=3)
    )
    assert result == [3, 4]

    result = (
        c.drop_while(c.this >= c.call_func(lambda: 0))
        .as_type(list)
        .execute(range(10))
    )
    assert result == []
