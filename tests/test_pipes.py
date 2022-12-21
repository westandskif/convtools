from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from convtools import conversion as c
from convtools.base import PipeConversion


def test_pipes_base():
    assert (
        c.this.pipe(
            c.iter(c.this + 10).as_type(list),
            label_output="abc",
        )
        .filter(c.this > c.label("abc").item(0))
        .as_type(list)
        .execute([1, 2, 3])
    ) == [12, 13]

    assert c.list_comp(c.inline_expr("{0} ** 2").pass_args(c.this)).pipe(
        c.call_func(sum, c.this)
    ).pipe(
        c.call_func(
            lambda x, a: x + a,
            c.this,
            c.naive({"abc": 10}).item(c.input_arg("key_name")),
        )
    ).pipe(
        [c.this, c.this]
    ).execute(
        [1, 2, 3], key_name="abc", debug=False
    ) == [
        24,
        24,
    ]
    assert c.item(0).pipe(datetime.strptime, "%Y-%m-%d").pipe(
        c.call_func(lambda dt: dt.date(), c.this)
    ).execute(["2019-01-01"], debug=False) == date(2019, 1, 1)

    assert c.item(0).pipe(datetime.strptime, "%Y-%m-%d").pipe(
        c.this.call_method("date")
    ).execute(["2019-01-01"], debug=False) == date(2019, 1, 1)

    conv = c.dict_comp(
        c.item("name"),
        c.item("transactions").pipe(
            c.list_comp(
                {
                    "id": c.item(0).as_type(str),
                    "amount": c.item(1).pipe(
                        c.if_(c.this, c.this.as_type(Decimal), None)
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

    assert c.this.pipe(lambda it: it).filter(c.this).sort().as_type(
        list
    ).execute((2, 1, 0)) == [1, 2]

    assert (
        c(1)
        .pipe(c.call_func(int), label_output="abc")
        .pipe(c.label("abc") + 10)
        .execute(None)
        == 10
    )
    assert (c.item(0).pipe(c.this + 1) + c.item(1)).execute([2, 3]) == 6

    for conversion, in_, out in [
        (c.item(0).pipe(c.this) + 2, (1,), 3),
        (c.item(0).pipe(c.this).add(2), (1,), 3),
        (c.item(0).pipe(c.this) & 2, (1,), 2),
        (c.item(0).pipe(c.this) == 2, (1,), False),
        (c.item(0).pipe(c.this) // 2, (3,), 1),
        (c.item(0).pipe(c.this).floor_div(2), (3,), 1),
        (c.item(0).pipe(c.this) >= 2, (2,), True),
        (c.item(0).pipe(c.this).gte(2), (2,), True),
        (c.item(0).pipe(c.this) > 2, (2,), False),
        (c.item(0).pipe(c.this).gt(2), (2,), False),
        (c.item(0).pipe(c.this) <= 2, (2,), True),
        (c.item(0).pipe(c.this).lte(2), (2,), True),
        (c.item(0).pipe(c.this) < 2, (2,), False),
        (c.item(0).pipe(c.this).lt(2), (2,), False),
        (c.item(0).pipe(c.this) % 2, (3,), 1),
        (c.item(0).pipe(c.this).mod(2), (3,), 1),
        (c.item(0).pipe(c.this) * 2, (3,), 6),
        (c.item(0).pipe(c.this).mul(2), (3,), 6),
        (c.item(0).pipe(c.this) != 2, (3,), True),
        (c.item(0).pipe(c.this).not_eq(2), (3,), True),
        (c.item(0).pipe(c.this) | 2, (0,), 2),
        (c.item(0).pipe(c.this) - 2, (5,), 3),
        (c.item(0).pipe(c.this).sub(2), (5,), 3),
        (c.item(0).pipe(c.this) / 2, (5,), 2.5),
        (c.item(0).pipe(c.this).div(2), (5,), 2.5),
        (c.item(0).pipe(c.iter(c.this)).as_type(list), ((5,),), [5]),
        (c.item(0).pipe(c.this).in_([2]), (2,), True),
        (c.item(0).pipe(c.this).not_in([2]), (3,), True),
        (c.item(0).pipe(c.this).is_(3), (3,), True),
        (c.item(0).pipe(c.this).is_not(3), (3,), False),
        (-c.item(0).pipe(c.this), (3,), -3),
        (c.item(0).pipe(c.this).neg(), (3,), -3),
        (~c.item(0).pipe(c.this), (True,), False),
        (c.item(0).pipe(c.this).not_(), (True,), False),
        (
            c.item(0).pipe(c.this).flatten().as_type(list),
            ([[1], [2]],),
            [1, 2],
        ),
        (c.item(0).pipe(c.this).len(), ([1, 2, 1],), 3),
    ]:
        assert (
            isinstance(conversion, PipeConversion)
            and conversion.execute(in_) == out
        )

    conversion = c.item(0).pipe(c.this) + c.item(1)
    assert (
        not isinstance(conversion, PipeConversion)
        and conversion.execute((1, 2)) == 3
    )
    conversion = (
        c.item(0)
        .pipe(c.this, label_output={"abc": c.item(-1)})
        .iter(c.this + c.label("abc"))
        .as_type(list)
    )
    assert conversion.execute(((1, 2),)) == [3, 4]

    old_replace = PipeConversion._replace
    count = 0

    def new_replace(pipe, where):
        nonlocal count
        count += 1
        # if count == 1:
        #     print(f"[{count}] REPLACING THIS:")
        #     pipe.where.gen_converter(debug=True)
        # print(f"[{count}] WITH THIS:")
        # where.gen_converter(debug=True)
        return old_replace(pipe, where)

    with patch.object(PipeConversion, "_replace", new_replace):
        # delegate iter
        count = 0
        assert (
            c.item("a")
            .pipe(c.item("b"))
            .iter(c.this + 1)
            .iter(c.this + 2)
            .as_type(list)
            .execute({"a": {"b": [1, 2, 3]}})
            == [4, 5, 6]
            and count == 3
        )

        # delegate iter_mut
        count = 0
        data = {"a": {"b": [[1], [2], [3]]}}
        c.item("a").pipe(c.item("b")).iter_mut(
            c.Mut.set_item(0, c.item(0) + c.item(0))
        ).as_type(list).execute(data)
        assert data["a"]["b"] == [[2], [4], [6]] and count == 2

        # delegate iter_windows
        count = 0
        assert (
            c.item("a")
            .pipe(c.item("b"))
            .iter_windows(2)
            .as_type(list)
            .execute({"a": {"b": [1, 2, 3]}})
            == [(1,), (1, 2), (2, 3), (3,)]
            and count == 2
        )

        # delegate filter
        count = 0
        assert (
            c.item("a")
            .pipe(c.item("b"))
            .filter(c.this > 1)
            .as_type(list)
            .execute({"a": {"b": [1, 2, 3]}})
            == [2, 3]
            and count == 2
        )

        # delegate pipe
        count = 0
        assert (
            c.item("a")
            .pipe(c.item("b"))
            .pipe(c.item(1))
            .execute({"a": {"b": [1, 2, 3]}})
            == 2
        ) and count == 1


def test_pipe_inlining():
    assert c.iter(
        (c.this() + 1).pipe(c.this() + 2).pipe(c.this() + 3).pipe(round)
    ).as_type(list).execute(range(3)) == [6, 7, 8]
    assert c.iter(
        (c.this() + 1).pipe(c.this() + c.this()).pipe(c.this() + 3).pipe(round)
    ).as_type(list).execute(range(3)) == [5, 7, 9]


def test_pipe_single_call_functions():
    class CustomException(Exception):
        pass

    def one_off_func():
        if one_off_func.first:
            one_off_func.first = False
            return 1
        raise CustomException

    one_off_func.first = True

    assert c.list_comp(
        c.call_func(one_off_func).pipe(
            (
                c.this + 1,
                c.this + 2,
            )
        )
    ).gen_converter(debug=False)([1]) == [(2, 3)]


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
        c.this.pipe(c.list_comp(c.this + 1))
        .filter(c.this > 3)
        .execute([1, 2, 3, 4, 5, 6], debug=False)
    ) == [4, 5, 6, 7]

    c.aggregate(
        c.ReduceFuncs.Array(c.item("key"), default=list).pipe(
            c.if_(
                c.call_func(any, c.generator_comp(c.this.is_(None))),
                c.call_func(list),
                c.this,
            )
        )
    ).gen_converter(debug=False)


def test_iter_method():
    assert c.this.iter(c.this * 3).filter(c.this).as_type(list).execute(
        [1, 2, 3, 0, 1],
        debug=False,
    ) == [3, 6, 9, 3]

    assert c.group_by(c.item(0)).aggregate(
        c(
            [
                c.item(0),
                c.item(1).pipe(c.ReduceFuncs.Max(c.this)),
            ]
        )
        .iter(c.this * 100)
        .as_type(tuple)
    ).execute([(0, 1), (0, 2), (1, 7)], debug=False) == [
        (0, 200),
        (100, 700),
    ]


def test_pipe_filter_sort():
    assert (
        c.this.as_type(list)
        .pipe(c.iter(c.this + 1))
        .filter(c.this > 3)
        .sort(key=lambda x: x, reverse=True)
        .execute(range(7), debug=False)
    ) == [7, 6, 5, 4]

    assert c.this.sort().execute([3, 1, 2]) == [1, 2, 3]


def test_pipe_label_args():
    assert (
        c.this.pipe(
            c.this,
            label_input={"label1": c.input_arg("abc")},
            label_output={"label2": c.input_arg("cde")},
        ).execute(None, abc=1, cde=2)
        is None
    )


def test_and_then():
    conv = c.and_then(c.this + 1).gen_converter()
    assert conv(0) == 0
    assert conv(1) == 2

    conv = c.and_then(c.this + 1, condition=c.this >= 10).gen_converter()
    assert conv(9) == 9
    assert conv(10) == 11
    assert conv(11) == 12

    conv = (c.this + 1).and_then(c.this + 10).gen_converter()
    assert conv(-1) == 0
    assert conv(0) == 11
    assert conv(1) == 12

    conv = (
        (c.this + 1)
        .and_then(c.this + 10, condition=c.this <= 1)
        .gen_converter()
    )
    assert conv(-1) == 10
    assert conv(0) == 11
    assert conv(1) == 2

    conv = c.this.and_then(c.this + 1, condition=bool).gen_converter()
    assert conv(-1) == 0
    assert conv(0) == 0
    assert conv(1) == 2

    conv = c.this.and_then(c.this + 1, condition=lambda x: x).gen_converter()
    assert conv(-1) == 0
    assert conv(0) == 0
    assert conv(1) == 2
