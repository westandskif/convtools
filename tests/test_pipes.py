from datetime import date, datetime
from decimal import Decimal

from convtools import conversion as c


def test_pipes():
    assert c.list_comp(c.inline_expr("{0} ** 2").pass_args(c.this())).pipe(
        c.call_func(sum, c.this())
    ).pipe(
        c.call_func(
            lambda x, a: x + a,
            c.this(),
            c.naive({"abc": 10}).item(c.input_arg("key_name")),
        )
    ).pipe(
        [c.this(), c.this()]
    ).execute(
        [1, 2, 3], key_name="abc", debug=False
    ) == [
        24,
        24,
    ]
    assert c.item(0).pipe(datetime.strptime, "%Y-%m-%d").pipe(
        c.call_func(lambda dt: dt.date(), c.this())
    ).execute(["2019-01-01"], debug=False) == date(2019, 1, 1)

    assert c.item(0).pipe(datetime.strptime, "%Y-%m-%d").pipe(
        c.this().call_method("date")
    ).execute(["2019-01-01"], debug=False) == date(2019, 1, 1)

    conv = c.dict_comp(
        c.item("name"),
        c.item("transactions").pipe(
            c.list_comp(
                {
                    "id": c.item(0).as_type(str),
                    "amount": c.item(1).pipe(
                        c.if_(c.this(), c.this().as_type(Decimal), None)
                    ),
                }
            )
        ),
    ).gen_converter(debug=False)
    assert conv([{"name": "test", "transactions": [(0, 0), (1, 10)]}]) == {
        "test": [
            {"id": "0", "amount": None},
            {"id": "1", "amount": Decimal("10")},
        ]
    }


def test_pipe_single_call_functions():
    class CustomException(Exception):
        pass

    def one_off_func():
        if one_off_func.first:
            one_off_func.first = False
            return 1
        raise CustomException

    one_off_func.first = True

    assert (
        c.list_comp(
            c.call_func(one_off_func).pipe(
                (
                    c.this() + 1,
                    c.this() + 2,
                )
            )
        ).gen_converter(debug=False)([1])
        == [(2, 3)]
    )


def test_pipe_conversion():
    from convtools import conversion as c
    from convtools.base import PipeConversion

    assert PipeConversion(c.naive([1, 2, 3]), c.item(1)).execute(None) == 2
    assert (
        PipeConversion(c.item("key1"), c.item("key2")).execute(
            {"key1": {"key2": 3}}, debug=False
        )
        == 3
    )
    assert (
        c.this()
        .pipe(c.list_comp(c.this() + 1))
        .filter(c.this() > 3)
        .execute([1, 2, 3, 4, 5, 6], debug=False)
    ) == [4, 5, 6, 7]

    c.aggregate(
        c.ReduceFuncs.Array(c.item("key"), default=list).pipe(
            c.if_(
                c.call_func(any, c.generator_comp(c.this().is_(None))),
                c.call_func(list),
                c.this(),
            )
        )
    ).gen_converter(debug=False)


def test_iter_method():
    assert (
        c.this()
        .iter(c.this() * 3)
        .filter(c.this())
        .as_type(list)
        .execute(
            [1, 2, 3, 0, 1],
            debug=False,
        )
        == [3, 6, 9, 3]
    )

    assert c.group_by(c.item(0)).aggregate(
        c(
            [
                c.item(0),
                c.item(1).pipe(c.ReduceFuncs.Max(c.this())),
            ]
        )
        .iter(c.this() * 100)
        .as_type(tuple)
    ).execute([(0, 1), (0, 2), (1, 7)], debug=False) == [
        (0, 200),
        (100, 700),
    ]


def test_pipe_filter_sort():
    assert (
        c.this()
        .as_type(list)
        .pipe(c.iter(c.this() + 1))
        .filter(c.this() > 3)
        .sort(key=lambda x: x, reverse=True)
        .execute(range(7), debug=False)
    ) == [7, 6, 5, 4]

    assert c.this().sort().execute([3, 1, 2]) == [1, 2, 3]
