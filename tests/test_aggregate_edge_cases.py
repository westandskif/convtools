import random
import statistics
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from itertools import chain, cycle
from operator import eq
from typing import List, Tuple

import pytest

from convtools import conversion as c
from convtools._utils import CODE_FORMATTING_AVAILABLE, format_code

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
    pairs = [(v, w) for v, w in samples if v is not None and w is not None]
    return sum(v * w for v, w in pairs) / sum(w for _, w in pairs)


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


def test_weighted_average_none_weight():
    """None weights skip the row (excluded from numerator and denominator)."""
    data = [
        {"v": 10, "w": None},
        {"v": 20, "w": 1},
    ]
    assert (
        c.aggregate(
            c.ReduceFuncs.Average(c.item("v"), weight=c.item("w"))
        ).execute(data)
        == 20.0
    )

    # None weight combined with where= filter still works
    data_where = [
        {"v": 10, "w": None, "ok": True},
        {"v": 30, "w": 1, "ok": False},
        {"v": 20, "w": 1, "ok": True},
    ]
    assert (
        c.aggregate(
            c.ReduceFuncs.Average(
                c.item("v"), weight=c.item("w"), where=c.item("ok")
            )
        ).execute(data_where)
        == 20.0
    )

    # group_by path uses different reducer codegen
    data_grouped = [
        {"g": "a", "v": 10, "w": None},
        {"g": "a", "v": 20, "w": 1},
        {"g": "b", "v": 5, "w": None},
        {"g": "b", "v": 15, "w": 2},
    ]
    result = (
        c.group_by(c.item("g"))
        .aggregate(
            {
                "g": c.item("g"),
                "avg": c.ReduceFuncs.Average(c.item("v"), weight=c.item("w")),
            }
        )
        .execute(data_grouped)
    )
    assert {row["g"]: row["avg"] for row in result} == {"a": 20.0, "b": 15.0}

    # All weights None → weight sum is 0, returns default
    assert (
        c.aggregate(
            c.ReduceFuncs.Average(c.item("v"), weight=c.item("w"))
        ).execute([{"v": 1, "w": None}, {"v": 2, "w": None}])
        is None
    )
    assert (
        c.aggregate(
            c.ReduceFuncs.Average(c.item("v"), weight=c.item("w"), default=-1)
        ).execute([{"v": 1, "w": None}, {"v": 2, "w": None}])
        == -1
    )


def test_weighted_average_where_skips_row_before_value():
    assert (
        c.aggregate(
            c.ReduceFuncs.Average(c.item("v"), c.item("w"), where=c.item("ok"))
        ).execute([{"ok": False}])
        is None
    )

    def boom(_x):
        raise AssertionError("value evaluated on excluded row")

    assert (
        c.aggregate(
            c.ReduceFuncs.Average(
                c.call_func(boom, c.item("v")),
                c.item("w"),
                where=c.item("ok"),
            )
        ).execute([{"ok": False, "v": 1, "w": 1}])
        is None
    )


def test_weighted_average_skips_none_value_and_weight():
    avg = c.aggregate(c.ReduceFuncs.Average(c.item(0), c.item(1)))
    assert avg.execute([(None, 2), (None, 3)]) is None
    assert avg.execute([(1, 2), (None, 3), (3, 1)]) == 5 / 3
    assert avg.execute([(1, None), (3, 1)]) == 3.0

    data = [(None, 1), (1, 1), (None, 1), (2, 1), (0, 1), (3, 1)]
    assert c.aggregate(c.ReduceFuncs.Average(c.item(0))).execute(
        data
    ) == c.aggregate(c.ReduceFuncs.Average(c.item(0), c.item(1))).execute(data)


def test_weighted_average_group_key_and_callable_default():
    assert c.group_by(c.item(0)).aggregate(
        c.ReduceFuncs.Average(c.item(1), weight=c.item(2), default=c.item(0))
    ).execute([(1, 2, 0)]) == [1]
    assert (
        c.aggregate(
            c.ReduceFuncs.Average(c.item(0), weight=c.item(1), default=list)
        ).execute([])
        is list
    )


class _MutatingWeight:
    def __init__(self, value):
        self.value = value
        self.iadd_called = False

    def __iadd__(self, other):
        self.iadd_called = True
        self.value += getattr(other, "value", other)
        return self

    def __add__(self, other):
        return _MutatingWeight(self.value + getattr(other, "value", other))

    def __mul__(self, other):
        return _MutatingWeight(self.value * getattr(other, "value", other))

    def __rmul__(self, other):
        return _MutatingWeight(getattr(other, "value", other) * self.value)

    def __truediv__(self, other):
        return self.value / getattr(other, "value", other)


def test_weighted_average_does_not_mutate_weight_objects():
    weights = [_MutatingWeight(1), _MutatingWeight(3)]
    data = [{"v": 2, "w": weights[0]}, {"v": 4, "w": weights[1]}]
    result = c.aggregate(
        {
            "avg": c.ReduceFuncs.Average(c.item("v"), weight=c.item("w")),
            "ws": c.ReduceFuncs.Array(c.item("w")),
        }
    ).execute(data)
    assert result["avg"] == 3.5
    assert result["ws"] is not None
    assert [w.value for w in weights] == [1, 3]
    assert not any(w.iadd_called for w in weights)
    assert [w.value for w in result["ws"]] == [1, 3]
    assert not any(w.iadd_called for w in result["ws"])


def _count_row_item(code_str, key):
    return code_str.count('row_["%s"]' % key) + code_str.count(
        "row_['%s']" % key
    )


def test_weighted_average_evaluates_value_and_weight_once():
    R = c.ReduceFuncs
    v, w = c.item("v"), c.item("w")
    spec = c.aggregate(R.Average(v, weight=w))
    code_str = get_code_str(spec.gen_converter())
    n_loops = code_str.count("for row_")
    assert n_loops >= 1
    assert _count_row_item(code_str, "v") == n_loops
    assert _count_row_item(code_str, "w") == n_loops

    spec = c.group_by(c.item("g")).aggregate(
        R.Average(v, weight=w, where=c.item("ok"))
    )
    code_str = get_code_str(spec.gen_converter())
    n_loops = code_str.count("for row_")
    assert n_loops >= 1
    assert _count_row_item(code_str, "v") == n_loops
    assert _count_row_item(code_str, "w") == n_loops

    spec = c.group_by(c.item("g")).aggregate(
        {
            "avg": R.Average(v, weight=w),
            "s": R.Sum(v),
        }
    )
    code_str = get_code_str(spec.gen_converter())
    n_loops = code_str.count("for row_")
    assert n_loops >= 1
    assert _count_row_item(code_str, "v") == n_loops
    assert "_tmp" in code_str


def test_sum_aggregate_group_by_parity():
    data = [timedelta(1), timedelta(2)]
    expected = timedelta(days=3)
    assert c.aggregate(c.ReduceFuncs.Sum(c.this)).execute(data) == expected
    assert (
        c.group_by().aggregate(c.ReduceFuncs.Sum(c.this)).execute(data)
        == expected
    )
    assert c.aggregate(c.ReduceFuncs.Sum(c.this)).execute([]) == 0
    assert c.aggregate(c.ReduceFuncs.Sum(c.this)).execute([None]) == 0
    assert (
        c.aggregate(c.ReduceFuncs.Sum(c.this, where=c.this > 1)).execute(
            [1, 2, 3]
        )
        == 5
    )
    assert c.aggregate(c.ReduceFuncs.Sum(c.this)).execute(
        [Decimal("1.1"), Decimal("2.2")]
    ) == Decimal("3.3")
    assert c.aggregate(c.ReduceFuncs.Sum(c.this)).execute(["a", "b"]) == "ab"
    assert (
        c.group_by().aggregate(c.ReduceFuncs.Sum(c.this)).execute(["a", "b"])
        == "ab"
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
        [x[0] for x in Counter(x[1] for x in series).most_common(k)],
    )


def test_top_k_extra():
    assert c.aggregate(c.ReduceFuncs.TopK(2, c.this)).execute(
        [None] * 4 + [3, 3, 3, 2, 2, 1],
        debug=False,
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
                x[0]
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
        c.item(1)
        .pipe(c.ReduceFuncs.Sum(c.this))
        .pipe(c.this, label_output="count")
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


def test_array_sorted():
    assert c.aggregate(c.ReduceFuncs.ArraySorted(c.this)).execute(
        [3, 1, 2]
    ) == [1, 2, 3]
    assert c.aggregate(
        c.ReduceFuncs.ArraySorted(c.this, reverse=True)
    ).execute([3, 1, 2]) == [3, 2, 1]
    assert c.aggregate(
        c.ReduceFuncs.ArraySorted(c.this, key=c.sorting_key(c.this.desc()))
    ).execute([3, 1, 2]) == [3, 2, 1]


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

    f = c.aggregate(c.ReduceFuncs.Percentile(50, c.this)).gen_converter()
    assert f([4, 2, 3, 1]) == 2.5
    assert f([None, 4, 2, 3, 1]) == 2.5

    assert (
        c.aggregate(
            c.ReduceFuncs.Percentile(70, c.this, interpolation="higher")
        ).execute(list(range(11)))
        == 7
    )


def _percentile_index_fraction(n, p):
    return Fraction((n - 1) * p, 100)


def _ref_percentile_lower(data, p):
    return data[int(_percentile_index_fraction(len(data), p))]


def _ref_percentile_higher(data, p):
    index = _percentile_index_fraction(len(data), p)
    left_index = int(index)
    if Fraction(left_index) == index:
        return data[left_index]
    return data[left_index + 1]


def _ref_percentile_nearest(data, p):
    return data[round((len(data) - 1) * p / 100)]


def _ref_percentile_midpoint(data, p):
    index = _percentile_index_fraction(len(data), p)
    left_index = int(index)
    if Fraction(left_index) == index:
        return data[left_index]
    left_value = data[left_index]
    return left_value + (data[left_index + 1] - left_value) / 2


def test_percentile_integer_index_matches_fraction():
    interpolations = (
        ("lower", _ref_percentile_lower),
        ("higher", _ref_percentile_higher),
        ("nearest", _ref_percentile_nearest),
        ("midpoint", _ref_percentile_midpoint),
    )
    converters = {
        (interpolation, p): c.aggregate(
            c.ReduceFuncs.Percentile(p, c.this, interpolation=interpolation)
        ).gen_converter()
        for interpolation, _ in interpolations
        for p in range(101)
    }
    for n in range(1, 151):
        data = list(range(n))
        for interpolation, reference in interpolations:
            for p in range(101):
                got = converters[(interpolation, p)](data)
                expected = reference(data, p)
                if interpolation == "midpoint":
                    assert got == pytest.approx(expected)
                else:
                    assert got == expected


@pytest.mark.parametrize("n", range(1, 12))
@pytest.mark.parametrize("p", range(0, 101, 5))
def test_percentile_nearest_half_to_even(n, p):
    data = list(range(n))
    got = c.aggregate(
        c.ReduceFuncs.Percentile(p, c.this, interpolation="nearest")
    ).execute(data)
    assert got == data[round((n - 1) * p / 100)]


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


# test_group_by_reducers_reuse
# test_aggregate_reducers_reuse
def test_group_by_dict_reducer_optimization():
    def gen_reducers(idx_start, number, *, with_side_effect):
        return {
            f"f{idx_start+i:02}": (
                c.ReduceFuncs.DictSum(
                    c.item(0, idx_start + i), c.item(1, idx_start + i)
                )
                if with_side_effect
                else c.ReduceFuncs.Sum(c.item(1, idx_start + i))
            )
            for i in range(number)
        }

    get_data_by_purchaser = c.aggregate(
        {
            **gen_reducers(0, 3, with_side_effect=False),
            **gen_reducers(3, 3, with_side_effect=True),
            **gen_reducers(6, 3, with_side_effect=False),
            **gen_reducers(9, 3, with_side_effect=True),
        }
    )

    converter = get_data_by_purchaser.gen_converter(debug=False)
    code_str = format_code(get_code_str(converter))
    data = [
        [
            list(range(12)),
            list(range(12, 24)),
        ],
        [
            list(range(24, 36)),
            list(range(36, 48)),
        ],
    ]
    result = converter(data)
    assert result == {
        "f00": 48,
        "f01": 50,
        "f02": 52,
        "f03": {3: 15, 27: 39},
        "f04": {4: 16, 28: 40},
        "f05": {5: 17, 29: 41},
        "f06": 60,
        "f07": 62,
        "f08": 64,
        "f09": {9: 21, 33: 45},
        "f10": {10: 22, 34: 46},
        "f11": {11: 23, 35: 47},
    }
    assert "_tmp0_ = row_[1]" in code_str
    assert code_str.count("row_[1]") == 2
    assert code_str.count("row_[(0)]") + code_str.count("row_[0]") >= 1


# FirstN / LastN reducer tests


@pytest.mark.parametrize("n", [0, -1, -100])
def test_firstn_lastn_invalid_n(n):
    with pytest.raises(ValueError):
        c.ReduceFuncs.FirstN(n, c.this)
    with pytest.raises(ValueError):
        c.ReduceFuncs.LastN(n, c.this)


@pytest.mark.parametrize("n", ["abc", 1.5, c.item(0)])
def test_firstn_lastn_non_integer_n(n):
    with pytest.raises(TypeError):
        c.ReduceFuncs.FirstN(n, c.this)
    with pytest.raises(TypeError):
        c.ReduceFuncs.LastN(n, c.this)


def test_firstn_aggregate():
    assert c.aggregate(c.ReduceFuncs.FirstN(3, c.this)).execute(range(10)) == [
        0,
        1,
        2,
    ]


def test_lastn_aggregate():
    assert c.aggregate(c.ReduceFuncs.LastN(3, c.this)).execute(range(10)) == [
        7,
        8,
        9,
    ]


def test_firstn_empty():
    assert c.aggregate(c.ReduceFuncs.FirstN(5, c.this)).execute([]) is None


def test_lastn_empty():
    assert c.aggregate(c.ReduceFuncs.LastN(5, c.this)).execute([]) is None


def test_firstn_n_exceeds_items():
    assert c.aggregate(c.ReduceFuncs.FirstN(100, c.this)).execute(
        range(5)
    ) == [0, 1, 2, 3, 4]


def test_lastn_n_exceeds_items():
    assert c.aggregate(c.ReduceFuncs.LastN(100, c.this)).execute(range(5)) == [
        0,
        1,
        2,
        3,
        4,
    ]


def test_firstn_with_default():
    assert (
        c.aggregate(c.ReduceFuncs.FirstN(3, c.this, default=[])).execute([])
        == []
    )


def test_lastn_with_default():
    assert (
        c.aggregate(c.ReduceFuncs.LastN(3, c.this, default=[])).execute([])
        == []
    )


# DictFirstN / DictLastN reducer tests


@pytest.mark.parametrize("n", [0, -1, -100])
def test_dictfirstn_dictlastn_invalid_n(n):
    with pytest.raises(ValueError):
        c.ReduceFuncs.DictFirstN(n, c.item(0), c.item(1))
    with pytest.raises(ValueError):
        c.ReduceFuncs.DictLastN(n, c.item(0), c.item(1))


@pytest.mark.parametrize("n", ["abc", 1.5, c.item(0)])
def test_dictfirstn_dictlastn_non_integer_n(n):
    with pytest.raises(TypeError):
        c.ReduceFuncs.DictFirstN(n, c.item(0), c.item(1))
    with pytest.raises(TypeError):
        c.ReduceFuncs.DictLastN(n, c.item(0), c.item(1))


def test_dictfirstn_aggregate():
    data = [("a", 1), ("a", 2), ("a", 3), ("b", 10), ("b", 20)]
    result = c.aggregate(
        c.ReduceFuncs.DictFirstN(2, c.item(0), c.item(1))
    ).execute(data)
    assert result == {"a": [1, 2], "b": [10, 20]}


def test_dictlastn_aggregate():
    data = [("a", 1), ("a", 2), ("a", 3), ("b", 10), ("b", 20)]
    result = c.aggregate(
        c.ReduceFuncs.DictLastN(2, c.item(0), c.item(1))
    ).execute(data)
    assert result == {"a": [2, 3], "b": [10, 20]}


def test_dictfirstn_empty():
    assert (
        c.aggregate(c.ReduceFuncs.DictFirstN(5, c.item(0), c.item(1))).execute(
            []
        )
        is None
    )


def test_dictlastn_empty():
    assert (
        c.aggregate(c.ReduceFuncs.DictLastN(5, c.item(0), c.item(1))).execute(
            []
        )
        is None
    )


def test_dictfirstn_n_exceeds_items():
    data = [("a", 1), ("a", 2), ("b", 10)]
    result = c.aggregate(
        c.ReduceFuncs.DictFirstN(100, c.item(0), c.item(1))
    ).execute(data)
    assert result == {"a": [1, 2], "b": [10]}


def test_dictlastn_n_exceeds_items():
    data = [("a", 1), ("a", 2), ("b", 10)]
    result = c.aggregate(
        c.ReduceFuncs.DictLastN(100, c.item(0), c.item(1))
    ).execute(data)
    assert result == {"a": [1, 2], "b": [10]}


def test_dictfirstn_with_default():
    assert (
        c.aggregate(
            c.ReduceFuncs.DictFirstN(3, c.item(0), c.item(1), default={})
        ).execute([])
        == {}
    )


def test_dictlastn_with_default():
    assert (
        c.aggregate(
            c.ReduceFuncs.DictLastN(3, c.item(0), c.item(1), default={})
        ).execute([])
        == {}
    )


def test_dictfirstn_with_where():
    data = [("a", 1), ("a", 2), ("a", 3), ("a", 4), ("b", 10), ("b", 20)]
    result = c.aggregate(
        c.ReduceFuncs.DictFirstN(2, c.item(0), c.item(1), where=c.item(1) > 1)
    ).execute(data)
    assert result == {"a": [2, 3], "b": [10, 20]}


def test_dictlastn_with_where():
    data = [("a", 1), ("a", 2), ("a", 3), ("a", 4), ("b", 10), ("b", 20)]
    result = c.aggregate(
        c.ReduceFuncs.DictLastN(2, c.item(0), c.item(1), where=c.item(1) < 20)
    ).execute(data)
    assert result == {"a": [3, 4], "b": [10]}


def test_reducer_percent_in_generated_code():
    """Literal % in generated expressions must not break template % kwargs."""
    data = [1, 2, 3, 4]

    # Bug A: % inside an expression arg
    assert (
        c.aggregate(
            c.reduce(lambda a, b: a + b, c.this % 3, initial=0)
        ).execute(data)
        == 4
    )

    # Bug A: % inside the reduce InlineExpr itself
    assert (
        c.aggregate(
            c.reduce(c.inline_expr("({0} + {1}) % 100"), c.this, initial=0)
        ).execute(data)
        == 10
    )

    # Bug B: % inside initial (via call_func so it is not an InlineExpr)
    assert (
        c.aggregate(
            c.reduce(
                lambda a, b: a + b,
                c.this,
                initial=c.call_func(lambda x: x, c.this % 3),
                default=0,
            )
        ).execute(data)
        == 11
    )

    # Bug B: built-in reducer initial with % via group_by
    # (bare c.aggregate(Sum(...)) shortcut ignores row-dependent initial)
    assert c.group_by(c.item(0)).aggregate(
        c.ReduceFuncs.Sum(
            c.item(1),
            initial=c.call_func(lambda x: x, c.item(1) % 3),
            default=0,
        )
    ).execute([(1, 1), (1, 2), (2, 5)]) == [4, 7]

    # Bug C: operator-built InlineExpr as initial must keep its args
    # (depends on input → default is required; auto-calling it would wipe args)
    assert (
        c.aggregate(
            c.reduce(
                lambda a, b: a + b,
                c.this,
                initial=c.this % 3,
                default=0,
            )
        ).execute(data)
        == 11
    )
    with pytest.raises(ValueError):
        c.reduce(lambda a, b: a + b, c.this, initial=c.this % 3)

    # Emitted code should contain a single % (not escaped %%)
    code_str = get_code_str(
        c.aggregate(
            c.reduce(lambda a, b: a + b, c.this % 3, initial=0)
        ).gen_converter()
    )
    assert "(row_ % (3))" in code_str
    assert " %% 3" not in code_str


def test_single_reducer_aggregate_honors_initial():
    """Bare reducer shortcut must not drop initial= (tuple form already works)."""
    R = c.ReduceFuncs
    data = [1, 2]
    assert c.aggregate(R.Sum(c.this, initial=100)).execute(data) == 103
    assert c.aggregate((R.Sum(c.this, initial=100),)).execute(data) == (103,)
    assert c.aggregate(R.Array(c.this, initial=lambda: [100])).execute(
        data
    ) == [100, 1, 2]
    assert (
        c.group_by().aggregate(R.Sum(c.this, initial=100)).execute(data) == 103
    )


def test_sum_owned_list_accumulator():
    R = c.ReduceFuncs
    n = 32
    data = [[i] for i in range(n)]
    snapshot = [row[:] for row in data]
    assert c.aggregate(R.Sum(c.this, initial=list)).execute(data) == list(
        range(n)
    )
    assert data == snapshot
    assert c.aggregate(R.SumOrNone(c.this, initial=list)).execute(
        data
    ) == list(range(n))
    assert data == snapshot

    grouped = (
        c.group_by(c.item(0))
        .aggregate(R.Sum(c.item(1), initial=list))
        .execute([(0, [1]), (0, [2]), (1, [10]), (1, [20])])
    )
    assert grouped == [[1, 2], [10, 20]]

    owned_code = get_code_str(
        c.aggregate(R.Sum(c.this, initial=list)).gen_converter()
    )
    assert "agg_data__v0 += " in owned_code
    unowned_code = get_code_str(c.aggregate(R.Sum(c.this)).gen_converter())
    assert "agg_data__v0 += " not in unowned_code
    const_initial_code = get_code_str(
        c.aggregate(R.Sum(c.this, initial=[])).gen_converter()
    )
    assert "agg_data__v0 += " not in const_initial_code


def test_reducer_callable_initial_and_default():
    """Plain Python callables used as initial/default still get auto-called."""
    assert (
        c.aggregate(
            c.reduce(lambda a, b: a + b, c.this, initial=lambda: 0)
        ).execute([1, 2, 3])
        == 6
    )
    assert (
        c.aggregate(
            c.reduce(lambda a, b: a + b, c.this, initial=int, default=0)
        ).execute([1, 2, 3])
        == 6
    )
    assert (
        c.aggregate(c.ReduceFuncs.Array(c.this, default=list)).execute([])
        == []
    )


def test_piped_reducer_where_initial_and_maxrow():
    R = c.ReduceFuncs
    data = [{"a": 1}, {"a": 2}, {"a": 3}]
    assert c.aggregate(
        c.item("a").pipe(R.Array(c.this, where=c.this > 1))
    ).execute(data) == [2, 3]
    assert (
        c.aggregate(c.item("a").pipe(R.Sum(c.this, where=c.this > 1))).execute(
            data
        )
        == 5
    )
    assert c.group_by(c.item("g")).aggregate(
        c.item("a").pipe(R.Array(c.this, where=c.this > 1))
    ).execute([{"g": 0, "a": 1}, {"g": 0, "a": 2}, {"g": 0, "a": 3}]) == [
        [2, 3]
    ]
    assert c.group_by(c.item("g")).aggregate(
        c.item("a").pipe(R.Sum(c.this, where=c.this > 1))
    ).execute([{"g": 0, "a": 1}, {"g": 0, "a": 2}, {"g": 0, "a": 3}]) == [5]
    assert (
        c.aggregate(
            c.item("a").pipe(
                c.reduce(lambda a, b: a + b, c.this, initial=0, default=0)
            )
        ).execute([{"a": 1}, {"a": 2}])
        == 3
    )
    assert (
        c.aggregate(
            c.item("a").pipe(
                c.reduce(
                    lambda a, b: a + b,
                    c.this,
                    initial=c.this * 10,
                    default=0,
                )
            )
        ).execute([{"a": 1}, {"a": 2}])
        == 13
    )
    assert c.aggregate(c.item("a").pipe(R.MaxRow(c.item("x")))).execute(
        [{"a": {"x": 1}}, {"a": {"x": 5}}]
    ) == {"x": 5}
