from datetime import datetime

import pytest

from convtools import conversion as c
from convtools._base import GetItem


def test_mutation_item():
    now = datetime.now()
    assert c.list_comp(
        {
            "name": c.item("fullName"),
            "age": c.item("age").as_type(int),
            "to_del": 1,
        }
    ).pipe(
        c.list_comp(
            c.call_func(lambda d: d, c.this).tap(
                c.Mut.set_item(
                    "name_before", c.label("_input").item(0, "name")
                ),
                c.Mut.set_item("name", c.item("name").call_method("lower")),
                c.Mut.set_item(
                    "name_after", c.label("_input").item(0, "name")
                ),
                c.Mut.set_item("_updated", c.input_arg("now")),
                c.Mut.set_item(
                    c.item("age"), c.item("age") >= c.call_func(lambda: 18)
                ),
                c.Mut.del_item("to_del"),
                c.Mut.custom(c.this.call_method("update", {"to_add": 2})),
                c.this.call_method("update", {"to_add2": 4}),
            )
        ),
        label_input="_input",
    ).execute(
        [{"fullName": "John", "age": "28"}], now=now
    ) == [
        {
            "name": "john",
            "name_after": "john",
            "name_before": "John",
            "age": 28,
            "_updated": now,
            28: True,
            "to_add": 2,
            "to_add2": 4,
        }
    ]

    with pytest.raises(Exception):
        c.item(c.Mut.set_item("abc", "cde"))
    with pytest.raises(Exception):
        conversion = c.item(1)
        conversion.ensure_conversion(
            c.Mut.set_item("abc", "cde"), explicitly_allowed_cls=GetItem
        )


def test_mutation_attr():
    class A:
        pass

    obj = A()
    obj.a = 1
    obj.b = 2

    obj = (
        c.this.tap(
            c.Mut.del_attr("a"),
            c.Mut.set_attr("c", 3),
        )
    ).execute(obj, debug=False)
    assert not hasattr(obj, "a") and obj.b == 2 and obj.c == 3

    obj = A()
    obj.a = 1
    obj.b = 2

    obj = (
        c.tap(
            c.Mut.del_attr("a"),
            c.Mut.set_attr("c", 3),
        )
    ).execute(obj, debug=False)
    assert not hasattr(obj, "a") and obj.b == 2 and obj.c == 3


def test_iter_mut_method():
    assert c.iter(c.item(0)).as_type(list).execute([[1], [2]]) == [1, 2]
    assert c.iter_mut(c.Mut.custom(c.this.call_method("append", 7))).as_type(
        list
    ).execute([[1], [2]]) == [[1, 7], [2, 7]]
    result = (
        c.this.iter({"a": c.this})
        .iter_mut(
            c.Mut.set_item("b", c.item("a") + 1),
            c.Mut.set_item("c", c.item("a") + c.call_func(lambda: 2)),
        )
        .iter_mut(
            c.Mut.set_item("d", c.item("a") + 3),
        )
        .as_type(list)
        .execute([1, 2, 3], debug=False)
    )
    assert result == [
        {"a": 1, "b": 2, "c": 3, "d": 4},
        {"a": 2, "b": 3, "c": 4, "d": 5},
        {"a": 3, "b": 4, "c": 5, "d": 6},
    ]

    result = (
        c.group_by(c.item(0))
        .aggregate(
            c(
                [
                    {c.item(0): c.item(1).pipe(c.ReduceFuncs.Max(c.this))},
                    {c.item(1).pipe(c.ReduceFuncs.Max(c.this)): c.item(0)},
                ]
            )
            .iter_mut(
                c.Mut.set_item(
                    "x",
                    c.call_func(sum, c.this.call_method("values"))
                    + c.input_arg("base"),
                )
            )
            .as_type(tuple)
        )
        .execute([(0, 1), (0, 2), (1, 7)], base=100, debug=False)
    )
    assert result == [
        ({0: 2, "x": 102}, {2: 0, "x": 100}),
        ({1: 7, "x": 107}, {7: 1, "x": 101}),
    ]
