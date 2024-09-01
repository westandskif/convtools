from types import GeneratorType

import pytest

from convtools import conversion as c


@pytest.fixture
def data_for_chunking():
    return [
        {"x": 0, "y": 0, "z": 10},
        {"x": 0, "y": 0, "z": 11},
        {"x": 0, "y": 1, "z": 12},
        {"x": 1, "y": 1, "z": 13},
        {"x": 1, "y": 2, "z": 14},
        {"x": 1, "y": 2, "z": 15},
        {"x": 2, "y": 3, "z": 16},
        {"x": 2, "y": 3, "z": 17},
        {"x": 2, "y": 4, "z": 18},
    ]


def test_chunks_exceptions():
    for bad_value in ("abc", -1):
        with pytest.raises(ValueError):
            c.chunk_by(size=bad_value)
    with pytest.raises(ValueError):
        c.chunk_by()
    with pytest.raises(ValueError):
        c.unordered_chunk_by()
    with pytest.raises(ValueError):
        c.unordered_chunk_by(c.item(0), size=-1)
    with pytest.raises(ValueError):
        c.unordered_chunk_by(c.item(0), max_items_in_memory=-1)


def test_chunks_by_condition(data_for_chunking):
    assert c.chunk_by_condition(c.call_func(len, c.CHUNK) < 5).iter(
        c.list_comp(c.item("z"))
    ).as_type(list).execute(data_for_chunking) == [
        [10, 11, 12, 13, 14],
        [15, 16, 17, 18],
    ]
    assert c.chunk_by_condition(
        c.and_(c.call_func(lambda x: len(x), c.CHUNK) < 5, c.item("z") < 18)
    ).aggregate(
        c.ReduceFuncs.Median(c.item(c.call_func(lambda: "z")))
    ).as_type(
        list
    ).execute(
        data_for_chunking
    ) == [
        12,
        16,
        18,
    ]
    assert c.chunk_by_condition(False).as_type(list).execute(range(3)) == [
        [0],
        [1],
        [2],
    ]


def test_chunks_by_size(data_for_chunking):
    assert c.chunk_by(size=5).iter(c.list_comp(c.item("z"))).as_type(
        list
    ).execute(data_for_chunking) == [
        [10, 11, 12, 13, 14],
        [15, 16, 17, 18],
    ]

    assert c.chunk_by(c.item(c.call_func(lambda: "x"))).iter(
        c.list_comp(c.item("z"))
    ).as_type(list).execute(data_for_chunking) == [
        [10, 11, 12],
        [13, 14, 15],
        [16, 17, 18],
    ]
    assert c.chunk_by(c.item("x"), size=2).iter(
        c.list_comp(c.item("z"))
    ).as_type(list).execute(data_for_chunking) == [
        [10, 11],
        [12],
        [13, 14],
        [15],
        [16, 17],
        [18],
    ]

    assert c.chunk_by(c.item("x"), c.item("y")).iter(
        c.list_comp(c.item("z"))
    ).as_type(list).execute(data_for_chunking) == [
        [10, 11],
        [12],
        [13],
        [14, 15],
        [16, 17],
        [18],
    ]

    assert c.chunk_by(c.item("x"), size=2).aggregate(
        c.ReduceFuncs.Last(c.item("z")),
    ).as_type(list).execute(data_for_chunking) == [11, 12, 14, 15, 17, 18]


def test_unordered_chunk_by_size():
    data = [
        {"a": 0, "b": 1},
        {"a": 1, "b": 6},
        {"a": 0, "b": 2},
        {"a": 1, "b": 7},
        {"a": 0, "b": 3},
        {"a": 1, "b": 8},
        {"a": 0, "b": 4},
        {"a": 1, "b": 9},
        {"a": 1, "b": 10},
        {"a": 0, "b": 5},
    ]
    gen = iter(
        c.unordered_chunk_by(c.item("a"))
        .aggregate(c.ReduceFuncs.Array(c.item("b")))
        .execute(data, debug=False)
    )
    assert isinstance(gen, GeneratorType)
    result = list(gen)
    assert result == [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]]
    result = (
        c.unordered_chunk_by(c.item("a"), size=3)
        .aggregate(c.ReduceFuncs.Array(c.item("b")))
        .as_type(list)
        .execute(data, debug=False)
    )
    assert result == [[1, 2, 3], [6, 7, 8], [4, 5], [9, 10]]
    result = (
        c.unordered_chunk_by(
            c.item("a"),
            max_items_in_memory=4,
            portion_to_pop_on_max_memory_hit=1,
        )
        .aggregate(c.ReduceFuncs.Array(c.item("b")))
        .as_type(list)
        .execute(data, debug=False)
    )
    assert result == [[1, 2], [6, 7], [3, 4], [8, 9], [10], [5]]
    result = (
        c.unordered_chunk_by(
            c.item("a"),
            max_items_in_memory=6,
            portion_to_pop_on_max_memory_hit=0.5,
        )
        .aggregate(c.ReduceFuncs.Array(c.item("b")))
        .as_type(list)
        .execute(data, debug=False)
    )
    assert result == [[1, 2, 3], [6, 7, 8, 9, 10], [4, 5]]
    result = (
        c.unordered_chunk_by(c.item("a"), size=4, max_items_in_memory=6)
        .aggregate(c.ReduceFuncs.Array(c.item("b")))
        .as_type(list)
        .execute(data, debug=True)
    )
    assert result == [[1, 2, 3], [6, 7, 8, 9], [4, 5], [10]]
