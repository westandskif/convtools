import pytest

from convtools import conversion as c
from convtools.base import Call


def test_cloning_functionality():
    conv1 = c.item("a")
    conv2 = c.item("c").pipe(c.item("b").pipe(conv1))
    conv3 = c.item("d").pipe(c.item(c.input_arg("test")).pipe(conv1))

    assert conv3.execute({"d": {"X": {"a": 2}}}, test="X") == 2
    assert conv2.execute({"c": {"b": {"a": 1}}}) == 1

    conv1 = c.item("a")
    conv2 = conv1.item("b")
    conv3 = conv1.item("c")
    assert conv3.execute({"a": {"c": 3}}) == 3
    assert conv2.execute({"a": {"b": 2}}) == 2


def test_set_predefined_self():
    conv = Call().set_predefined_self(c.this())
    with pytest.raises(c.ConversionException):
        conv.set_predefined_self(c.this())


def test_group_by_reducer_clones():
    conv = c.aggregate(
        c.item("value").pipe(c.ReduceFuncs.Sum(c.this()).pipe(c.this() + 1))
    )
    conv.gen_converter(debug=True)
    assert len(conv.agg_items) == 1

    reducer = c.ReduceFuncs.DictSum(c.item("k"), c.item("v"))
    reducer1 = c.item("item1").pipe(reducer)
    reducer2 = c.item("item2").pipe(reducer)
    assert c.aggregate(reducer1).execute([{"item1": {"k": 1, "v": 2}}]) == {
        1: 2
    }
    assert c.aggregate(reducer2).execute([{"item2": {"k": 2, "v": 3}}]) == {
        2: 3
    }
