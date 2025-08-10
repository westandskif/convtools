from decimal import Decimal

import pytest

from convtools import conversion as c


def test_hints():
    for conv in [
        -c.item(0),
        c.this + 0,
        c.item(0) + 1,
        c.item(0) * 1,
        c.item(0) - 1,
        c.item(0) / 1,
        c.item(0) % 1,
        c.item(0) // 1,
        c.max(c.this, c.this + 1),
        c.min(c.this, c.this + 1),
        c.call_func(min, c.this),
        c.call_func(max, c.this),
        c.call_func(sum, c.this),
        c.call_func(len, c.this),
        c.call_func(int, c.this),
        c.call_func(float, c.this),
        c.call_func(Decimal, c.this),
        c.naive(min).call(c.this),
        c.naive(max).call(c.this),
        c.naive(sum).call(c.this),
        c.naive(len).call(c.this),
        c.naive(int).call(c.this),
        c.naive(float).call(c.this),
        c.naive(Decimal).call(c.this),
        c.this.pipe(c.call_func(Decimal, c.this)),
        c.this.pipe(c.this.as_type(Decimal)),
        (c.this + 0).pipe(c.this),
    ]:
        assert conv.has_hint(c.BaseConversion.OutputHints.NOT_NONE)

    assert (
        not c.naive([]).call().has_hint(c.BaseConversion.OutputHints.NOT_NONE)
    )


@pytest.mark.parametrize(
    [
        "reducer_cls",
        "data",
        "expected_result",
    ],
    [
        (c.ReduceFuncs.Sum, list(range(5)), 10),
        (c.ReduceFuncs.SumOrNone, list(range(5)), 10),
        (c.ReduceFuncs.Max, list(range(5, 0, -1)), 5),
        (c.ReduceFuncs.MaxRow, list(range(5, 0, -1)), 5),
        (c.ReduceFuncs.Min, list(range(5)), 0),
        (c.ReduceFuncs.MinRow, list(range(5)), 0),
    ],
)
@pytest.mark.parametrize(
    "conv", [c.this, c.this.as_type(int), c.call_func(lambda x: x, c.this)]
)
def test_reducers_with_hints(reducer_cls, data, expected_result, conv):
    converter = c.aggregate(reducer_cls(conv)).gen_converter(debug=False)
    result = converter(data)
    assert result == expected_result

    converter = (
        c.group_by(c.call_func(lambda x: x, 1))
        .aggregate(reducer_cls(conv))
        .gen_converter()
    )
    result = converter(data)
    assert result[0] == expected_result


@pytest.mark.parametrize(
    [
        "reducer_cls",
        "data",
        "expected_result",
    ],
    [
        (c.ReduceFuncs.DictSum, list(range(6)), {0: 6, 1: 9}),
        (c.ReduceFuncs.DictSumOrNone, list(range(6)), {0: 6, 1: 9}),
        (c.ReduceFuncs.DictMax, list(range(6)), {0: 4, 1: 5}),
        (c.ReduceFuncs.DictMin, list(range(6)), {0: 0, 1: 1}),
        (c.ReduceFuncs.DictCountDistinct, list(range(6)), {0: 3, 1: 3}),
    ],
)
@pytest.mark.parametrize(
    "value_conv",
    [c.this, c.this.as_type(int), c.call_func(lambda x: x, c.this)],
)
def test_dict_reducers_with_hints(
    reducer_cls, data, expected_result, value_conv
):
    converter = c.aggregate(reducer_cls(c.this % 2, value_conv)).gen_converter(
        debug=False
    )
    result = converter(data)
    assert result == expected_result

    converter = (
        c.group_by(c.call_func(lambda x: x, 1))
        .aggregate(reducer_cls(c.this % 2, value_conv))
        .gen_converter()
    )
    result = converter(data)
    assert result[0] == expected_result


def test_combination_of_reducers_with_hints():
    agg_config = {
        "a": c.ReduceFuncs.Sum(c.item(0)),
        "b": c.ReduceFuncs.Sum(c.item(1)),
        "c": c.ReduceFuncs.Sum(c.item(0) + c.item(1)),
        "d": c.ReduceFuncs.Sum(c.item(0).as_type(int)),
        "e": c.ReduceFuncs.Min(c.this),
        "f": c.ReduceFuncs.Max(c.this),
        "g": c.ReduceFuncs.Max(c.item(0) + c.item(1)),
        "k": c.ReduceFuncs.Max(c.item(0).as_type(int)),
    }
    converter = c.aggregate(agg_config).gen_converter(debug=False)
    result = converter(zip(range(5), range(5)))
    converter_2 = (
        c.group_by(c.call_func(lambda x: x, 1))
        .aggregate(agg_config)
        .item(0)
        .gen_converter(debug=False)
    )
    result_2 = converter(zip(range(5), range(5)))
    assert (
        result
        == {
            "a": 10,
            "b": 10,
            "c": 20,
            "d": 10,
            "e": (0, 0),
            "f": (4, 4),
            "g": 8,
            "k": 4,
        }
        and result == result_2
    )
