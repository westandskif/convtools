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
            "to_del_twice": 2,
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
                c.Mut.del_item("to_del_twice", if_exists=True),
                c.Mut.del_item("to_del_twice", if_exists=True),
                c.Mut.del_item("missing", if_exists=True),
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

    with pytest.raises(KeyError):
        c.this.tap(c.Mut.del_item("a")).execute({})

    result = (
        c.item(0)
        .tap(
            c.Mut.set_item("a", {}),
            c.Mut.set_item("b", 1, of_=c.item("a")),
            c.Mut.del_item("d", of_=c.item("c")),
            c.Mut.set_item("e", {}, of_=c.item("c")),
            c.Mut.set_item("f", 2, of_=c.item("c", "e")),
        )
        .execute([{"c": {"d": 2}}], debug=False)
    )
    assert result == {"a": {"b": 1}, "c": {"e": {"f": 2}}}


def test_mutation_attr():
    class A:
        pass

    obj = A()
    obj.a = 1
    obj.b = 2
    obj.to_del_twice = 3

    obj = (
        c.this.tap(
            c.Mut.del_attr("a"),
            c.Mut.del_attr("to_del_twice", if_exists=True),
            c.Mut.del_attr("to_del_twice", if_exists=True),
            c.Mut.del_attr("missing", if_exists=True),
            c.Mut.set_attr("c", 3),
        )
    ).execute(obj, debug=False)
    assert (
        not hasattr(obj, "a")
        and obj.b == 2
        and obj.c == 3
        and not hasattr(obj, "to_del_twice")
    )

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

    with pytest.raises(AttributeError):
        c.this.tap(c.Mut.del_attr("a")).execute(object())

    obj = A()
    obj.c = 2
    c.item(0).tap(
        c.Mut.set_attr("a", A()),
        c.Mut.set_attr("b", 1, of_=c.attr("a")),
        c.Mut.del_attr("c"),
    ).execute([obj])
    assert obj.a.b == 1 and not hasattr(obj, "c")


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
            c.Mut.set_item("obj", {"value": 10}),
            c.Mut.set_item(
                "value",
                c.item("obj", "value") + c.item("c"),
                of_=c.item("obj"),
            ),
        )
        .iter_mut(
            c.Mut.set_item("d", c.item("a") + 3),
        )
        .as_type(list)
        .execute([1, 2, 3])
    )
    assert result == [
        {"a": 1, "b": 2, "c": 3, "d": 4, "obj": {"value": 13}},
        {"a": 2, "b": 3, "c": 4, "d": 5, "obj": {"value": 14}},
        {"a": 3, "b": 4, "c": 5, "d": 6, "obj": {"value": 15}},
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
