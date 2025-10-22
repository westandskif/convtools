import sqlite3
from datetime import date, datetime, timedelta

import pytest

from convtools import conversion as c


def test_iter_window():
    assert list(c.iter_windows(2, step=1).execute(range(3))) == [
        (0,),
        (0, 1),
        (1, 2),
        (2,),
    ]
    assert list(
        c.iter_windows(2, step=1)
        .iter(c.aggregate(c.ReduceFuncs.Sum(c.this)))
        .execute(range(3))
    ) == [0, 1, 3, 2]

    assert c.call_func(range, 3).iter_windows(3).as_type(list).execute(
        None
    ) == [
        (0,),
        (0, 1),
        (0, 1, 2),
        (1, 2),
        (2,),
    ]

    assert list(c.iter_windows(2, step=2).execute(range(5))) == [
        (0,),
        (1, 2),
        (3, 4),
    ]

    assert list(c.iter_windows(2).execute([])) == []


def test_accumulators():
    assert (
        c.iter(c.cumulative(c.this, c.this + c.PREV))
        .as_type(list)
        .execute([0, 1, 2, 3, 4])
    ) == [0, 1, 3, 6, 10]

    assert (
        c.iter(
            c.cumulative(
                c.this + c.input_arg("a"), c.this + c.PREV + c.input_arg("b")
            )
        )
        .as_type(list)
        .execute([0, 1, 2, 3, 4], a=10, b=1000)
    ) == [10, 1011, 2013, 3016, 4020]

    assert (
        c.iter(c.iter(c.cumulative(c.this, c.this + c.PREV)).as_type(list))
        .as_type(list)
        .execute([[0, 1, 2], [3, 4]])
    ) == [[0, 1, 3], [6, 10]]

    assert (
        c.iter(
            c.cumulative_reset("abc")
            .iter(c.cumulative(c.this, c.this + c.PREV, label_name="cde"))
            .as_type(list)
        )
        .as_type(list)
        .execute([[0, 1, 2], [3, 4]])
    ) == [[0, 1, 3], [6, 10]]

    assert (
        c.iter(
            c.cumulative_reset("abc")
            .iter(c.cumulative(c.this, c.this + c.PREV, label_name="abc"))
            .as_type(list)
        )
        .as_type(list)
        .execute([[0, 1, 2], [3, 4]])
    ) == [[0, 1, 3], [3, 7]]

    assert (
        c.iter(
            c.cumulative(
                c.this,
                c((c.this, c.PREV)).pipe(
                    c.aggregate(c.ReduceFuncs.Sum(c.this))
                ),
            )
        )
        .as_type(list)
        .execute([0, 1, 2, 3, 4])
    ) == [0, 1, 3, 6, 10]

    assert (
        c.iter(c.item(0).cumulative(c.this + 1, c.this * c.PREV))
        .as_type(list)
        .execute([[0], [1], [2], [3], [4]])
    ) == [1, 1, 2, 6, 24]


def test_window_func_range(window_in_1):
    data = window_in_1
    with c.OptionsCtx() as options:
        options.debug = False
        result = (
            c.this.window(
                {
                    "1_sum": c.ReduceFuncs.Sum(c.item("b")),
                    "2_l": c.ReduceFuncs.Array(c.item("b")),
                    "rows": (
                        c.WindowFuncs.Row().item("id", default=None),
                        c.WindowFuncs.PeerGroupFirstRow().item(
                            "id", default=None
                        ),
                        c.WindowFuncs.PeerGroupLastRow().item(
                            "id", default=None
                        ),
                    ),
                    "indexes": (
                        c.WindowFuncs.PeerGroupFirstRowIndex(),
                        c.WindowFuncs.PeerGroupLastRowIndex(),
                    ),
                }
            )
            .over(
                partition_by=c.item("a").or_(c.input_arg("a_fallback")),
                order_by=c.item("dt").or_(c.input_arg("dt_fallback")),
                frame_mode="RANGE",
                frame_start=(timedelta(days=3), "PRECEDING"),
                frame_end=(timedelta(days=1), "PRECEDING"),
            )
            .execute(data, dt_fallback=date(1970, 1, 1), a_fallback=0)
        )
    # fmt: off
    assert result == [
        {"1_sum": 0, "2_l": None, "indexes": (0, 0), "rows": (1, 1, 1)},
        {"1_sum": 0, "2_l": None, "indexes": (0, 0), "rows": (2, 2, 2)},
        {"1_sum": 1, "2_l": [1], "indexes": (1, 3), "rows": (3, 3, 5)},
        {"1_sum": 1, "2_l": [1], "indexes": (1, 3), "rows": (4, 3, 5)},
        {"1_sum": 1, "2_l": [1], "indexes": (1, 3), "rows": (5, 3, 5)},
        {"1_sum": 10, "2_l": [1, 3, 4, 2], "indexes": (4, 4), "rows": (6, 6, 6)},
        {"1_sum": 15, "2_l": [1, 3, 4, 2, 5], "indexes": (5, 5), "rows": (7, 7, 7)},
        {"1_sum": 20, "2_l": [3, 4, 2, 5, 6], "indexes": (6, 6), "rows": (8, 8, 8)},
        {"1_sum": 13, "2_l": [6, 7], "indexes": (7, 7), "rows": (9, 9, 9)},
    ]
    # fmt: on


@pytest.fixture
def window_in_1():
    return [
        {"id": 1, "a": 1, "dt": date(2020, 1, 1), "b": 1},
        {"id": 2, "a": 2, "dt": date(2020, 1, 1), "b": 6},
        {"id": 3, "a": 1, "dt": date(2020, 1, 2), "b": 3},
        {"id": 4, "a": 1, "dt": date(2020, 1, 2), "b": 4},
        {"id": 5, "a": 1, "dt": date(2020, 1, 2), "b": 2},
        {"id": 6, "a": 1, "dt": date(2020, 1, 3), "b": 5},
        {"id": 7, "a": 1, "dt": date(2020, 1, 4), "b": 6},
        {"id": 8, "a": 1, "dt": date(2020, 1, 5), "b": 7},
        {"id": 9, "a": 1, "dt": date(2020, 1, 7), "b": 8},
    ]


@pytest.fixture
def con(window_in_1):
    sqlite3.register_adapter(date, lambda d: str(d.toordinal()))
    sqlite3.register_converter(
        "date", lambda b: date.fromordinal(int(b.decode()))
    )

    con = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    con.execute("create table t(id integer, a integer, dt date, b integer)")
    con.executemany(
        "insert into t values (:id, :a, :dt, :b)",
        window_in_1,
    )
    yield con
    con.close()


@pytest.mark.parametrize(
    "f",
    [
        (("sum(b)",), (c.ReduceFuncs.Sum(c.item("b"), default=None),)),
        (
            (
                "count(*)",
                "row_number()",
                "rank()",
                "dense_rank()",
                "lag(b)",
                "lag(b, 2)",
                "lag(b, 3, -1)",
                "lead(b)",
                "lead(b, 2)",
                "lead(b, 3, -1)",
                "first_value(b)",
                "last_value(b)",
                "nth_value(b, 1)",
                "nth_value(b, 2)",
            ),
            (
                c.ReduceFuncs.Count(),
                c.WindowFuncs.RowIndex() + 1,
                c.WindowFuncs.PeerGroupFirstRowIndex() + 1,
                c.WindowFuncs.PeerGroupIndex() + 1,
                c.WindowFuncs.RowPreceding(1).item("b", default=None),
                c.WindowFuncs.RowPreceding(2).item("b", default=None),
                c.WindowFuncs.RowPreceding(3).item("b", default=-1),
                c.WindowFuncs.RowFollowing(1).item("b", default=None),
                c.WindowFuncs.RowFollowing(2).item("b", default=None),
                c.WindowFuncs.RowFollowing(3).item("b", default=-1),
                c.WindowFuncs.FrameFirstRow().item("b", default=None),
                c.WindowFuncs.FrameLastRow().item("b", default=None),
                c.WindowFuncs.FrameNthRow(0).item("b", default=None),
                c.WindowFuncs.FrameNthRow(1).item("b", default=None),
            ),
        ),
    ],
)
@pytest.mark.parametrize("partition_by", [(), ("a",)])
@pytest.mark.parametrize(
    "order_by_n_mode",
    [
        ((), (), "ROWS"),
        ((), (), "RANGE"),
        ((), (), "GROUPS"),
        (("id",), (c.item("id"),), "ROWS"),
        (("id",), (c.item("id"),), "GROUPS"),
        (("id",), (c.item("id"),), "RANGE"),
        (("dt",), (c.item("dt"),), "ROWS"),
        (
            ("dt desc nulls last",),
            (c.item("dt").desc(none_last=True),),
            "ROWS",
        ),
        (("dt",), (c.item("dt"),), "GROUPS"),
        (("a", "dt"), (c.item("a"), c.item("dt")), "ROWS"),
        (("dt", "a"), (c.item("dt"), c.item("a")), "ROWS"),
    ],
)
@pytest.mark.parametrize(
    "frame",
    [
        # fmt: off
        ("between unbounded preceding and current row", {"frame_start": "UNBOUNDED PRECEDING", "frame_end": "CURRENT ROW"}),
        ("between current row and unbounded following", {"frame_start": "CURRENT ROW", "frame_end": "UNBOUNDED FOLLOWING"}),
        ("between current row and current row", {"frame_start": "CURRENT ROW", "frame_end": "CURRENT ROW"}),
        ("between 2 preceding and 1 preceding", {"frame_start": (2, "PRECEDING"), "frame_end": (1, "PRECEDING")}),
        ("between 0 preceding and 0 following", {"frame_start": (0, "PRECEDING"), "frame_end": (0, "FOLLOWING")}),
        ("between 1 preceding and 1 following", {"frame_start": (1, "PRECEDING"), "frame_end": (1, "FOLLOWING")}),
        ("between 1 following and 2 following", {"frame_start": (1, "FOLLOWING"), "frame_end": (2, "FOLLOWING")}),
        # fmt: on
    ],
)
@pytest.mark.parametrize(
    "exclusion", ["", "NO OTHERS", "TIES", "GROUP", "CURRENT ROW"]
)
def test_window_funcs_with_sqlite(
    con, window_in_1, f, partition_by, order_by_n_mode, frame, exclusion
):
    order_by, c_order_by, mode = order_by_n_mode
    if mode == "RANGE" and any(
        isinstance(frame[1][key], tuple)
        for key in ("frame_start", "frame_end")
    ):
        return

    over_parts = ["over ("]
    over_kwargs = {"frame_mode": mode}

    if partition_by:
        over_parts.append("partition by {}".format(", ".join(partition_by)))
        over_kwargs["partition_by"] = tuple(c.item(s) for s in partition_by)
    if order_by:
        over_parts.append("order by {}".format(", ".join(order_by)))
        over_kwargs["order_by"] = c_order_by

    over_parts.append(mode)
    over_parts.append(frame[0])
    over_kwargs.update(frame[1])

    if exclusion:
        over_parts.append(f"EXCLUDE {exclusion}")
        over_kwargs["frame_exclusion"] = exclusion

    over_parts.append(")")
    over_query_part = " ".join(over_parts)
    del over_parts

    query = "select {} from t order by id".format(
        ", ".join(f"{item} {over_query_part}" for item in f[0])
    )
    expected = con.execute(query).fetchall()

    # c.this.window((f[1],)).over(**over_kwargs).gen_converter(debug=True)
    # breakpoint()
    converter = c.this.window(tuple(f[1])).over(**over_kwargs).gen_converter()
    result = converter(window_in_1)
    assert expected == result


def test_window_func_inside_agg():
    result = c.aggregate(
        c.ReduceFuncs.Array(c.this).pipe(
            c.this.window(c.ReduceFuncs.Sum(c.this)).over()
        )
    ).execute(range(10))
    assert result == [45, 45, 45, 45, 45, 45, 45, 45, 45, 45]


def test_window_func_exceptions():
    with pytest.raises(ValueError):
        c.this.window(1).over(frame_start=-1)

    with pytest.raises(ValueError):
        c.this.window(1).over(frame_start="UNBOUNDED FOLLOWING")
    with pytest.raises(ValueError):
        c.this.window(1).over(frame_end="UNBOUNDED PRECEDING")

    with pytest.raises(ValueError):
        c.this.window(1).over(frame_mode="ROWS", frame_start=(-1, "PRECEDING"))

    with pytest.raises(ValueError):
        c.this.window(1).over(frame_start=(-1, "PRECEDING"))

    with pytest.raises(ValueError):
        c.this.pipe(c.this.window(1)).gen_converter()

    with pytest.raises(ValueError):
        c.this.window(1).over(frame_start=())

    with pytest.raises(ValueError):
        c.this.window(1).gen_converter()


# TODO: ordering
