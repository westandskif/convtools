import pytest

from convtools import conversion as c

from .utils import get_code_str


def test_ordering():
    data = [
        {"a": None, "b": 1},
        {"a": 2, "b": 2},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
        {"a": 1, "b": 4},
        {"a": None, "b": 2},
    ]
    converter = c.this.sort(
        key=(
            c.item("a").asc(none_last=True),
            (c.item("b") % c.input_arg("x")).desc(),
        )
    ).gen_converter()
    result = converter(data, x=3)
    assert result == [
        {"a": 1, "b": 4},
        {"a": 2, "b": 2},
        {"a": 2, "b": 4},
        {"a": 2, "b": 3},
        {"a": None, "b": 2},
        {"a": None, "b": 1},
    ]

    converter = c.this.sort(
        key=(
            c.item("a").desc(none_first=True),
            (c.item("b") % c.input_arg("x")).desc(),
        )
    ).gen_converter()
    result = converter(data, x=10)
    assert result == [
        {"a": None, "b": 2},
        {"a": None, "b": 1},
        {"a": 2, "b": 4},
        {"a": 2, "b": 3},
        {"a": 2, "b": 2},
        {"a": 1, "b": 4},
    ]

    converter = c.this.sort(
        key=(
            c.item("a").asc(none_first=True),
            c.item("b").desc(),
        ),
        reverse=True,
    ).gen_converter()
    result = converter(data)
    assert result == [
        {"a": 2, "b": 2},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
        {"a": 1, "b": 4},
        {"a": None, "b": 1},
        {"a": None, "b": 2},
    ]

    converter = c.this.sort(key=c.item("b")).gen_converter()
    result = converter(data)
    assert result == [
        {"a": None, "b": 1},
        {"a": 2, "b": 2},
        {"a": None, "b": 2},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
        {"a": 1, "b": 4},
    ] and "]," not in get_code_str(converter)

    converter = c.this.sort(
        key=(c.item("b"), c.item(c.input_arg("field")))
    ).gen_converter()
    result = converter(data, field="b")
    assert result == [
        {"a": None, "b": 1},
        {"a": 2, "b": 2},
        {"a": None, "b": 2},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
        {"a": 1, "b": 4},
    ]

    class A:
        def __init__(self, v):
            self.a = v

        __hash__ = None

        def __eq__(self, v):
            return self.a == v

    attr_data = [A(2), A(1), A(3)]

    converter = c.this.sort(key=c.attr("a")).gen_converter()
    result = converter(attr_data)
    assert result == [A(1), A(2), A(3)]

    converter = c.this.sort(key=c.attr("a").desc()).gen_converter()
    result = converter(attr_data)
    assert result == [A(3), A(2), A(1)]

    result = sorted(
        data,
        key=c.sorting_key(c.item("a").desc(none_last=True), c.item("b")),
    )
    assert result == [
        {"a": 2, "b": 2},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
        {"a": 1, "b": 4},
        {"a": None, "b": 1},
        {"a": None, "b": 2},
    ]
    result = sorted(
        data,
        key=c.sorting_key(c.item(c.escaped_string("'b'"))),
    )
    assert result == [
        {"a": None, "b": 1},
        {"a": 2, "b": 2},
        {"a": None, "b": 2},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
        {"a": 1, "b": 4},
    ]

    class A:
        def __init__(self, v):
            self.a = v

        __hash__ = None
        __iter__ = None

        def __eq__(self, v):
            return self.a == v

        def __getitem__(self, k):
            return getattr(self, k)

    data = [A(2), A(1), A(3)]
    result = c.this.sort(key=(c.item("a"), c.attr("a"))).execute(
        data, debug=True
    )
    assert result == [A(1), A(2), A(3)]


def test_ordering_exceptions():
    with pytest.raises(ValueError):
        c.this.asc(none_first=True, none_last=True)
    with pytest.raises(ValueError):
        c.this.desc(none_first=True, none_last=True)


def test_ordering_callable_key():
    """Test sort with callable conversion keys like c.this."""
    # c.this as key (was broken before fix - ThisConversion is callable)
    converter = c.this.sort(key=c.this).gen_converter()
    assert converter([3, 1, 2]) == [1, 2, 3]

    # Lambda function as key (should still work)
    converter = c.this.sort(key=lambda x: -x).gen_converter()
    assert converter([3, 1, 2]) == [3, 2, 1]
