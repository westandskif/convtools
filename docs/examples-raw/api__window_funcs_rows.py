from datetime import date, timedelta
from convtools import conversion as c


data = [
    {"a": 1, "dt": date(2020, 1, 1), "b": 1},
    {"a": 2, "dt": date(2020, 1, 1), "b": 6},
    {"a": 1, "dt": date(2020, 1, 2), "b": 3},
    {"a": 1, "dt": date(2020, 1, 2), "b": 4},
    {"a": 1, "dt": date(2020, 1, 2), "b": 2},
    {"a": 1, "dt": date(2020, 1, 3), "b": 5},
    {"a": 1, "dt": date(2020, 1, 3), "b": None},
    {"a": 1, "dt": date(2020, 1, 4), "b": 6},
    {"a": 1, "dt": date(2020, 1, 5), "b": 7},
    {"a": 1, "dt": date(2020, 1, 7), "b": 8},
]

result = (
    c.this.window(
        {
            "sum": c.ReduceFuncs.Sum(c.item("b")),
            "idx": c.WindowFuncs.RowIndex(),
            "frame": c.ReduceFuncs.Array(c.item("b")),
        }
    )
    .over(
        order_by=c.item("b").desc(none_last=True),
        frame_mode="ROWS",
        frame_start="UNBOUNDED PRECEDING",
        frame_end="CURRENT ROW",
    )
    .execute(data)
)
assert result == [
    {"sum": 42, "idx": 8, "frame": [8, 7, 6, 6, 5, 4, 3, 2, 1]},
    {"sum": 21, "idx": 2, "frame": [8, 7, 6]},
    {"sum": 39, "idx": 6, "frame": [8, 7, 6, 6, 5, 4, 3]},
    {"sum": 36, "idx": 5, "frame": [8, 7, 6, 6, 5, 4]},
    {"sum": 41, "idx": 7, "frame": [8, 7, 6, 6, 5, 4, 3, 2]},
    {"sum": 32, "idx": 4, "frame": [8, 7, 6, 6, 5]},
    {"sum": 42, "idx": 9, "frame": [8, 7, 6, 6, 5, 4, 3, 2, 1, None]},
    {"sum": 27, "idx": 3, "frame": [8, 7, 6, 6]},
    {"sum": 15, "idx": 1, "frame": [8, 7]},
    {"sum": 8, "idx": 0, "frame": [8]},
]
