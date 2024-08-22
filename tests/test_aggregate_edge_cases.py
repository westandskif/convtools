import random
import statistics
from collections import Counter
from itertools import cycle
from operator import eq
from typing import List, Tuple

import pytest

from convtools import conversion as c

from .utils import get_code_str


@pytest.fixture
def dict_series():
    return [
        {"name": "Nick", "value": 1},
        {"name": "Nick", "value": 2},
        {"name": "John", "value": 20},
        {"name": "John", "value": 21},
        {"name": "John", "value": 22},
    ]


@pytest.fixture
def series():
    random.seed(73)
    return [
        (random.randint(0, 100), random.randint(0, 10**9))
        for _ in range(10000)
    ]


def ordered_set(data):
    return list({x: 1 for x in data})


def weighted_average(samples: List[Tuple]):
    return sum(v * w for v, w in samples) / sum(x[1] for x in samples)


def test_custom_reduce_initialization():
    with pytest.raises(TypeError):
        # initial is not provided
        c.reduce(lambda a, b: a + b, c.this)
    with pytest.raises(ValueError):
        # default is not provided, initial is a conversion, so it cannot be
        # used as default
        c.reduce(lambda a, b: a + b, c.this, initial=c.this)


def test_legacy_dict_reduce_approach(dict_series):
    output = c.aggregate(
        c.reduce(
            c.ReduceFuncs.DictSum,
            (c.item("name"), c.item("value")),
        )
    ).execute(dict_series)
    assert output == {
        "Nick": 3,
        "John": 63,
    }
    with pytest.raises(ValueError):
        c.ReduceFuncs.DictSum(c.this, c.this, c.this)
    with pytest.raises(ValueError):
        c.ReduceFuncs.DictSum({c.this, c.this})


def test_reducer_reuse(dict_series):
    f = lambda a, b: a + b
    reducer = c.reduce(f, c.item("value"), initial=0)
    reducer2 = c.reduce(
        f, c.item("value"), initial=0, where=c.or_(default=True)
    )
    output = (
        c.group_by(c.item("name"))
        .aggregate(
            (
                c.item("name"),
                reducer + 10,
                reducer2 + 20,
            )
        )
        .execute(dict_series)
    )
    assert output == [
        ("Nick", 13, 23),
        ("John", 73, 83),
    ]


def test_blank_aggregate(series):
    assert eq(
        c.group_by(c.item(0)).aggregate(c.item(0)).execute(series),
        list({x[0]: 1 for x in series}),
    )


def test_average(series):
    assert eq(
        c.aggregate(c.ReduceFuncs.Average(c.item(1))).execute(series),
        statistics.mean(x[1] for x in series),
    )


def test_average_with_group_by(series):
    assert eq(
        c.group_by(c.item(0))
        .aggregate(c.ReduceFuncs.Average(c.item(1)))
        .execute(series, debug=True),
        [
            statistics.mean(x[1] for x in series if x[0] == key)
            for key in ordered_set(x[0] for x in series)
        ],
    )


def test_average_of_empty_collection():
    assert c.aggregate(c.ReduceFuncs.Average(c.item(1))).execute([]) is None


def test_weighted_average(series):
    assert eq(
        c.aggregate(c.ReduceFuncs.Average(c.item(0), c.item(1))).execute(
            series
        ),
        weighted_average(series),
    )
    result = (
        c.group_by(c.item(0) // 5)
        .aggregate(
            [
                c.item(0) // 5,
                c.ReduceFuncs.Average(c.item(1)),
                c.ReduceFuncs.Average(
                    c.item(1), where=c.item(0) > 10, default=-1
                ),
            ]
        )
        .execute(zip(range(10), range(10)), debug=False)
    )
    assert result == [
        [0, 2, -1],
        [1, 7, -1],
    ]
    result = (
        c.group_by(c.item(0) // 5)
        .aggregate(
            [
                c.item(0) // 5,
                c.ReduceFuncs.Average(c.item(1), c.item(2)),
                c.ReduceFuncs.Average(
                    c.item(1), c.item(2), where=c.item(0) > 10, default=-1
                ),
            ]
        )
        .execute(zip(range(10), range(10), cycle([1, 2])), debug=False)
    )

    assert result == [
        [0, 2, -1],
        [1, 7, -1],
    ]


def test_weighted_average_with_group_by(series):
    assert eq(
        c.group_by(c.item(0))
        .aggregate(c.ReduceFuncs.Average(c.item(0), c.item(1)))
        .execute(series),
        [
            weighted_average([x for x in series if x[0] == key])
            for key in ordered_set(x[0] for x in series)
        ],
    )


def test_mode(series):
    assert eq(
        c.aggregate(c.ReduceFuncs.Mode(c.item(0))).execute(series),
        statistics.mode(x[0] for x in series),
    )


def test_mode_with_groupby():
    series = [(0, 1), (0, 1), (0, 2), (1, 1), (1, 2), (1, 2)]

    assert eq(
        (
            c.group_by(c.item(0))
            .aggregate(c.ReduceFuncs.Mode(c.item(1)))
            .execute(series)
        ),
        [
            statistics.mode([x[1] for x in series if x[0] == key])
            for key in ordered_set(x[0] for x in series)
        ],
    )


@pytest.mark.parametrize("k", [1, 5, 10**9])
def test_top_k(series, k):
    assert eq(
        c.aggregate(c.ReduceFuncs.TopK(k, c.item(1))).execute(series),
        [x[1] for x in Counter(x[1] for x in series).most_common(k)],
    )


def test_top_k_extra():
    assert c.aggregate(c.ReduceFuncs.TopK(2, c.this)).execute(
        [3, 3, 3, 2, 2, 1]
    ) == [3, 2]


@pytest.mark.parametrize("k", [0, -1])
def test_top_k_non_positive_int(k):
    with pytest.raises(ValueError):
        c.aggregate(c.ReduceFuncs.TopK(k, c.this)).execute([1, 2]),


@pytest.mark.parametrize("k", [c.item(1), "abc"])
def test_top_k_invalid_input(k):
    with pytest.raises(TypeError):
        c.aggregate(c.ReduceFuncs.TopK(k, c.this)).execute([1, 2]),


@pytest.mark.parametrize("k", [1, 5])
def test_top_k_with_group_by(series, k):
    assert eq(
        c.group_by(c.item(0))
        .aggregate(c.ReduceFuncs.TopK(k, c.item(1)))
        .execute(series),
        [
            [
                x[1]
                for x in Counter(
                    x[1] for x in series if x[0] == key
                ).most_common(k)
            ]
            for key in ordered_set(x[0] for x in series)
        ],
    )


def test_median(series):
    assert eq(
        c.aggregate(c.ReduceFuncs.Median(c.item(1))).execute(series),
        statistics.median(x[1] for x in series),
    )


def test_median_with_group_by(series):
    assert eq(
        c.group_by(c.item(0))
        .aggregate(c.ReduceFuncs.Median(c.item(1)))
        .execute(series),
        [
            statistics.median(x[1] for x in series if x[0] == key)
            for key in ordered_set(x[0] for x in series)
        ],
    )


def test_multiple_aggregations(dict_series):
    assert (
        c.aggregate(c.ReduceFuncs.Array(c.item("name")))
        .pipe(
            c.aggregate(c.ReduceFuncs.ArrayDistinct(c.this)).pipe(
                c.aggregate(c.ReduceFuncs.Max(c.this))
            )
        )
        .execute(dict_series, debug=False)
        == "Nick"
    )


def test_reducer_inlining(dict_series):
    def f():
        f.number_of_calls += 1
        if f.number_of_calls > f.max_number_of_calls:
            raise Exception
        return []

    f.max_number_of_calls = 1
    f.number_of_calls = 0

    converter = c.aggregate(
        c.ReduceFuncs.Array(
            c.item("name"), default=f, where=c.item("value") < 0
        ).pipe(
            c.if_(
                if_true=c.this,
                if_false=c.this,
            )
        )
    ).gen_converter()
    assert converter(dict_series) == []


def test_group_by_key_edge_case():
    with pytest.raises(ValueError):
        c.this.add_label("row").pipe(c.ReduceFuncs.Count())
    with pytest.raises(ValueError):
        (c.this.add_label("row") + 1).pipe(c.ReduceFuncs.Count() + 1)
    with pytest.raises(ValueError):
        c.this.pipe(c.ReduceFuncs.Count(), label_input="row")
    data = [
        (0, 1),
        (1, 2),
    ]
    assert c.group_by(c.item(0)).aggregate(
        c.if_(c.item(1), c.item(1), c.item(1)).pipe(
            (c.ReduceFuncs.Sum(c.this) / c.ReduceFuncs.Count(c.this)).pipe(
                c.this + 10
            )
        )
    ).gen_converter(debug=False)(data) == [11, 12]
    assert c.group_by(c.item(0)).aggregate(
        c.item(1).pipe(c.ReduceFuncs.Sum(c.this), label_output="count")
    ).gen_converter(debug=False)(data) == [1, 2]
    assert c.group_by().aggregate(1).execute([0]) == 1


def test_nested_group_by():
    data = [
        [0, [1, 2, 3]],
        [0, [4, 5, 6]],
        [1, [2, 3, 4]],
    ]
    assert c.group_by(c.item(0)).aggregate(
        (
            c.item(0),
            c.ReduceFuncs.Sum(
                c.item(1).pipe(c.aggregate(c.ReduceFuncs.Sum(c.this)))
            ),
        )
    ).execute(data, debug=False) == [
        (0, 21),
        (1, 9),
    ]
    agg_conv = c.aggregate(c.ReduceFuncs.Sum(c.this))
    assert c.group_by(c.item(0)).aggregate(
        (
            c.item(0),
            c.if_(
                c.item(1),
                c.item(1),
                c.item(1),
            ).pipe(
                c.if_(
                    c.this,
                    c.this,
                    c.this,
                ).pipe(
                    c.ReduceFuncs.Sum(
                        c.if_(
                            c.this,
                            c.this,
                            c.this,
                        )
                        .pipe((agg_conv, agg_conv))
                        .pipe(c.item(1))
                    ).pipe(
                        c.if_(
                            c.this,
                            c.this,
                            c.this,
                        )
                    ),
                )
            ),
        )
    ).execute(data, debug=False) == [
        (0, 21),
        (1, 9),
    ]

    summer = c.aggregate(c.ReduceFuncs.Sum(c.this))

    merger = c.aggregate(
        {
            "value1": c.ReduceFuncs.First(
                c.item("value1"), where=c("value1").in_(c.this)
            ),
            "value2": c.ReduceFuncs.First(
                c.item("value2"), where=c("value2").in_(c.this)
            ).pipe(c.if_(c.this, c.this.pipe(summer))),
        }
    )
    converter = (
        c.group_by(c.item("id_"))
        .aggregate(
            {
                "id_": c.item("id_"),
                "data": c.ReduceFuncs.Array(c.this).pipe(merger),
            }
        )
        .gen_converter(debug=False)
    )
    assert converter(
        [
            {"id_": 1, "value1": 2},
            {"id_": 2, "value1": 3},
            {"id_": 2, "value2": [1, 2, 3]},
        ]
    ) == [
        {"id_": 1, "data": {"value1": 2, "value2": None}},
        {"id_": 2, "data": {"value1": 3, "value2": 6}},
    ]

    def g():
        yield 1
        raise Exception

    assert (
        c.aggregate(c.ReduceFuncs.First(c.this)).execute(g(), debug=False)
    ) == 1


def test_aggregate_no_init_loops():
    converter = c.aggregate(
        {
            "first_a": c.ReduceFuncs.First(c.item("a"), where=c.item("b") > 0),
            "list_b": c.ReduceFuncs.Array(c.item("b"), where=c.item("a") > 0),
        }
    ).gen_converter(debug=False)
    assert converter(
        [
            {"a": 1, "b": 0},
            {"a": 2, "b": 1},
            {"a": 3, "b": 2},
            {"a": 4, "b": 3},
        ],
    ) == {
        "first_a": 2,
        "list_b": [0, 1, 2, 3],
    }


def test_aggregate_percentile():
    converter = c.aggregate(
        (
            c.ReduceFuncs.Percentile(50, c.this),
            c.ReduceFuncs.Percentile(100, c.this),
        )
    ).gen_converter()
    assert converter(range(10)) == (4.5, 9)
    assert converter(range(11)) == (5, 10)
    converter = c.aggregate(
        (
            c.ReduceFuncs.Percentile(0, c.this, interpolation="linear"),
            c.ReduceFuncs.Percentile(49, c.this, interpolation="linear"),
            c.ReduceFuncs.Percentile(50, c.this, interpolation="linear"),
            c.ReduceFuncs.Percentile(51, c.this, interpolation="linear"),
            c.ReduceFuncs.Percentile(100, c.this, interpolation="linear"),
            #
            c.ReduceFuncs.Percentile(0, c.this, interpolation="lower"),
            c.ReduceFuncs.Percentile(49, c.this, interpolation="lower"),
            c.ReduceFuncs.Percentile(50, c.this, interpolation="lower"),
            c.ReduceFuncs.Percentile(51, c.this, interpolation="lower"),
            c.ReduceFuncs.Percentile(100, c.this, interpolation="lower"),
            #
            c.ReduceFuncs.Percentile(0, c.this, interpolation="higher"),
            c.ReduceFuncs.Percentile(49, c.this, interpolation="higher"),
            c.ReduceFuncs.Percentile(50, c.this, interpolation="higher"),
            c.ReduceFuncs.Percentile(51, c.this, interpolation="higher"),
            c.ReduceFuncs.Percentile(100, c.this, interpolation="higher"),
            #
            c.ReduceFuncs.Percentile(0, c.this, interpolation="midpoint"),
            c.ReduceFuncs.Percentile(49, c.this, interpolation="midpoint"),
            c.ReduceFuncs.Percentile(50, c.this, interpolation="midpoint"),
            c.ReduceFuncs.Percentile(51, c.this, interpolation="midpoint"),
            c.ReduceFuncs.Percentile(100, c.this, interpolation="midpoint"),
            #
            c.ReduceFuncs.Percentile(0, c.this, interpolation="nearest"),
            c.ReduceFuncs.Percentile(49, c.this, interpolation="nearest"),
            c.ReduceFuncs.Percentile(50, c.this, interpolation="nearest"),
            c.ReduceFuncs.Percentile(51, c.this, interpolation="nearest"),
            c.ReduceFuncs.Percentile(100, c.this, interpolation="nearest"),
        )
    ).gen_converter()
    assert converter(range(9, -1, -1)) == (
        # linear
        0,
        4.41,
        4.5,
        4.59,
        9,
        # lower
        0,
        4,
        4,
        4,
        9,
        # higher
        0,
        5,
        5,
        5,
        9,
        # midpoint
        0,
        4.5,
        4.5,
        4.5,
        9,
        # nearest
        0,
        4,
        4,
        5,
        9,
    )

    with pytest.raises(TypeError):
        c.ReduceFuncs.Percentile("asd", c.this)
    with pytest.raises(ValueError):
        c.ReduceFuncs.Percentile(200, c.this)
    with pytest.raises(ValueError):
        c.ReduceFuncs.Percentile(10, c.this, interpolation="asd")


def test_group_by_percentile():
    input_data = [
        {"key": key, "value": value}
        for index, key in enumerate("abc")
        for value in range(index + 90, -1, -1)
    ]
    c_round = c.call_func(round, c.this, 2)
    result = (
        c.group_by(c.item("key"))
        .aggregate(
            {
                "key": c.item("key"),
                "min": c.ReduceFuncs.Percentile(0, c.item("value")).pipe(
                    c_round
                ),
                "min2": c.ReduceFuncs.Percentile(
                    0, c.item("value"), where=c.and_(default=True)
                ).pipe(c_round),
                "percentile_5": c.ReduceFuncs.Percentile(
                    5, c.item("value")
                ).pipe(c_round),
                "median": c.ReduceFuncs.Percentile(50, c.item("value")).pipe(
                    c_round
                ),
                "percentile_95": c.ReduceFuncs.Percentile(
                    95, c.item("value")
                ).pipe(c_round),
                "max": c.ReduceFuncs.Percentile(100, c.item("value")).pipe(
                    c_round
                ),
            }
        )
        .execute(input_data, debug=False)
    )

    assert result == [
        {
            "key": "a",
            "max": 90,
            "median": 45.0,
            "min": 0.0,
            "min2": 0.0,
            "percentile_5": 4.5,
            "percentile_95": 85.5,
        },
        {
            "key": "b",
            "max": 91,
            "median": 45.5,
            "min": 0.0,
            "min2": 0.0,
            "percentile_5": 4.55,
            "percentile_95": 86.45,
        },
        {
            "key": "c",
            "max": 92,
            "median": 46.0,
            "min": 0.0,
            "min2": 0.0,
            "percentile_5": 4.6,
            "percentile_95": 87.4,
        },
    ]


def test_conditional_init_merges():
    converter = (
        c.group_by(c.item(0))
        .aggregate(
            [
                c.ReduceFuncs.First(c.item(1)),
                c.ReduceFuncs.First(c.item(2)),
                c.ReduceFuncs.Min(c.item(1)),
                c.ReduceFuncs.Max(c.item(1)),
                c.ReduceFuncs.Min(c.item(2)),
                c.ReduceFuncs.Max(c.item(2)),
                c.ReduceFuncs.DictMin(c.item(0), c.item(1)),
                c.ReduceFuncs.DictMin(c.item(0), c.item(2)),
                c.ReduceFuncs.DictMax(c.item(0), c.item(1)),
                c.ReduceFuncs.DictMax(c.item(0), c.item(2)),
                c.ReduceFuncs.MaxRow(c.item(2)),
                c.ReduceFuncs.MaxRow(c.item(2), where=c.item(0) == 1).item(-1),
            ]
        )
        .gen_converter(debug=False)
    )
    result = converter(
        [
            [1, 2, None],
            [1, 1, 4],
            [1, None, 3],
        ]
    )
    assert result == [
        [2, None, 1, 2, 3, 4, {1: 1}, {1: 3}, {1: 2}, {1: 4}, [1, 1, 4], 4]
    ]

    converter = (
        c.group_by(c.item(0))
        .aggregate(
            [
                c.ReduceFuncs.Min(c.item(1)),
                c.ReduceFuncs.Min(c.item(1)) + 1,
            ]
        )
        .gen_converter(debug=False)
    )
    assert get_code_str(converter).count(">") == 1


def test_reducer_defaultdict_locking():
    result = c.aggregate(
        (
            c.ReduceFuncs.DictArray(c.this, c.this),
            c.ReduceFuncs.DictSum(c.this, c.this),
            c.ReduceFuncs.DictSumOrNone(c.this, c.this),
        )
    ).execute(range(10))
    for data in result:
        with pytest.raises(KeyError):
            data[11]


def test_reducer_bad_number_of_expressions():
    with pytest.raises(ValueError):
        c.aggregate(c.ReduceFuncs.Sum()).gen_converter()

    with pytest.raises(ValueError):
        c.aggregate(
            c.ReduceFuncs.DictLast(c.this, c.this, c.this)
        ).gen_converter()

    assert c.aggregate(c.ReduceFuncs.DictCount((c.this, c.this))).execute(
        [1, 1, 2]
    ) == {1: 2, 2: 1}
    with pytest.raises(ValueError):
        c.aggregate(
            c.ReduceFuncs.DictCount(c.this, c.this, c.this)
        ).gen_converter()

    with pytest.raises(TypeError):
        c.reduce(lambda a, b: a + b, default=0)
