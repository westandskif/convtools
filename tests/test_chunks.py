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


def test_chunks_by_condition(data_for_chunking):
    assert c.chunk_by_condition(c.call_func(len, c.CHUNK) < 5).iter(
        c.list_comp(c.item("z"))
    ).as_type(list).execute(data_for_chunking) == [
        [10, 11, 12, 13, 14],
        [15, 16, 17, 18],
    ]
    assert c.chunk_by_condition(
        c.and_(c.call_func(len, c.CHUNK) < 5, c.item("z") < 18)
    ).aggregate(c.ReduceFuncs.Median(c.item("z"))).as_type(list).execute(
        data_for_chunking,
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

    assert c.chunk_by(c.item("x")).iter(c.list_comp(c.item("z"))).as_type(
        list
    ).execute(data_for_chunking) == [
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

    assert (
        c.chunk_by(c.item("x"), size=2)
        .aggregate(
            c.ReduceFuncs.Last(c.item("z")),
        )
        .as_type(list)
        .execute(data_for_chunking)
        == [11, 12, 14, 15, 17, 18]
    )
