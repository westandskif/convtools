import pytest

from convtools import conversion as c
from convtools.aggregations import MultiStatementReducer


class SumReducer1(MultiStatementReducer):
    reduce = ("%(result)s = {0} + ({1} or 1)",)
    default = int
    initial = int
    unconditional_init = True


class SumReducer2(MultiStatementReducer):
    reduce = ("%(result)s = {0} + ({1} or 2)",)
    default = 0
    initial = 0
    unconditional_init = True


class SumReducer3(MultiStatementReducer):
    reduce = ("%(result)s = {0} + ({1} or 3)",)
    initial = 0
    unconditional_init = True


class SumReducer4(MultiStatementReducer):
    prepare_first = ("%(result)s = {0}",)
    reduce = ("%(result)s = {0} + ({1} or 4)",)
    default = 0
    unconditional_init = True


class SumReducer5(MultiStatementReducer):
    reduce = ("%(result)s = {0} + ({1} or 5)",)
    default = 0
    unconditional_init = True


NAME_VALUE_INPUT_DATA = [
    {"name": "Nick", "value": 1},
    {"name": "Nick", "value": 2},
    {"name": "John", "value": 20},
    {"name": "John", "value": 21},
    {"name": "John", "value": 22},
]


def test_multi_statement_reducers():
    output = (
        c.group_by(c.item("name"))
        .aggregate(
            (
                c.item("name"),
                SumReducer1(c.item("value")),
                SumReducer2(c.item("value")),
                SumReducer3(c.item("value")),
                SumReducer4(c.item("value")),
                SumReducer5(c.item("value"), initial=5),
            )
        )
        .execute(NAME_VALUE_INPUT_DATA, debug=True)
    )
    assert output == [("Nick", 3, 3, 3, 3, 8), ("John", 63, 63, 63, 63, 68)]

    with pytest.raises(ValueError):

        class SumReducer(MultiStatementReducer):
            reduce = ("%(result)s = {0} + ({1} or 4)",)
            default = 0
            unconditional_init = True

        SumReducer(c.item("value"))
    with pytest.raises(ValueError):

        class SumReducer(MultiStatementReducer):
            reduce = ("%(result)s = {0} + ({1} or 4)",)
            unconditional_init = True

        SumReducer(c.item("value"))


def test_custom_reduce():
    with pytest.raises(ValueError):
        c.reduce(lambda a, b: a + b, c.this())
    with pytest.raises(ValueError):
        c.reduce(lambda a, b: a + b, c.this(), default=0)


def test_legacy_dict_reduce_approach():
    output = c.aggregate(
        c.reduce(
            c.ReduceFuncs.DictSum,
            (c.item("name"), c.item("value")),
        )
    ).execute(NAME_VALUE_INPUT_DATA)
    assert output == {
        "Nick": 3,
        "John": 63,
    }
    with pytest.raises(ValueError):
        c.ReduceFuncs.DictSum(c.this(), c.this(), c.this())
    with pytest.raises(ValueError):
        c.ReduceFuncs.DictSum({c.this(), c.this()})


def test_reducer_reuse():
    input_data = [
        {"name": "Nick", "value": 1},
        {"name": "Nick", "value": 2},
        {"name": "John", "value": 20},
        {"name": "John", "value": 21},
        {"name": "John", "value": 22},
    ]

    f = lambda a, b: a + b
    reducer = c.reduce(f, c.item("value"), initial=0)
    reducer2 = c.reduce(f, c.item("value"), initial=0)
    output = (
        c.group_by(c.item("name"))
        .aggregate(
            (
                c.item("name"),
                reducer + 10,
                reducer2 + 20,
            )
        )
        .execute(input_data)
    )
    assert output == [
        ("Nick", 13, 23),
        ("John", 73, 83),
    ]


def test_blank_aggregate():
    assert c.group_by(c.item(0)).aggregate(c.item(0)).execute(
        [
            (0, 1),
            (1, 2),
        ]
    ) == [
        0,
        1,
    ]
