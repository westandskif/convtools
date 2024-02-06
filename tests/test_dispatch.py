import pytest

from convtools import conversion as c


def test_dispatch():
    data = [
        {"obj": {"version": "v1", "field1": 10}},
        {"obj": {"version": "v2", "field2": 20}},
    ]
    data2 = [
        {"obj": {"version": "v1", "field1": 10}},
        {"obj": {"version": "v2", "field2": 20}},
        {"obj": {"version": "v3"}},
    ]
    converter = (
        c.iter(
            c.item("obj").dispatch(
                c.item("version"),
                {
                    "v1": c.item("field1"),
                    "v2": c.item("field2"),
                },
            )
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter(data) == [10, 20]

    converter2 = (
        c.iter(
            c.item("obj").dispatch(
                c.item("version"),
                {
                    "v1": c.item("field1"),
                    "v2": c.item("field2"),
                },
                -1,
            )
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter2(data2) == [10, 20, -1]

    with pytest.raises(KeyError):
        converter(data2)

    converter3 = (
        c.iter(
            c.call_func(lambda item: item["obj"], c.this).dispatch(
                c.item("version"),
                {
                    "v1": c.item("field1"),
                    "v2": c.item(c.input_arg("v2_field")),
                },
                -1,
            )
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter3(data2, v2_field="field2") == [10, 20, -1]
