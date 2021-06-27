import pytest

from convtools import conversion as c


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
        .pipe(c.call_func(",".join, c.this()))
        .gen_converter(debug=False)
    )
    assert converter(input_data) == "a,b,c,a,b,c"

    with pytest.raises(ValueError):
        c.zip(1, 2, a=1)


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
        .gen_converter(debug=True)
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
