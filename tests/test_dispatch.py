import re

import pytest

from convtools import conversion as c

from .utils import get_code_str


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


def test_dispatch_default_none():
    """Literal None must be a valid default, not treated as omitted."""
    assert (
        c.this.dispatch(c.item("v"), {"a": 1}, default=None).execute(
            {"v": "x"}
        )
        is None
    )
    assert (
        c.this.dispatch(c.item("v"), {"a": 1}, default=None).execute(
            {"v": "a"}
        )
        == 1
    )
    with pytest.raises(KeyError):
        c.this.dispatch(c.item("v"), {"a": 1}).execute({"v": "x"})


def test_dispatch_branch_naive_defaults():
    def fa(x):
        return ("a", x)

    def fb(x):
        return ("b", x)

    def fe(x):
        return ("e", x)

    converter = c.this.dispatch(
        c.item("k"),
        {
            "a": c.call_func(fa, c.item("v")),
            "b": c.call_func(fb, c.item("v")),
        },
        c.call_func(fe, c.item("v")),
    ).gen_converter()
    assert converter({"k": "a", "v": 1}) == ("a", 1)
    assert converter({"k": "b", "v": 2}) == ("b", 2)
    assert converter({"k": "z", "v": 3}) == ("e", 3)

    defs = [
        line
        for line in get_code_str(converter).splitlines()
        if line.startswith("def _branch")
    ]
    assert len(defs) == 3
    bound = []
    for line in defs:
        names = re.findall(r"(\w+)=__naive_values__", line)
        assert len(names) == 1
        bound.append(names[0])
    assert len(set(bound)) == 3
