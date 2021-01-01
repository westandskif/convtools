from datetime import datetime

import pytest

from convtools import conversion as c


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
            c.call_func(lambda d: d, c.this()).tap(
                c.Mut.set_item(
                    "name_before", c.label("_input").item(0, "name")
                ),
                c.Mut.set_item("name", c.item("name").call_method("lower")),
                c.Mut.set_item(
                    "name_after", c.label("_input").item(0, "name")
                ),
                c.Mut.set_item("_updated", c.input_arg("now")),
                c.Mut.set_item(c.item("age"), c.item("age") >= 18),
                c.Mut.del_item("to_del"),
                c.Mut.custom(c.this().call_method("update", {"to_add": 2})),
            )
        ),
        label_input="_input",
    ).execute(
        [{"fullName": "John", "age": "28"}], debug=False, now=now
    ) == [
        {
            "name": "john",
            "name_after": "john",
            "name_before": "John",
            "age": 28,
            "_updated": now,
            28: True,
            "to_add": 2,
        }
    ]

    with pytest.raises(Exception):
        c.item(c.Mut.set_item("abc", "cde"))


def test_mutation_attr():
    class A:
        pass

    obj = A()
    obj.a = 1
    obj.b = 2

    obj = (
        c.this().tap(
            c.Mut.del_attr("a"),
            c.Mut.set_attr("c", 3),
        )
    ).execute(obj, debug=True)
    assert not hasattr(obj, "a") and obj.b == 2 and obj.c == 3
