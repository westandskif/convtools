import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from convtools import conversion as c
from convtools._window import iter_frame

from .utils import get_code_str


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

    assert list(c.iter_windows(3, step=1).execute(range(2))) == [
        (0,),
        (0, 1),
        (0, 1),
        (1,),
    ]
    assert list(c.iter_windows(3, step=1).execute(range(1))) == [
        (0,),
        (0,),
        (0,),
    ]
    assert list(c.iter_windows(3, step=2).execute(range(2))) == [
        (0,),
        (0, 1),
    ]
    for width, step in ((0, 1), (1, 0), (-1, 1)):
        with pytest.raises(ValueError):
            c.iter_windows(width, step=step).execute(range(3))


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


def test_row_preceding_following_signed_offset():
    data = list(range(10))
    following_neg2 = (
        c.this.window(c.WindowFuncs.RowFollowing(-2))
        .over(order_by=c.this)
        .execute(data)
    )
    preceding_2 = (
        c.this.window(c.WindowFuncs.RowPreceding(2))
        .over(order_by=c.this)
        .execute(data)
    )
    assert following_neg2 == [None, None, 0, 1, 2, 3, 4, 5, 6, 7]
    assert following_neg2 == preceding_2

    preceding_neg2 = (
        c.this.window(c.WindowFuncs.RowPreceding(-2))
        .over(order_by=c.this)
        .execute(data)
    )
    following_2 = (
        c.this.window(c.WindowFuncs.RowFollowing(2))
        .over(order_by=c.this)
        .execute(data)
    )
    assert preceding_neg2 == [2, 3, 4, 5, 6, 7, 8, 9, None, None]
    assert preceding_neg2 == following_2

    following_neg2_default = (
        c.this.window(c.WindowFuncs.RowFollowing(-2, default=-1))
        .over(order_by=c.this)
        .execute(data)
    )
    preceding_2_default = (
        c.this.window(c.WindowFuncs.RowPreceding(2, default=-1))
        .over(order_by=c.this)
        .execute(data)
    )
    assert following_neg2_default == [-1, -1, 0, 1, 2, 3, 4, 5, 6, 7]
    assert following_neg2_default == preceding_2_default

    preceding_neg2_default = (
        c.this.window(c.WindowFuncs.RowPreceding(-2, default=-1))
        .over(order_by=c.this)
        .execute(data)
    )
    following_2_default = (
        c.this.window(c.WindowFuncs.RowFollowing(2, default=-1))
        .over(order_by=c.this)
        .execute(data)
    )
    assert preceding_neg2_default == [2, 3, 4, 5, 6, 7, 8, 9, -1, -1]
    assert preceding_neg2_default == following_2_default

    offset_0 = (
        c.this.window(c.WindowFuncs.RowFollowing(0))
        .over(order_by=c.this)
        .execute(data)
    )
    assert offset_0 == data
    assert (
        c.this.window(c.WindowFuncs.RowPreceding(0))
        .over(order_by=c.this)
        .execute(data)
    ) == data

    n = len(data)
    for helper, k in (
        (c.WindowFuncs.RowFollowing, n),
        (c.WindowFuncs.RowFollowing, n + 1),
        (c.WindowFuncs.RowPreceding, n),
        (c.WindowFuncs.RowPreceding, n + 1),
        (c.WindowFuncs.RowFollowing, -n),
        (c.WindowFuncs.RowFollowing, -(n + 1)),
        (c.WindowFuncs.RowPreceding, -n),
        (c.WindowFuncs.RowPreceding, -(n + 1)),
    ):
        result = (
            c.this.window(helper(k, default=-1))
            .over(order_by=c.this)
            .execute(data)
        )
        assert result == [-1] * n

    conv_offset = (
        c.this.window(c.WindowFuncs.RowFollowing(c.input_arg("k")))
        .over(order_by=c.this)
        .execute(data, k=-2)
    )
    assert conv_offset == following_neg2


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

    with pytest.raises(ValueError):
        c.this.window(1).over(
            frame_mode="ROWS", frame_start=(True, "PRECEDING")
        )
    with pytest.raises(ValueError):
        c.this.window(1).over(
            frame_mode="RANGE",
            order_by=c.this,
            frame_start=(True, "PRECEDING"),
        )
    with pytest.raises(ValueError, match="numeric or timedelta"):
        c.this.window(1).over(
            frame_mode="RANGE",
            order_by=c.this,
            frame_start=("x", "PRECEDING"),
        )


@pytest.mark.parametrize("frame_mode", ["ROWS", "GROUPS", "RANGE"])
@pytest.mark.parametrize(
    "kwargs",
    [
        {"frame_start": (None, "PRECEDING")},
        {"frame_end": (None, "FOLLOWING")},
    ],
)
def test_window_none_frame_offset_rejected(frame_mode, kwargs):
    with pytest.raises(ValueError, match="unsupported window frame offset"):
        c.this.window(1).over(frame_mode=frame_mode, **kwargs)


def test_iter_frame_binds_args_not_loop_vars():
    data = [0, 1, 2, 3, 4]
    start, end = 1, 4
    gen = iter_frame(data, start, end)
    start, end = 0, 1
    other = [9, 9, 9, 9, 9]
    other[:] = other
    assert list(gen) == [1, 2, 3]

    assert list(iter_frame(data, 3, 1)) == []

    class ObservingList(list):
        def __init__(self, *args):
            super().__init__(*args)
            self.accessed = []

        def __getitem__(self, index):
            self.accessed.append(index)
            return list.__getitem__(self, index)

    observed = ObservingList([10, 20, 30, 40])
    gen = iter_frame(observed, 0, 4)
    assert next(gen) == 10
    del gen
    assert observed.accessed == [0]


def test_window_frame_iter_generated_code():
    bounded = get_code_str(
        c.this.window(c.ReduceFuncs.Sum(c.this)).over(
            frame_mode="ROWS",
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
        )
    )
    assert "iter_frame(" in bounded
    assert "itertools_islice(" not in bounded

    for frame_mode in ("ROWS", "GROUPS", "RANGE"):
        default = get_code_str(
            c.this.window(c.ReduceFuncs.Sum(c.this)).over(
                frame_mode=frame_mode
            )
        )
        assert "itertools_islice(data_, 0," in default
        assert "iter_frame(" not in default

    unbounded_excl = get_code_str(
        c.this.window(c.ReduceFuncs.Sum(c.this)).over(
            frame_mode="ROWS",
            frame_exclusion="CURRENT ROW",
        )
    )
    assert "itertools_islice(data_, 0," in unbounded_excl
    assert "iter_frame(" in unbounded_excl

    bounded_excl = get_code_str(
        c.this.window(c.ReduceFuncs.Sum(c.this)).over(
            frame_mode="ROWS",
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
            frame_exclusion="CURRENT ROW",
        )
    )
    assert "iter_frame(" in bounded_excl
    assert "itertools_islice(" not in bounded_excl


@pytest.mark.parametrize("frame_mode", ["ROWS", "GROUPS", "RANGE"])
@pytest.mark.parametrize(
    "frame_exclusion, expected_array, expected_first, expected_last",
    [
        (
            "NO OTHERS",
            {
                "ROWS": [[1], [1, 1], [1, 2]],
                "GROUPS": [[1, 1], [1, 1], [1, 1, 2]],
                "RANGE": [[1, 1], [1, 1], [1, 1, 2]],
            },
            {
                "ROWS": [1, 1, 1],
                "GROUPS": [1, 1, 1],
                "RANGE": [1, 1, 1],
            },
            {
                "ROWS": [1, 1, 2],
                "GROUPS": [1, 1, 2],
                "RANGE": [1, 1, 2],
            },
        ),
        (
            "CURRENT ROW",
            {
                "ROWS": [None, [1], [1]],
                "GROUPS": [[1], [1], [1, 1]],
                "RANGE": [[1], [1], [1, 1]],
            },
            {
                "ROWS": [None, 1, 1],
                "GROUPS": [1, 1, 1],
                "RANGE": [1, 1, 1],
            },
            {
                "ROWS": [None, 1, 1],
                "GROUPS": [1, 1, 1],
                "RANGE": [1, 1, 1],
            },
        ),
        (
            "GROUP",
            {
                "ROWS": [None, None, [1]],
                "GROUPS": [None, None, [1, 1]],
                "RANGE": [None, None, [1, 1]],
            },
            {
                "ROWS": [None, None, 1],
                "GROUPS": [None, None, 1],
                "RANGE": [None, None, 1],
            },
            {
                "ROWS": [None, None, 1],
                "GROUPS": [None, None, 1],
                "RANGE": [None, None, 1],
            },
        ),
        (
            "TIES",
            {
                "ROWS": [[1], [1], [1, 2]],
                "GROUPS": [[1], [1], [1, 1, 2]],
                "RANGE": [[1], [1], [1, 1, 2]],
            },
            {
                "ROWS": [1, 1, 1],
                "GROUPS": [1, 1, 1],
                "RANGE": [1, 1, 1],
            },
            {
                "ROWS": [1, 1, 2],
                "GROUPS": [1, 1, 2],
                "RANGE": [1, 1, 2],
            },
        ),
    ],
)
def test_window_bounded_frame_exclusions_with_ties(
    frame_mode, frame_exclusion, expected_array, expected_first, expected_last
):
    data = [1, 1, 2]
    over_kwargs = dict(
        frame_mode=frame_mode,
        order_by=c.this,
        frame_start=(1, "PRECEDING"),
        frame_end="CURRENT ROW",
        frame_exclusion=frame_exclusion,
    )
    array_result = (
        c.this.window(c.ReduceFuncs.Array(c.this))
        .over(**over_kwargs)
        .execute(data)
    )
    first_result = (
        c.this.window(c.WindowFuncs.FrameFirstRow())
        .over(**over_kwargs)
        .execute(data)
    )
    last_result = (
        c.this.window(c.WindowFuncs.FrameLastRow())
        .over(**over_kwargs)
        .execute(data)
    )
    assert array_result == expected_array[frame_mode]
    assert first_result == expected_first[frame_mode]
    assert last_result == expected_last[frame_mode]


@pytest.mark.parametrize(
    "kwargs, match",
    [
        (
            {"frame_mode": "GROUPS", "frame_start": (-1, "PRECEDING")},
            "offsets should be non-negative",
        ),
        (
            {"frame_mode": "GROUPS", "frame_start": (1.5, "PRECEDING")},
            "offsets should be non-negative",
        ),
        (
            {"frame_mode": "RANGE", "frame_start": (1, "PRECEDING")},
            "require 'order_by'",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (-1, "PRECEDING"),
            },
            "offsets should be non-negative",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (-1.0, "PRECEDING"),
            },
            "offsets should be non-negative",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (Decimal("-1"), "PRECEDING"),
            },
            "offsets should be non-negative",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (-timedelta(days=1), "PRECEDING"),
            },
            "offsets should be non-negative",
        ),
        (
            {
                "frame_mode": "ROWS",
                "frame_start": "CURRENT ROW",
                "frame_end": (1, "PRECEDING"),
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": "CURRENT ROW",
                "frame_end": (1, "PRECEDING"),
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "GROUPS",
                "frame_start": "CURRENT ROW",
                "frame_end": (1, "PRECEDING"),
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "ROWS",
                "frame_start": (1, "FOLLOWING"),
                "frame_end": "CURRENT ROW",
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (1, "FOLLOWING"),
                "frame_end": "CURRENT ROW",
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "GROUPS",
                "frame_start": (1, "FOLLOWING"),
                "frame_end": "CURRENT ROW",
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "ROWS",
                "frame_start": (1, "FOLLOWING"),
                "frame_end": (1, "PRECEDING"),
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (1, "FOLLOWING"),
                "frame_end": (1, "PRECEDING"),
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "GROUPS",
                "frame_start": (1, "FOLLOWING"),
                "frame_end": (1, "PRECEDING"),
            },
            "frame start cannot be after frame end",
        ),
        (
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (Fraction(-1), "PRECEDING"),
            },
            "offsets should be non-negative",
        ),
    ],
)
def test_window_frame_offset_validation(kwargs, match):
    with pytest.raises(ValueError, match=match):
        c.this.window(c.ReduceFuncs.Count()).over(**kwargs)


def test_range_fraction_offset_matches_int():
    data = [1, 2, 3, 5]
    via_int = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=c.this,
            frame_start=(1, "PRECEDING"),
            frame_end="CURRENT ROW",
        )
        .execute(data)
    )
    via_fraction = (
        c.this.window(c.ReduceFuncs.Count())
        .over(
            order_by=c.this,
            frame_start=(Fraction(1), "PRECEDING"),
            frame_end="CURRENT ROW",
        )
        .execute(data)
    )
    assert via_fraction == via_int


def test_range_custom_non_orderable_offset():
    class Delta(object):
        def __init__(self, n):
            self.n = n

        def __radd__(self, other):
            return other + self.n

        def __rsub__(self, other):
            return other - self.n

    with pytest.raises(ValueError, match="numeric or timedelta"):
        c.this.window(c.ReduceFuncs.Count()).over(
            order_by=c.this,
            frame_start=(Delta(1), "PRECEDING"),
            frame_end=(Delta(1), "FOLLOWING"),
        )


@pytest.mark.parametrize(
    "over_kwargs",
    [
        {
            "frame_mode": "ROWS",
            "frame_start": "CURRENT ROW",
            "frame_end": (0, "PRECEDING"),
        },
        {
            "frame_mode": "GROUPS",
            "order_by": c.this,
            "frame_start": "CURRENT ROW",
            "frame_end": (0, "PRECEDING"),
        },
        {
            "frame_mode": "RANGE",
            "order_by": c.this,
            "frame_start": "CURRENT ROW",
            "frame_end": (0, "PRECEDING"),
        },
        {
            "frame_mode": "ROWS",
            "frame_start": (0, "FOLLOWING"),
            "frame_end": "CURRENT ROW",
        },
    ],
)
def test_window_zero_offset_is_current_row(over_kwargs):
    data = [1, 1, 2]
    result = (
        c.this.window(c.ReduceFuncs.Count()).over(**over_kwargs).execute(data)
    )
    current_row_kwargs = dict(over_kwargs)
    current_row_kwargs["frame_start"] = "CURRENT ROW"
    current_row_kwargs["frame_end"] = "CURRENT ROW"
    expected = (
        c.this.window(c.ReduceFuncs.Count())
        .over(**current_row_kwargs)
        .execute(data)
    )
    if over_kwargs["frame_mode"] == "ROWS":
        peer_counts = [1, 1, 1]
    else:
        peer_counts = [2, 2, 1]
    assert result == expected == peer_counts


@pytest.mark.parametrize(
    "over_kwargs",
    [
        {
            "frame_mode": "ROWS",
            "frame_start": (0, "PRECEDING"),
            "frame_end": (2, "PRECEDING"),
        },
        {
            "frame_mode": "ROWS",
            "frame_start": (1, "FOLLOWING"),
            "frame_end": "CURRENT ROW",
        },
    ],
)
def test_window_zero_offset_still_rejects_inverted_frames(over_kwargs):
    with pytest.raises(ValueError):
        c.this.window(c.ReduceFuncs.Count()).over(**over_kwargs)


@pytest.mark.parametrize(
    "data, over_kwargs",
    [
        (
            [1, 2, 3],
            {
                "frame_mode": "ROWS",
                "order_by": c.this,
                "frame_start": (2, "FOLLOWING"),
                "frame_end": (1, "FOLLOWING"),
            },
        ),
        (
            [1, 2, 3],
            {
                "frame_mode": "ROWS",
                "order_by": c.this,
                "frame_start": (1, "PRECEDING"),
                "frame_end": (2, "PRECEDING"),
            },
        ),
        (
            [1, 2, 3],
            {
                "frame_mode": "GROUPS",
                "order_by": c.this,
                "frame_start": (2, "FOLLOWING"),
                "frame_end": (1, "FOLLOWING"),
            },
        ),
        (
            [1, 2, 3],
            {
                "frame_mode": "GROUPS",
                "order_by": c.this,
                "frame_start": (1, "PRECEDING"),
                "frame_end": (2, "PRECEDING"),
            },
        ),
        (
            [1, 2, 3],
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (2, "FOLLOWING"),
                "frame_end": (1, "FOLLOWING"),
            },
        ),
        (
            [1, 2, 3],
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (1, "PRECEDING"),
                "frame_end": (2, "PRECEDING"),
            },
        ),
        (
            [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (timedelta(days=2), "FOLLOWING"),
                "frame_end": (timedelta(days=1), "FOLLOWING"),
            },
        ),
        (
            [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
            {
                "frame_mode": "RANGE",
                "order_by": c.this,
                "frame_start": (timedelta(days=1), "PRECEDING"),
                "frame_end": (timedelta(days=2), "PRECEDING"),
            },
        ),
    ],
)
def test_window_same_direction_empty_frames(data, over_kwargs):
    array_result = (
        c.this.window(c.ReduceFuncs.Array(c.this))
        .over(**over_kwargs)
        .execute(data)
    )
    assert array_result == [None, None, None]
    count_result = (
        c.this.window(c.ReduceFuncs.Count()).over(**over_kwargs).execute(data)
    )
    assert count_result == [0, 0, 0]


def test_window_empty_runtime_frame_keeps_default():
    result = (
        c.this.window(c.ReduceFuncs.Sum(c.this))
        .over(
            frame_mode="ROWS",
            frame_start=(5, "FOLLOWING"),
            frame_end=(6, "FOLLOWING"),
        )
        .execute([1, 2, 3])
    )
    assert result == [0, 0, 0]


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


def test_window_order_by_last_hint_wins():
    data = [{"v": v} for v in [1, 3, 2]]
    via_asc = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=c.item("v").asc())
        .execute(data)
    )
    via_desc = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=c.item("v").desc())
        .execute(data)
    )
    via_desc_asc = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=c.item("v").desc().asc())
        .execute(data)
    )
    via_asc_desc = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=c.item("v").asc().desc())
        .execute(data)
    )
    via_pipe_desc_asc = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=c.item("v").pipe(c.this).desc().asc())
        .execute(data)
    )
    assert via_desc_asc == via_asc
    assert via_pipe_desc_asc == via_asc
    assert via_asc_desc == via_desc
    assert via_asc != via_desc


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


def test_window_order_by_list_equals_tuple():
    data = [(1,), (2,), (3,)]
    expected = [2, 1, 0]
    via_tuple = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=(c.item(0).desc(),))
        .execute(data)
    )
    via_list = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=[c.item(0).desc()])
        .execute(data)
    )
    assert via_tuple == expected
    assert via_list == expected

    none_data = [(None,), (1,), (2,)]
    none_expected = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=(c.item(0).desc(none_last=True),))
        .execute(none_data)
    )
    none_list = (
        c.this.window(c.WindowFuncs.RowIndex())
        .over(order_by=[c.item(0).desc(none_last=True)])
        .execute(none_data)
    )
    assert none_list == none_expected


def test_window_partition_by_list_single_key():
    data = [(0, 1), (1, 2), (0, 3)]
    via_conv = (
        c.this.window(c.ReduceFuncs.Count())
        .over(partition_by=c.item(0))
        .execute(data)
    )
    via_list = (
        c.this.window(c.ReduceFuncs.Count())
        .over(partition_by=[c.item(0)])
        .execute(data)
    )
    via_tuple = (
        c.this.window(c.ReduceFuncs.Count())
        .over(partition_by=(c.item(0),))
        .execute(data)
    )
    assert via_list == via_conv
    assert via_tuple == via_conv
    assert via_conv == [2, 1, 2]

    multi = [(0, 1), (0, 2), (0, 1)]
    via_multi_tuple = (
        c.this.window(c.ReduceFuncs.Count())
        .over(partition_by=(c.item(0), c.item(1)))
        .execute(multi)
    )
    via_multi_list = (
        c.this.window(c.ReduceFuncs.Count())
        .over(partition_by=[c.item(0), c.item(1)])
        .execute(multi)
    )
    assert via_multi_list == via_multi_tuple
    assert via_multi_tuple == [2, 1, 2]


def test_window_single_key_order_by_input_arg_and_label():
    data = [{"k": (i * 7) % 5, "v": i} for i in range(6)]
    assert c.this.window(c.WindowFuncs.RowIndex()).over(
        order_by=c.item("k") * c.input_arg("m")
    ).execute(data, m=1) == [0, 3, 5, 2, 4, 1]
    assert (
        c.this.pipe(c.this, label_output="rows")
        .window(c.WindowFuncs.RowIndex())
        .over(order_by=c.item("k") * c.label("rows").pipe(len))
        .execute(data)
    ) == [0, 3, 5, 2, 4, 1]


def test_window_order_by_rejects_plain_callable():
    with pytest.raises(TypeError, match="key sequence elements"):
        (
            c.this.window(c.ReduceFuncs.Count())
            .over(order_by=(c.item("a"), lambda x: 1))
            .gen_converter()
        )


def test_window_order_by_none_hint_binds_once():
    data = [{"a": None}, {"a": 2}, {"a": 1}]
    spec = c.this.window(c.ReduceFuncs.Count()).over(
        order_by=c.item("a").desc(none_last=True)
    )
    converter = spec.gen_converter()
    code = get_code_str(converter)
    assert "ReversedOrdering" in code
    assert "is None, ReversedOrdering(data_" not in code
    assert "v0 = " in code
    assert spec.execute(data) == [3, 1, 2]
