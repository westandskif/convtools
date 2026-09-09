from types import SimpleNamespace

import pytest

from convtools import conversion as c
from convtools._ordering import SortingKeyConversion

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


def test_asc_desc_do_not_mutate():
    k = c.item("a")
    k2 = k.desc()
    assert k2 is not k
    assert k.output_hints == 0
    data = [{"a": 1}, {"a": 2}]
    assert c.this.sort(key=k).execute(data) == [{"a": 1}, {"a": 2}]
    assert c.this.sort(key=k2).execute(data) == [{"a": 2}, {"a": 1}]

    k3 = k.asc(none_last=True)
    assert k3 is not k
    assert k.output_hints == 0
    assert c.this.sort(key=k).execute(data) == [{"a": 1}, {"a": 2}]

    this_desc = c.this.desc()
    assert this_desc is not c.this
    assert c.this.output_hints == 0

    sk = SortingKeyConversion((k,))
    assert sk.try_get_key_or_index(k) is not None


def test_pipe_ordering_hints():
    assert c.this.sort(key=c.this.pipe(int).desc()).execute(
        ["1", "3", "2"]
    ) == [
        "3",
        "2",
        "1",
    ]
    assert c.this.sort(
        key=c.item("a").pipe(c.this).asc(none_last=True)
    ).execute([{"a": None}, {"a": 2}]) == [{"a": 2}, {"a": None}]
    data = [{"a": 1}, {"a": 2}]
    assert c.this.sort(key=c.item("a").pipe(c.this.desc()).asc()).execute(
        data
    ) == [{"a": 1}, {"a": 2}]
    assert c.this.sort(key=c.item("a").desc().pipe(c.this).asc()).execute(
        data
    ) == [{"a": 1}, {"a": 2}]


def test_last_ordering_hint_wins():
    assert c.this.sort(key=c.this.desc().asc()).execute([1, 3, 2]) == [1, 2, 3]
    assert c.this.sort(key=c.this.asc().desc()).execute([1, 3, 2]) == [3, 2, 1]
    assert c.this.sort(key=c.this.pipe(int).desc().asc()).execute(
        ["1", "3", "2"]
    ) == ["1", "2", "3"]
    assert c.this.sort(key=c.this.pipe(int).asc().desc()).execute(
        ["1", "3", "2"]
    ) == ["3", "2", "1"]

    assert c.this.sort(
        key=c.this.pipe(c.this.desc(none_last=True)).asc()
    ).execute([1, 3, 2]) == [1, 2, 3]
    with pytest.raises(TypeError):
        c.this.sort(
            key=c.this.pipe(c.this.desc(none_last=True)).asc()
        ).execute([1, None, 2])
    assert c.this.sort(key=c.this.desc().asc(none_last=True)).execute(
        [1, None, 2]
    ) == [1, 2, None]
    assert c.this.sort(
        key=c.this.pipe(c.this.desc()).asc(none_last=True)
    ).execute([1, None, 2]) == [1, 2, None]
    with pytest.raises(TypeError):
        c.this.sort(key=c.this.desc(none_last=True).asc()).execute(
            [1, None, 2]
        )
    assert c.this.output_hints == 0


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


def test_sort_runtime_callable_via_input_arg_call():
    result = c.this.sort(key=c.input_arg("f").call(c.this)).execute(
        [3, 1, 2], f=lambda x: -x
    )
    assert result == [3, 2, 1]


def test_sort_chained_lookup_key():
    data = [{"a": {"b": 2}, "b": 0}, {"a": {"b": 1}, "b": 9}]
    result = c.this.sort(key=c.item("a").item("b")).execute(data)
    assert result == [{"a": {"b": 1}, "b": 9}, {"a": {"b": 2}, "b": 0}]

    attr_data = [
        SimpleNamespace(a=SimpleNamespace(b=2), b=0),
        SimpleNamespace(a=SimpleNamespace(b=1), b=9),
    ]
    result = c.this.sort(key=c.attr("a").attr("b")).execute(attr_data)
    assert [row.a.b for row in result] == [1, 2]

    mixed = [
        SimpleNamespace(a={"b": 2}),
        SimpleNamespace(a={"b": 1}),
    ]
    result = c.this.sort(key=c.attr("a").item("b")).execute(mixed)
    assert [row.a["b"] for row in result] == [1, 2]

    direct_key = c.item("a")
    sk_direct = SortingKeyConversion((direct_key,))
    assert sk_direct.try_get_key_or_index(sk_direct.keys[0]) is not None
    assert "operator_itemgetter" in get_code_str(
        c.this.sort(key=direct_key).gen_converter()
    )

    this_item = c.this.item("a")
    sk_this = SortingKeyConversion((this_item,))
    assert sk_this.try_get_key_or_index(sk_this.keys[0]) is not None

    chained_key = c.item("a").item("b")
    sk_chained = SortingKeyConversion((chained_key,))
    assert sk_chained.try_get_key_or_index(sk_chained.keys[0]) is None
    chained_code = get_code_str(c.this.sort(key=chained_key).gen_converter())
    assert "operator_itemgetter" not in chained_code
    assert "sorting_key" in chained_code


def test_sort_dotted_attr_name():
    a = SimpleNamespace(x=SimpleNamespace(y=20))
    b = SimpleNamespace(x=SimpleNamespace(y=10))
    setattr(a, "x.y", 1)
    setattr(b, "x.y", 2)
    data = [a, b]
    assert [c.attr("x.y").execute(r) for r in data] == [1, 2]

    result = c.sort(c.attr("x.y")).execute(data)
    assert [getattr(r, "x.y") for r in result] == [1, 2]

    result = c.sort(c.attr(c.input_arg("n"))).execute(data, n="x.y")
    assert [getattr(r, "x.y") for r in result] == [1, 2]

    dotted_code = get_code_str(c.this.sort(key=c.attr("x.y")).gen_converter())
    assert "operator_attrgetter" not in dotted_code
    input_arg_code = get_code_str(
        c.this.sort(key=c.attr(c.input_arg("n"))).gen_converter()
    )
    assert "operator_attrgetter" not in input_arg_code

    converter = c.this.sort(key=c.attr("a")).gen_converter()
    assert "operator_attrgetter" in get_code_str(converter)
    sk = SortingKeyConversion((c.attr("a"),))
    assert sk.try_get_key_or_index(sk.keys[0]) is not None
    sk_dotted = SortingKeyConversion((c.attr("x.y"),))
    assert sk_dotted.try_get_key_or_index(sk_dotted.keys[0]) is None
    sk_input = SortingKeyConversion((c.attr(c.input_arg("n")),))
    assert sk_input.try_get_key_or_index(sk_input.keys[0]) is None


def test_sort_key_list_equals_tuple():
    data = [
        {"a": 1, "b": 2},
        {"a": 1, "b": 1},
        {"a": 0, "b": 9},
    ]
    expected = c.this.sort(key=(c.item("a"), c.item("b").desc())).execute(data)
    result = c.this.sort(key=[c.item("a"), c.item("b").desc()]).execute(data)
    assert result == expected
    assert expected == [
        {"a": 0, "b": 9},
        {"a": 1, "b": 2},
        {"a": 1, "b": 1},
    ]

    none_data = [{"a": None}, {"a": 1}, {"a": 2}]
    none_expected = c.this.sort(
        key=(c.item("a").desc(none_last=True),)
    ).execute(none_data)
    none_list = c.this.sort(key=[c.item("a").desc(none_last=True)]).execute(
        none_data
    )
    assert none_list == none_expected


def test_sort_unsupported_key_type():
    with pytest.raises(TypeError, match="callable"):
        c.this.sort(key=123)
