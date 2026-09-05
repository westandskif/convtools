import pytest

from convtools import conversion as c


def test_optional_dict():
    conv = c.list_comp(
        {
            "key1": c.item("key1"),
            "key2": c.optional(c.item("key2", default=None)),
            "key3": c.optional(c.item("key1") * 200, skip_value=2000),
            "key4": c.optional(
                c.item("key1") * c.input_arg("x") * 300,
                skip_if=c.item("key1") < 5,
            ),
            "key5": c.optional(
                c.item("key1") * c.input_arg("x") * 300,
                keep_if=c.item("key1") >= 5,
            ),
            c.optional(c.item("key2", default=-1), skip_value=-1): 0,
            c.optional(
                c.item("key1") * 400, skip_if=c.item("key1") < 5
            ): c.optional(c.item("key22")),
            c.optional(
                c.item("key1") * c.call_func(lambda: 500),
                skip_if=c.item("key1") < 5,
            ): c.optional(c.item("key22"), skip_value=20),
        }
    ).gen_converter()
    assert conv([{"key1": 1, "key2": 2}, {"key1": 10, "key22": 20}], x=1) == [
        {"key1": 1, "key2": 2, "key3": 200, 2: 0},
        {"key1": 10, "key4": 3000, "key5": 3000, 4000: 20},
    ]

    with pytest.raises(Exception):
        c.list_comp(c.optional(c.item("key1"))).gen_converter()
    with pytest.raises(Exception):
        c.optional(c.item("key1"), skip_value=1, skip_if=c.this)
    with pytest.raises(ValueError):
        c.optional(c.item("key1"), skip_if=c.this, keep_if=c.this)
    with pytest.raises(Exception):
        c.item(1).pipe(c.optional(c.this))


def test_optional_list_tuple_set():
    conv = c.list_comp(
        [
            c.item("key1"),
            c.optional(c.item("key2", default=None)),
            c.optional(c.item("key1") * c.call_func(lambda: 2), skip_value=20),
            c.optional(c.item("key1") * 3, skip_if=c.item("key1") < 5),
        ]
    ).gen_converter()
    assert conv([{"key1": 1, "key2": 2}, {"key1": 10, "key22": 20}]) == [
        [1, 2, 2],
        [10, 30],
    ]
    conv = c.list_comp(
        (
            c.item("key1"),
            c.optional(c.item("key2", default=None)),
            c.optional(c.item("key1") * 2, skip_value=20),
            c.optional(c.item("key1") * 3, skip_if=c.item("key1") < 5),
        )
    ).gen_converter(debug=False)
    assert conv([{"key1": 1, "key2": 2}, {"key1": 10, "key22": 20}]) == [
        (1, 2, 2),
        (10, 30),
    ]
    conv = c.list_comp(
        {
            c.item("key1"),
            c.optional(c.item("key2", default=None)),
            c.optional(c.item("key1") * 2, skip_value=20),
            c.optional(c.item("key1") * 3, skip_if=c.item("key1") < 5),
        }
    ).gen_converter(debug=False)
    assert conv([{"key1": 1, "key2": 2}, {"key1": 10, "key22": 20}]) == [
        {1, 2, 2},
        {10, 30},
    ]


def _counting(value=None):
    calls = []

    def heavy(*args):
        calls.append(1)
        if args:
            return args[0]
        return value

    return heavy, calls


def test_optional_evaluates_conversion_once():
    assert c.list(c.optional(c.call_func(next, iter(range(9))))).execute(
        None
    ) == [0]

    heavy, calls = _counting(1)
    assert c.list(c.optional(c.call_func(heavy, 1))).execute(None) == [1]
    assert calls == [1]

    heavy, calls = _counting(1)
    assert c.tuple(c.optional(c.call_func(heavy, 1))).execute(None) == (1,)
    assert calls == [1]

    heavy, calls = _counting(1)
    assert c.set(c.optional(c.call_func(heavy, 1))).execute(None) == {1}
    assert calls == [1]

    heavy, calls = _counting(2)
    assert (
        c.list(c.optional(c.call_func(heavy, 2), skip_value=2)).execute(None)
        == []
    )
    assert calls == [1]

    heavy, calls = _counting(3)
    assert c.list(c.optional(c.call_func(heavy, 3), skip_value=2)).execute(
        None
    ) == [3]
    assert calls == [1]

    heavy, calls = _counting(1)
    assert c.dict(("k", c.optional(c.call_func(heavy, 1)))).execute(None) == {
        "k": 1
    }
    assert calls == [1]

    calls = []

    def heavy_key(x):
        calls.append(("k", x))
        return x

    def heavy_value(x):
        calls.append(("v", x))
        return x

    assert c.dict(
        (
            c.optional(c.call_func(heavy_key, "k")),
            c.optional(c.call_func(heavy_value, "v")),
        )
    ).execute(None) == {"k": "v"}
    assert calls == [("k", "k"), ("v", "v")]

    heavy, calls = _counting(1)
    assert (
        c.list(c.optional(c.call_func(heavy, 1), skip_if=c.this == 1)).execute(
            1
        )
        == []
    )
    assert calls == []

    heavy, calls = _counting(1)
    assert c.list(
        c.optional(c.call_func(heavy, 1), skip_if=c.this == 1)
    ).execute(0) == [1]
    assert calls == [1]

    calls = []

    def none_key():
        calls.append("k")
        return None

    def value_should_not_run():
        calls.append("v")
        return 1

    assert (
        c.dict(
            (
                c.optional(c.call_func(none_key)),
                c.optional(c.call_func(value_should_not_run)),
            )
        ).execute(None)
        == {}
    )
    assert calls == ["k"]

    order = []

    def key_fn(x):
        order.append("k")
        return x

    def value_fn(x):
        order.append("v")
        return x

    assert c.dict(
        (
            c.optional(c.call_func(key_fn, "k")),
            c.optional(c.call_func(value_fn, "v")),
        )
    ).execute(None) == {"k": "v"}
    assert order == ["k", "v"]

    order = []

    def mixed_key(x):
        order.append("k")
        return x

    def mixed_value(x):
        order.append("v")
        return x

    mixed = c.dict(
        (
            c.optional(c.call_func(mixed_key, "k"), keep_if=c.this == 1),
            c.optional(c.call_func(mixed_value, c.this)),
        )
    )
    assert mixed.execute(None) == {}
    assert order == []

    order = []
    assert mixed.execute(1) == {"k": 1}
    assert order == ["v", "k"]

    order = []
    none_value = c.dict(
        (
            c.optional(c.call_func(mixed_key, "k"), keep_if=c.this == 1),
            c.optional(c.call_func(mixed_value, None)),
        )
    )
    assert none_value.execute(1) == {}
    assert order == ["v"]
