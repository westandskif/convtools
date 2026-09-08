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
        (("id desc",), (c.item("id").desc(),), "ROWS"),
        (("id desc",), (c.item("id").desc(),), "RANGE"),
        (
            ("b desc nulls last",),
            (c.item("b").desc(none_last=True),),
            "RANGE",
        ),
        (("dt",), (c.item("dt"),), "ROWS"),
        (
            ("dt desc nulls last",),
            (c.item("dt").desc(none_last=True),),
            "ROWS",
        ),
        (("dt",), (c.item("dt"),), "GROUPS"),
        (("dt",), (c.item("dt"),), "RANGE"),
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
        ("between 1 preceding and unbounded following", {"frame_start": (1, "PRECEDING"), "frame_end": "UNBOUNDED FOLLOWING"}),
        ("between unbounded preceding and 1 following", {"frame_start": "UNBOUNDED PRECEDING", "frame_end": (1, "FOLLOWING")}),
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
        if (
            not order_by
            or len(order_by) != 1
            or any("dt" in part for part in order_by)
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


def test_rows_frame_end_preceding_early_rows():
    # frame_end N PRECEDING (N>=2) must not pass a negative stop to islice.
    # Empty frames yield Sum default 0 (PostgreSQL would use NULL here).
    result = (
        c.this.window(c.ReduceFuncs.Sum(c.this))
        .over(
            frame_mode="ROWS",
            frame_start="UNBOUNDED PRECEDING",
            frame_end=(2, "PRECEDING"),
        )
        .execute([1, 2, 3, 4])
    )
    assert result == [0, 0, 1, 3]

    # both bounds preceding: start and end clamped together on early rows
    result = (
        c.this.window(c.ReduceFuncs.Sum(c.this))
        .over(
            frame_mode="ROWS",
            frame_start=(3, "PRECEDING"),
            frame_end=(2, "PRECEDING"),
        )
        .execute([1, 2, 3, 4])
    )
    assert result == [0, 0, 1, 3]


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


@pytest.mark.parametrize(
    "data, order_by, frame_start, frame_end, expected",
    [
        (
            [1, 2, 3, 5],
            c.this.desc(),
            (1, "PRECEDING"),
            "CURRENT ROW",
            [2, 2, 1, 1],
        ),
        (
            [1, 2, 3, 5],
            c.this.desc(),
            "CURRENT ROW",
            (1, "FOLLOWING"),
            [1, 2, 2, 1],
        ),
        (
            [1, 2, 3, 5, 5],
            c.this.desc(),
            (1, "PRECEDING"),
            (1, "FOLLOWING"),
            [2, 3, 2, 2, 2],
        ),
        (
            [3, None, 1, 2, None],
            c.this.asc(none_last=True),
            (1, "PRECEDING"),
            "CURRENT ROW",
            [2, 2, 1, 2, 2],
        ),
        (
            [3, None, 1, 2, None],
            c.this.asc(none_first=True),
            (1, "PRECEDING"),
            (1, "FOLLOWING"),
            [2, 2, 2, 3, 2],
        ),
        (
            [3, None, 1, 2, None, 5],
            c.this.desc(none_last=True),
            "CURRENT ROW",
            (2, "FOLLOWING"),
            [3, 2, 1, 2, 2, 2],
        ),
        (
            [3, None, 1, 2, None, 5],
            c.this.desc(none_first=True),
            (1, "PRECEDING"),
            "CURRENT ROW",
            [1, 2, 2, 2, 2, 1],
        ),
        (
            [10, 11, None, None],
            c.this.asc(none_last=True),
            (1, "FOLLOWING"),
            "UNBOUNDED FOLLOWING",
            [3, 2, 2, 2],
        ),
        (
            [10, 11, None, None],
            c.this.asc(none_last=True),
            (1, "PRECEDING"),
            "UNBOUNDED FOLLOWING",
            [4, 4, 2, 2],
        ),
        (
            [10, 11, None, None],
            c.this.asc(none_last=True),
            (1, "FOLLOWING"),
            (2, "FOLLOWING"),
            [1, 0, 2, 2],
        ),
        (
            [10, 11, None, None],
            c.this.asc(none_last=True),
            "UNBOUNDED PRECEDING",
            (1, "FOLLOWING"),
            [2, 2, 4, 4],
        ),
        (
            [None, None, 10, 11],
            c.this.asc(none_first=True),
            "UNBOUNDED PRECEDING",
            (1, "PRECEDING"),
            [2, 2, 2, 3],
        ),
        (
            [None, None, 10, 11],
            c.this.asc(none_first=True),
            (1, "PRECEDING"),
            "UNBOUNDED FOLLOWING",
            [4, 4, 2, 2],
        ),
        (
            [10, 11, None, None],
            c.this.desc(none_first=True),
            (1, "FOLLOWING"),
            "UNBOUNDED FOLLOWING",
            [0, 1, 4, 4],
        ),
    ],
)
def test_range_offsets_honor_ordering_hints(
    data, order_by, frame_start, frame_end, expected
):
    result = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=order_by,
            frame_start=frame_start,
            frame_end=frame_end,
        )
        .execute(data)
    )
    assert result == expected


def test_range_offsets_pipe_shaped_desc_key():
    data = [{"v": v} for v in [1, 2, 3, 5]]
    expected = [2, 2, 1, 1]
    via_desc = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=c.item("v").desc(),
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
        )
        .execute(data)
    )
    via_pipe = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=c.item("v").pipe(c.this.desc()),
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
        )
        .execute(data)
    )
    assert via_desc == expected
    assert via_pipe == expected


def test_window_order_by_desc_on_pipe():
    data = [{"v": v} for v in [1, 2, 3, 5]]
    expected = [2, 2, 1, 1]
    via_desc = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=c.item("v").desc(),
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
        )
        .execute(data)
    )
    via_pipe = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=c.item("v").pipe(c.this).desc(),
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
        )
        .execute(data)
    )
    assert via_desc == expected
    assert via_pipe == expected


def test_range_offsets_require_single_order_by_key():
    with pytest.raises(ValueError):
        c.this.window(c.ReduceFuncs.Count()).over(
            order_by=(c.this, c.this),
            frame_start=(1, "PRECEDING"),
        )


def test_window_chained_order_by():
    result = (
        c.this.window(c.ReduceFuncs.Count())
        .over(order_by=c.item("a").item("b"))
        .execute([{"a": {"b": 1}, "b": 2}, {"a": {"b": 1}, "b": 3}])
    )
    assert result == [2, 2]

    result = (
        c.this.window(
            {
                "idx": c.WindowFuncs.RowIndex(),
                "count": c.ReduceFuncs.Count(),
            }
        )
        .over(order_by=c.item("a").item("b"))
        .execute([{"a": {"b": 2}, "b": 1}, {"a": {"b": 1}, "b": 1}])
    )
    assert result == [
        {"idx": 1, "count": 2},
        {"idx": 0, "count": 1},
    ]


_LAZY_FRAME_OPTS = dict(
    frame_mode="ROWS", frame_start="CURRENT ROW", frame_end="CURRENT ROW"
)


def test_window_lazy_row_index_current_row():
    reducer = c.ReduceFuncs.Array(c.this).iter(c.WindowFuncs.RowIndex())
    lazy = (
        c.this.window(reducer).over(**_LAZY_FRAME_OPTS).execute([10, 20, 30])
    )
    eager = (
        c.this.window(reducer.as_type(list))
        .over(**_LAZY_FRAME_OPTS)
        .execute([10, 20, 30])
    )
    lazy_result = [list(v) for v in lazy]
    assert lazy_result == [[0], [1], [2]]
    assert lazy_result == eager


def test_window_nested_deferred_row_index():
    reducer = c.ReduceFuncs.Array(c.this.iter(c.WindowFuncs.RowIndex()))
    result = (
        c.this.window(reducer)
        .over(**_LAZY_FRAME_OPTS)
        .execute([[10], [20], [30]])
    )
    assert [[list(g) for g in arr] for arr in result] == [
        [[0]],
        [[1]],
        [[2]],
    ]


def test_window_bare_sum_row_index():
    result = (
        c.this.window(c.ReduceFuncs.Sum(c.WindowFuncs.RowIndex()))
        .over(**_LAZY_FRAME_OPTS)
        .execute([10, 20, 30])
    )
    assert result == [0, 1, 2]


@pytest.mark.parametrize(
    "window_func",
    [
        pytest.param(c.WindowFuncs.RowIndex(), id="RowIndex"),
        pytest.param(c.WindowFuncs.Row(), id="Row"),
        pytest.param(c.WindowFuncs.RowPreceding(1), id="RowPreceding"),
        pytest.param(c.WindowFuncs.RowFollowing(1), id="RowFollowing"),
        pytest.param(c.WindowFuncs.PeerGroupIndex(), id="PeerGroupIndex"),
        pytest.param(
            c.WindowFuncs.PeerGroupFirstRowIndex(),
            id="PeerGroupFirstRowIndex",
        ),
        pytest.param(
            c.WindowFuncs.PeerGroupLastRowIndex(),
            id="PeerGroupLastRowIndex",
        ),
        pytest.param(
            c.WindowFuncs.PeerGroupFirstRow(), id="PeerGroupFirstRow"
        ),
        pytest.param(c.WindowFuncs.PeerGroupLastRow(), id="PeerGroupLastRow"),
    ],
)
@pytest.mark.parametrize("frame_mode", ["ROWS", "RANGE", "GROUPS"])
@pytest.mark.parametrize("with_partition", [False, True])
@pytest.mark.parametrize("with_order", [False, True])
def test_window_lazy_vs_eager_frame_metadata(
    window_func, frame_mode, with_partition, with_order
):
    data = [
        {"p": "a", "k": 1, "v": 10},
        {"p": "a", "k": 1, "v": 20},
        {"p": "a", "k": 2, "v": 30},
        {"p": "b", "k": 1, "v": 40},
        {"p": "b", "k": 2, "v": 50},
    ]
    over_kwargs = {
        "frame_mode": frame_mode,
        "frame_start": "CURRENT ROW",
        "frame_end": "CURRENT ROW",
    }
    if with_partition:
        over_kwargs["partition_by"] = c.item("p")
    if with_order:
        over_kwargs["order_by"] = c.item("k")

    lazy_reducer = c.ReduceFuncs.Array(c.this).iter(window_func)
    lazy = c.this.window(lazy_reducer).over(**over_kwargs).execute(data)
    eager = (
        c.this.window(lazy_reducer.as_type(list))
        .over(**over_kwargs)
        .execute(data)
    )
    assert [list(v) for v in lazy] == eager


def test_window_input_arg_partition_does_not_clash():
    result = (
        c.this.window(
            {
                "row": c.WindowFuncs.Row(),
                "arg": c.input_arg("partition"),
            }
        )
        .over(**_LAZY_FRAME_OPTS)
        .execute([10, 20, 30], partition="x")
    )
    assert result == [
        {"row": 10, "arg": "x"},
        {"row": 20, "arg": "x"},
        {"row": 30, "arg": "x"},
    ]


# TODO: ordering
