import pytest

from convtools import conversion as c
from convtools._debug import Breakpoint


def test_base_zip():
    meta = {1: "a", 2: "b", 3: "c"}
    input_data = {"items": [1, 2, 3], "meta": meta}
    converter = (
        c.zip(
            c.item("items"),
            c.repeat(c.item("meta")),
        )
        .as_type(list)
        .gen_converter(debug=False)
    )
    assert converter(input_data) == [
        (1, meta),
        (2, meta),
        (3, meta),
    ]
    converter = (
        c.zip(
            item=c.item("items"),
            meta=c.repeat(c.item("meta")),
        )
        .as_type(list)
        .gen_converter(debug=False)
    )
    assert converter(input_data) == [
        {"item": 1, "meta": meta},
        {"item": 2, "meta": meta},
        {"item": 3, "meta": meta},
    ]

    input_data = [
        ([1, 2, 3], {1: "a", 2: "b", 3: "c"}),
        ([4, 5, 6], {4: "a", 5: "b", 6: "c"}),
    ]
    converter = (
        c.iter(c.zip(c.item(0), c.repeat(c.item(1))))
        .flatten()
        .iter(c.item(1, c.item(0)))
        .pipe(c.call_func(",".join, c.this))
        .gen_converter(debug=False)
    )
    assert converter(input_data) == "a,b,c,a,b,c"

    with pytest.raises(ValueError):
        c.zip(1, 2, a=1)

    assert c.this.pipe(c.this, label_output="abc").flatten().as_type(
        list
    ).execute([[1], [2]]) == [1, 2]


def test_base_zip_longest():
    # Test with positional args (tuples output)
    converter = (
        c.zip_longest(
            c.item("a"),
            c.item("b"),
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter({"a": [1, 2, 3], "b": [4, 5]}) == [
        (1, 4),
        (2, 5),
        (3, None),
    ]

    # Test with fill_value for positional args
    converter = (
        c.zip_longest(
            c.item("a"),
            c.item("b"),
            fill_value=-1,
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter({"a": [1, 2, 3], "b": [4, 5]}) == [
        (1, 4),
        (2, 5),
        (3, -1),
    ]

    # Test with keyword args (dicts output)
    converter = (
        c.zip_longest(
            x=c.item("a"),
            y=c.item("b"),
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter({"a": [1, 2, 3], "b": [4, 5]}) == [
        {"x": 1, "y": 4},
        {"x": 2, "y": 5},
        {"x": 3, "y": None},
    ]

    # Test with fill_value for keyword args
    converter = (
        c.zip_longest(
            x=c.item("a"),
            y=c.item("b"),
            fill_value="missing",
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter({"a": [1, 2], "b": [4, 5, 6]}) == [
        {"x": 1, "y": 4},
        {"x": 2, "y": 5},
        {"x": "missing", "y": 6},
    ]

    # Test error when mixing args and kwargs
    with pytest.raises(ValueError):
        c.zip_longest(1, 2, a=1)


def test_zip_in_aggregate():
    input_data = [
        ("kitchen", "size", 10),
        ("kitchen", "temperature", 40),
        ("living_room", "size", 12),
        ("living_room", "color", "white"),
    ]
    converter = (
        c.group_by(c.item(1))
        .aggregate(
            {
                "prop": c.item(1),
                "values": c.zip(
                    room=c.ReduceFuncs.Array(c.item(0)),
                    value=c.ReduceFuncs.Array(c.item(2)),
                ).as_type(list),
            }
        )
        .gen_converter()
    )
    assert converter(input_data) == [
        {
            "prop": "size",
            "values": [
                {"room": "kitchen", "value": 10},
                {"room": "living_room", "value": 12},
            ],
        },
        {"prop": "temperature", "values": [{"room": "kitchen", "value": 40}]},
        {
            "prop": "color",
            "values": [{"room": "living_room", "value": "white"}],
        },
    ]


def test_flatten():
    assert c.flatten().as_type(list).execute([[1], [2]]) == [1, 2]


def test_min_max():
    assert c.min(0, 1).execute(None) == 0
    assert c.min(2, 1).execute(None) == 1
    assert c.max(0, 1).execute(None) == 1
    assert c.max(2, 1).execute(None) == 2

    assert c.min(c.item(0), c.item(1)).execute((0, 1)) == 0
    assert c((2, 1)).pipe(c.min(c.item(0), c.item(1))).execute(None) == 1

    assert c.min(c.this).execute(range(3)) == 0
    assert c.max(c.this).execute(range(3)) == 2


def test_breakpoint():
    before = Breakpoint.debug_func
    l = []

    def add_to_list(obj):
        l.append(obj)
        return obj

    Breakpoint.debug_func = staticmethod(add_to_list)
    try:
        c.list_comp(c.this.breakpoint()).execute([1, 2, 3])
        c.list_comp(c.breakpoint()).execute([3, 4])
    finally:
        Breakpoint.debug_func = before
    assert l == [1, 2, 3, 3, 4]
