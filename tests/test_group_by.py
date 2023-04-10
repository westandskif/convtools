import re
from datetime import date
from types import GeneratorType

import pytest

from convtools import conversion as c
from convtools._base import LazyEscapedString, Namespace

from .utils import get_code_str


def test_group_by_with_attr_lookups():
    converter = (
        c.group_by(c.attr("original_payment", "source", default=None))
        .aggregate(
            (
                c.attr("original_payment", "source", default=None),
                c.ReduceFuncs.Max(c.attr("date_original")),
            )
        )
        .gen_converter()
    )

    class A:
        class original_payment:
            source = 1

        date_original = 100

    class B:
        date_original = 10

    assert converter([A, B]) == [(1, 100), (None, 10)]

    converter = (
        c.group_by(c.call_func(int, c.this).pipe((c.this, c.this)))
        .aggregate(
            (
                c.call_func(int, c.this).pipe((c.this, c.this)),
                c.ReduceFuncs.Count(),
            )
        )
        .gen_converter()
    )
    assert converter(["1", "2"]) == [((1, 1), 1), ((2, 2), 1)]


def test_manually_defined_reducers():
    data = [
        {"name": "John", "category": "Games", "debit": 10, "balance": 90},
        {"name": "John", "category": "Games", "debit": 200, "balance": -110},
        {"name": "John", "category": "Food", "debit": 30, "balance": -140},
        {"name": "John", "category": "Games", "debit": 300, "balance": 0},
        {"name": "Nick", "category": "Food", "debit": 7, "balance": 50},
        {"name": "Nick", "category": "Games", "debit": 18, "balance": 32},
        {"name": "Bill", "category": "Games", "debit": 18, "balance": 120},
    ]
    grouper_base = c.group_by(c.item("name")).aggregate(
        c.reduce(
            lambda a, b: a + b,
            c.item(c.input_arg("group_key")),
            initial=int,
            default=int,
            where=None,
        )
    )
    grouper = grouper_base.filter(c.this > 20).gen_converter(
        signature="data_, group_key='debit'"
    )
    assert grouper(data) == [540, 25]
    assert list(grouper(data, group_key="balance")) == [82, 120]

    grouper = grouper_base.filter((c.this > 20), cast=list).gen_converter(
        signature="data_, group_key='debit'", debug=False
    )
    assert grouper(data) == [540, 25]

    grouper = grouper_base.filter((c.this > 20), cast=set).gen_converter(
        signature="data_, group_key='debit'", debug=False
    )
    assert grouper(data, group_key="balance") == {82, 120}

    assert c.group_by(c.item("name")).aggregate(
        {
            "name": c.item("name"),
            "value": c.reduce(
                lambda a, b: max(a, b),
                c.item(c.input_arg("group_key")),
                initial=int,
                default=int,
                where=c.item(c.input_arg("group_key")) > 10,
            ),
        }
    ).execute(data, group_key="debit") == [
        {"name": "John", "value": 300},
        {"name": "Nick", "value": 18},
        {"name": "Bill", "value": 18},
    ]


def test_grouping():
    data = [
        {"name": "John", "category": "Games", "debit": 10, "balance": 90},
        {"name": "John", "category": "Games", "debit": 200, "balance": -110},
        {"name": "John", "category": "Food", "debit": 30, "balance": -140},
        {"name": "John", "category": "Games", "debit": 300, "balance": 0},
        {"name": "Nick", "category": "Food", "debit": 7, "balance": 50},
        {"name": "Nick", "category": "Games", "debit": 18, "balance": 32},
        {"name": "Bill", "category": "Games", "debit": 18, "balance": 120},
    ]
    result = (
        c.group_by(c.item("name"))
        .aggregate(
            (
                c.item("name"),
                c.item("name").call_method("lower"),
                c.call_func(str.lower, c.item("name")),
                c.reduce(
                    lambda a, b: a + b,
                    c.item("debit"),
                    initial=c.input_arg("arg1"),
                    unconditional_init=True,
                ),
                c.reduce(
                    c.inline_expr("{0} + {1}"),
                    c.item("debit"),
                    initial=lambda: 100,
                    unconditional_init=True,
                ),
                c.reduce(
                    max,
                    c.item("debit"),
                    initial=c.item("debit"),
                    default=c.input_arg("arg1"),
                    where=c.call_func(lambda x: x < 0, c.item("balance")),
                ),
                c.call_func(
                    lambda max_debit, n: max_debit * n,
                    c.reduce(
                        max,
                        c.item("debit"),
                        initial=c.item("debit"),
                        default=0,
                        where=c.call_func(lambda x: x < 0, c.item("balance")),
                    ),
                    1000,
                ),
                c.call_func(
                    lambda max_debit, n: max_debit * n,
                    c.reduce(
                        c.ReduceFuncs.Max,
                        c.item("debit"),
                        default=1000,
                        where=c.inline_expr("{0} > {1}").pass_args(
                            c.item("balance"),
                            c.input_arg("arg2"),
                        ),
                    ),
                    -1,
                ),
                c.reduce(c.ReduceFuncs.MaxRow, c.item("debit")).item(
                    "balance"
                ),
                c.reduce(c.ReduceFuncs.MinRow, c.item("debit")).item(
                    "balance"
                ),
            )
        )
        .sort(key=lambda t: t[0].lower(), reverse=True)
        .execute(data, arg1=100, arg2=0, debug=False)
    )

    # fmt: off
    assert result == [('Nick', 'nick', 'nick', 125, 125, 100, 0, -18, 32, 50),
                     ('John', 'john', 'john', 640, 640, 200, 200000, -10, 0, 90),
                     ('Bill', 'bill', 'bill', 118, 118, 100, 0, -18, 120, 120),]
    # fmt: on

    with pytest.raises(c.ConversionException):
        # there's a single group by field, while we use separate items
        # of this tuple in aggregate
        result = (
            c.group_by(c.item("name"))
            .aggregate(
                (
                    c.item("category"),
                    c.reduce(c.ReduceFuncs.Sum, c.item("debit")),
                )
            )
            .execute(data, debug=False)
        )

    aggregation = {
        c.call_func(
            tuple,
            c.ReduceFuncs.Array(c.item("name"), default=None),
        ): c.item("category").call_method("lower"),
        "count": c.ReduceFuncs.Count(),
        "max": c.ReduceFuncs.Max(c.item("debit")),
        "min": c.ReduceFuncs.Min(c.item("debit")),
        "count_distinct": c.ReduceFuncs.CountDistinct(c.item("name")),
        "array_agg_distinct": c.ReduceFuncs.ArrayDistinct(c.item("name")),
        "dict": c.ReduceFuncs.Dict(c.item("debit"), c.item("name")),
    }
    result = (
        c.group_by(c.item("category"))
        .aggregate(aggregation)
        .execute(data, debug=False)
    )
    result2 = (
        c.group_by(c.item("category"))
        .aggregate(c.dict(*aggregation.items()))
        .execute(data, debug=False)
    )
    # fmt: off
    assert result == result2 == [{'array_agg_distinct': ['John', 'Nick', 'Bill'],
          'count': 5,
          'count_distinct': 3,
          'dict': {10: 'John', 18: 'Bill', 200: 'John', 300: 'John'},
          'max': 300,
          'min': 10,
          ('John', 'John', 'John', 'Nick', 'Bill'): 'games'},
         {'array_agg_distinct': ['John', 'Nick'],
          'count': 2,
          'count_distinct': 2,
          'dict': {7: 'Nick', 30: 'John'},
          'max': 30,
          'min': 7,
          ('John', 'Nick'): 'food'}]
    # fmt: on
    result3 = (
        c.aggregate(c.ReduceFuncs.Sum(c.item("debit") + 0))
        .pipe(c.inline_expr("{0} + {1}").pass_args(c.this, c.this))
        .execute(data, debug=False)
    )
    assert result3 == 583 * 2

    by = c.item("name"), c.item("category")
    result4 = (
        c.group_by(*by)
        .aggregate(by + (c.ReduceFuncs.Sum(c.item("debit")),))
        .execute(data, debug=False)
    )
    # fmt: off
    assert result4 == [('John', 'Games', 510),
         ('John', 'Food', 30),
         ('Nick', 'Food', 7),
         ('Nick', 'Games', 18),
         ('Bill', 'Games', 18)]
    # fmt: on
    result5 = (
        c.group_by()
        .aggregate(c.ReduceFuncs.Sum(c.item("debit")))
        .execute(data, debug=False)
    )
    assert result5 == 583

    with pytest.raises(c.ConversionException):
        # there's a single group by field, while we use separate items
        # of this tuple in aggregate
        (
            c.group_by(by)
            .aggregate(by + (c.reduce(c.ReduceFuncs.Sum, c.item("debit")),))
            .execute(data, debug=False)
        )

    assert Namespace(
        c.aggregate(c.ReduceFuncs.Array(c.this.or_(LazyEscapedString("foo"))))
        + c.input_arg("tst"),
        {"foo": "tst"},
    ).execute(range(3), tst=[]) == [[], 1, 2]


# fmt: off
reducer_data1 = [
    {"name": "Bill", "debit": 100},
    {"name": "Bill", "debit": 50},
    {"name": "Nick", "debit": 1},
]
reducer_data2 = [
    {"name": "Bill", "debit": None},
    {"name": "Nick", "debit": 2},
]
reducer_data3 = [
    {"name": "Bill", "debit": 50},
    {"name": "Nick", "debit": 2},
    {"name": "Nick", "debit": 2},
]
reducer_data4 = [
    {"name": "Bill", "debit": 25},
    {"name": "Nick", "debit": 3},
]
@pytest.fixture
def reducers_in_out():
    return [
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(lambda a, b: a + b, c.item("debit"), initial=0),
        data=reducer_data1,
        output=[('Bill', 150), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.inline_expr("{} + {}"), c.item("debit"), initial=0),
        data=reducer_data1,
        output=[('Bill', 150), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Sum(c.item("debit")),
        data=reducer_data1,
        output=[('Bill', 150), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Sum(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 150), ('Nick', 3)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.SumOrNone(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', None), ('Nick', 3)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Max(c.item("debit")),
        data=reducer_data1,
        output=[('Bill', 100), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Max(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 100), ('Nick', 2)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.MaxRow(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', {'debit': 100, 'name': 'Bill'}),
                 ('Nick', {'debit': 2, 'name': 'Nick'})],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Min(c.item("debit")),
        data=reducer_data1,
        output=[('Bill', 50), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Min(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 50), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.MinRow(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', {'debit': 50, 'name': 'Bill'}),
                 ('Nick', {'debit': 1, 'name': 'Nick'})],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Count(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 2), ('Nick', 2)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Count(c.item("debit"), where=c.item("debit").is_(None)),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 0), ('Nick', 0)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Count(where=c.item("debit").is_(None)),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 1), ('Nick', 0)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.CountDistinct(c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3 + reducer_data4,
        output=[('Bill', 4), ('Nick', 3)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.First(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 100), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Last(c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', None), ('Nick', 2)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.Array(c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[('Bill', [100, 50, None, 50]), ('Nick', [1, 2, 2, 2])],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.ReduceFuncs.ArrayDistinct(c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[('Bill', [100, 50, None]), ('Nick', [1, 2])],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.Dict(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 50, 'Nick': 2})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictArray(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': [100, 50, None, 50], 'Nick': [1, 2, 2, 2]})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictArrayDistinct(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': [100, 50, None], 'Nick': [1, 2]})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictSum(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 200, 'Nick': 7})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictSumOrNone(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': None, 'Nick': 7})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictMax(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 100, 'Nick': 2})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictMin(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 50, 'Nick': 1})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictCount(c.item("name")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 4, 'Nick': 4})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictCount(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 3, 'Nick': 4})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictCountDistinct(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3 + reducer_data4,
        output=[(True, {'Bill': 4, 'Nick': 3})],
        raises=None,
        debug=False,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictFirst(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 100, 'Nick': 1})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.ReduceFuncs.DictLast(c.item("name"), c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3 + reducer_data4,
        output=[(True, {'Bill': 25, 'Nick': 3})],
        raises=None,
    ),

]
# fmt: on
def test_reducers(reducers_in_out):
    for config in reducers_in_out:
        converter = (
            c.group_by(config["groupby"])
            .aggregate((config["groupby"], config["reduce"]))
            .gen_converter(debug=config.get("debug", True))
        )

        if config["raises"]:
            with pytest.raises(config["raises"]):
                converter(config["data"])
        else:
            data = converter(config["data"])
            assert data == config["output"]


def test_base_reducer():
    assert c.aggregate(
        (
            c.reduce(lambda a, b: a + b, c.this, initial=0),
            c.reduce(c.naive(lambda a, b: a + b), c.this, initial=int),
            c.reduce(
                c.inline_expr("{0} + {1}"),
                c.this,
                initial=c.inline_expr("int()"),
                default=0,
            ),
            c.reduce(
                c.inline_expr("{0} + {1}"),
                c.this,
                initial=c(int),
                default=0,
            ),
            c.reduce(
                c.inline_expr("{0} + {1}"),
                c.this,
                initial=int,
                default=0,
            ),
        )
    ).filter(c.this > 5).as_type(list).gen_converter(debug=False)(
        [1, 2, 3]
    ) == [
        6,
        6,
        6,
        6,
        6,
    ]

    with pytest.raises(ValueError):
        c.aggregate(
            c.ReduceFuncs.Sum(c.reduce(c.ReduceFuncs.Count))
        ).gen_converter()
    with pytest.raises(ValueError):
        c.aggregate(
            c.ReduceFuncs.Sum(c.ReduceFuncs.Count() + 1)
        ).gen_converter()
    with pytest.raises(ValueError):
        c.aggregate(
            (c.ReduceFuncs.Count() + 2).pipe(c.ReduceFuncs.Sum(c.this) + 1)
        ).gen_converter()

    conv = c.aggregate(
        c.ReduceFuncs.DictArray(c.item(0), c.item(1))
    ).gen_converter(debug=False)
    data = [
        ("a", 1),
        ("a", 2),
        ("b", 3),
    ]
    result = {"a": [1, 2], "b": [3]}
    assert conv(data) == result
    assert conv([]) is None

    conv2 = c.aggregate(
        {"key": c.ReduceFuncs.DictArray(c.item(0), c.item(1))}
    ).gen_converter(debug=False)
    assert conv2([]) == {"key": None}
    assert conv2(data) == {"key": result}

    def two():
        return 2

    assert (
        c.aggregate(c.ReduceFuncs.Sum(c.this * c.naive(two).call())).execute(
            range(4)
        )
        == 12
    )


def test_piped_group_by():
    input_data = [
        {"a": 5, "b": "foo", "amount": 1},
        {"a": 10, "b": "bar", "amount": 2},
        {"a": 10, "b": "bar", "amount": 3},
    ]
    assert c.group_by(c.item("a"), c.item("b")).aggregate(
        {
            "a": c.item("a"),
            "b": c.item("b"),
            "amount": c.ReduceFuncs.Sum(c.item("amount")),
        }
    ).pipe(
        c.group_by(c.item("b")).aggregate(
            {
                "b": c.item("b"),
                "set_a": c.ReduceFuncs.ArrayDistinct(c.item("a")),
                "min_amount": c.ReduceFuncs.Min(c.item("amount")),
            }
        )
    ).execute(
        input_data, debug=False
    ) == [
        {"b": "foo", "set_a": [5], "min_amount": 1},
        {"b": "bar", "set_a": [10], "min_amount": 5},
    ]


def test_group_by_with_pipes():
    # fmt: off
    input_data = [
        {"name": "John", "started_at": date(2020, 1, 1), "stopped_at": None, "product": "A"},
        {"name": "John", "started_at": date(2020, 1, 1), "stopped_at": date(2020, 1, 2), "product": "B"},
        {"name": "John", "started_at": date(2020, 1, 1), "stopped_at": None, "product": "C"},
        {"name": "Nick", "started_at": date(2020, 1, 1), "stopped_at": None, "product": "D"},
        {"name": "Nick", "started_at": date(2020, 2, 1), "stopped_at": None, "product": "D"},
        {"name": "Nick", "started_at": date(2020, 2, 1), "stopped_at": None, "product": "E"},
    ]
    # fmt: on
    output = (
        c.group_by(
            c.item("name"),
            c.item("started_at"),
        )
        .aggregate(
            {
                "name": c.item("name"),
                "started_at": c.item("started_at"),
                "products": c.ReduceFuncs.ArrayDistinct(
                    c.if_(
                        c.item("stopped_at").is_(None),
                        c.item("product"),
                        None,
                    ),
                )
                .pipe(c.filter(c.this))
                .pipe(
                    c.call_func(sorted, c.this).pipe(
                        c(", ").call_method("join", c.this)
                    )
                )
                .pipe(c.this),
            }
        )
        .execute(input_data)
    )
    # fmt: off
    assert output == [
        {'name': 'John', 'products': 'A, C', 'started_at': date(2020, 1, 1)},
        {'name': 'Nick', 'products': 'D', 'started_at': date(2020, 1, 1)},
        {'name': 'Nick', 'products': 'D, E', 'started_at': date(2020, 2, 1)}]
    # fmt: on

    reducer = c.ReduceFuncs.Array(c.this, default=list)
    output = (
        c.group_by(
            c.this["name"],
            c.this["started_at"],
        )
        .aggregate(
            {
                "name": c.this["name"],
                "started_at": c.this["started_at"],
                "products": c.this["product"].pipe(reducer)[:3],
            }
        )
        .execute(input_data)
    )
    assert output == [
        {
            "name": "John",
            "products": ["A", "B", "C"],
            "started_at": date(2020, 1, 1),
        },
        {
            "name": "Nick",
            "products": ["D"],
            "started_at": date(2020, 1, 1),
        },
        {
            "name": "Nick",
            "products": ["D", "E"],
            "started_at": date(2020, 2, 1),
        },
    ]


def test_group_by_with_double_ended_pipes():
    input_data = [
        {"value": 1},
        {"value": 2},
    ]
    # fmt: off
    conv = c.aggregate(
        c.item("value")
        .pipe(c.ReduceFuncs.Sum(c.this))
        .pipe(c.this * 2)
    ).gen_converter()
    # fmt: on
    result = conv(input_data)
    assert result == 6

    input_data = [
        {"k": "A", "v": 1},
        {"k": "A", "v": 2},
    ]
    reducer = c.ReduceFuncs.Sum(c.item("v"))
    conv = (
        c.group_by(c.item("k"))
        .aggregate(
            {
                "v1": c.input_arg("test").pipe(reducer),
                "v2": reducer,
            }
        )
        .gen_converter()
    )
    assert conv(input_data, test={"v": 7}) == [{"v1": 14, "v2": 3}]


def test_simple_label():
    conv1 = (
        c.tuple(c.item(2).add_label("a"), c.this)
        .pipe(c.item(1).pipe(c.list_comp((c.this, c.label("a")))))
        .gen_converter(debug=False)
    )
    assert conv1([1, 2, 3, 4]) == [(1, 3), (2, 3), (3, 3), (4, 3)]

    conv2 = (
        c.tuple(c.item(1).add_label("a"), c.this)
        .pipe(
            c.item(1),
            label_input={"aa": c.item(0), "bb": c.item(0)},
            label_output="collection1",
        )
        .pipe(
            c.label("collection1").pipe(
                c.aggregate(
                    c.ReduceFuncs.Sum(
                        c.this
                        + c.label("a")
                        + c.label("aa")
                        + c.input_arg("x")
                        + c.label("collection1").item(0),
                    )
                )
            ),
            label_output="b",
        )
        .pipe(c.this + c.label("b"))
        .gen_converter()
    )
    assert conv2([1, 2, 3, 4], x=10) == 140

    conv3 = (
        c.tuple(c.item("default").add_label("default"), c.this)
        .pipe(c.item(1).pipe(c.item("abc", default=c.label("default"))))
        .gen_converter(debug=False)
    )
    assert conv3({"default": 1}) == 1

    with pytest.raises(c.ConversionException):
        c.this.pipe(c.this, label_input=1)


def test_aggregate_func():
    input_data = [
        {"a": 5, "b": "foo"},
        {"a": 10, "b": "bar"},
        {"a": 10, "b": "bar"},
    ]

    conv = c.aggregate(
        {
            "a": c.ReduceFuncs.Array(c.item("a")),
            "a_sum": c.ReduceFuncs.Array(c.item("a")).pipe(
                c.aggregate(c.ReduceFuncs.Sum(c.this))
            ),
            "ab_sum": c.ReduceFuncs.Sum(c.item("a")) + c.ReduceFuncs.Count(),
            "b": c.ReduceFuncs.ArrayDistinct(c.item("b")),
            "b_max_a": c.ReduceFuncs.MaxRow(c.item("a")).item(
                "b", default=None
            ),
        }
    ).gen_converter()

    assert conv(input_data) == {
        "a": [5, 10, 10],
        "a_sum": 25,
        "ab_sum": 28,
        "b": ["foo", "bar"],
        "b_max_a": "bar",
    }


def test_group_by_delegate():
    converter = (
        c.group_by(c.item("a"))
        .aggregate({"a": c.item("a"), "b": c.ReduceFuncs.Sum(c.item("b"))})
        .iter(c.item("b"))
        .as_type(set)
        .gen_converter()
    )
    code_str = get_code_str(converter)
    assert (
        converter(
            [
                {"a": 1, "b": 0},
                {"a": 1, "b": 3},
                {"a": 2, "b": 0},
                {"a": 2, "b": 3},
                {"a": 3, "b": 1},
                {"a": 3, "b": 3},
            ]
        )
        == {3, 4}
        and "return {{" in code_str
        and ".items() if " not in code_str
    )
    converter = (
        c.group_by(c.item("a"))
        .aggregate({"a": c.item("a"), "b": c.ReduceFuncs.Sum(c.item("b"))})
        .iter_mut(c.Mut.set_item("c", c.item("a") + c.item("b")))
        .gen_converter()
    )
    assert list(converter([{"a": 1, "b": 0}, {"a": 1, "b": 3}])) == [
        {"a": 1, "b": 3, "c": 4},
    ] and re.findall(r"return iter_mut\w*\(\(\{", get_code_str(converter))

    with c.OptionsCtx() as options:
        options.debug = True
        converter = c.aggregate(
            {
                "a": c.ReduceFuncs.Sum(c.item(1)),
                "b": c.ReduceFuncs.Sum(c.item(0)),
                "c": c.ReduceFuncs.Sum(c.item(1), where=c.item(1) > 1),
                "d": c.ReduceFuncs.Sum(c.item(0), where=c.item(1) > 1),
                "e": c.ReduceFuncs.Sum(c.item(1), where=c.item(1) > 2),
            }
        ).gen_converter()
        assert (
            converter(zip(range(10), range(100, 110)))
            == {
                "a": 1045,
                "b": 45,
                "c": 1045,
                "d": 45,
                "e": 1045,
            }
            and converter.__globals__["__BROKEN_EARLY__"]
        )

        converter = c.aggregate(c.ReduceFuncs.Sum(c.this)).gen_converter()
        assert (
            converter(range(10)) == 45
            and converter.__globals__["__BROKEN_EARLY__"]
        )

    result = (
        c.group_by(c.item(0))
        .aggregate(c.ReduceFuncs.Sum(c.item(1)))
        .to_iter()
        .execute([(1, 1), (1, 2), (3, 4)])
    )
    assert isinstance(result, GeneratorType) and list(result) == [3, 4]


def test_group_by_with_labels():
    converter = (
        c.this.pipe(c.this, label_input={"label_d": c.item(0, "b")})
        .pipe(
            c.group_by(c.item("a"))
            .aggregate(
                {
                    "a": c.item("a"),
                    "sum": c.ReduceFuncs.Sum(c.item("b")),
                }
            )
            .iter_mut(
                c.Mut.set_item("c", c.input_arg("input_c")),
                c.Mut.set_item("d", c.label("label_d")),
            )
            .as_type(list)
        )
        .gen_converter(debug=True)
    )
    assert converter(
        [
            {"a": 1, "b": 0},
            {"a": 1, "b": 1},
            {"a": 1, "b": 2},
        ],
        input_c=7,
    ) == [{"a": 1, "sum": 3, "c": 7, "d": 0}]


def test_group_by_none_counts():
    converter = c.aggregate(c.ReduceFuncs.Count()).gen_converter()
    assert converter((1,) * 10) == 10
    assert converter((None,) * 10) == 10

    converter = c.aggregate(c.ReduceFuncs.Count(c.this)).gen_converter()
    assert converter((1,) * 10) == 10
    assert converter((None,) * 10) == 0

    converter = c.aggregate(c.ReduceFuncs.DictCount(c.this)).gen_converter()
    assert converter((1,) * 10) == {1: 10}
    assert converter((None,) * 10) == {None: 10}
    converter = c.aggregate(
        c.ReduceFuncs.DictCount(c.this, c.this)
    ).gen_converter()
    assert converter((1,) * 10) == {1: 10}
    assert converter((None,) * 10) is None
