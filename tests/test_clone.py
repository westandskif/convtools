from convtools import conversion as c


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


def test_group_by_reducer_clones():
    data = [
        {"value": 2},
        {"value": 3},
    ]
    conv = c.aggregate(
        c.item("value").pipe(c.ReduceFuncs.Sum(c.this()).pipe(c.this() + 1))
    )
    assert conv.execute(data) == 6

    reducer = c.ReduceFuncs.DictSum(c.item("k"), c.item("v"))
    reducer1 = c.item("item1").pipe(reducer)
    reducer2 = c.item("item2").pipe(reducer)
    assert c.aggregate(reducer1).execute([{"item1": {"k": 1, "v": 2}}]) == {
        1: 2
    }
    assert c.aggregate(reducer2).execute([{"item2": {"k": 2, "v": 3}}]) == {
        2: 3
    }
