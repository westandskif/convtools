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
                c.item("key1") * 500, skip_if=c.item("key1") < 5
            ): c.optional(c.item("key22"), skip_value=20),
        }
    ).gen_converter(debug=False)
    assert conv([{"key1": 1, "key2": 2}, {"key1": 10, "key22": 20}], x=1) == [
        {"key1": 1, "key2": 2, "key3": 200, 2: 0},
        {"key1": 10, "key4": 3000, "key5": 3000, 4000: 20},
    ]

    with pytest.raises(Exception):
        c.list_comp(c.optional(c.item("key1"))).gen_converter()
    with pytest.raises(Exception):
        c.optional(c.item("key1"), skip_value=1, skip_if=c.this)
    with pytest.raises(Exception):
        c.this.pipe(c.optional(c.this))


def test_optional_list_tuple_set():
    conv = c.list_comp(
        [
            c.item("key1"),
            c.optional(c.item("key2", default=None)),
            c.optional(c.item("key1") * 2, skip_value=20),
            c.optional(c.item("key1") * 3, skip_if=c.item("key1") < 5),
        ]
    ).gen_converter(debug=False)
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
