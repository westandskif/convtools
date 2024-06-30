from datetime import date, timedelta
from convtools import conversion as c


data = [
    {"a": 1, "dt": date(2020, 1, 1), "b": 1},
    {"a": 2, "dt": date(2020, 1, 1), "b": 6},
    {"a": 1, "dt": date(2020, 1, 2), "b": 3},
    {"a": 1, "dt": date(2020, 1, 2), "b": 4},
    {"a": 1, "dt": date(2020, 1, 2), "b": 2},
    {"a": 1, "dt": date(2020, 1, 3), "b": 5},
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
        partition_by=c.item("a"),
        order_by=c.item("dt"),
        frame_mode="RANGE",
        frame_start=(timedelta(days=1), "PRECEDING"),
        frame_end=(timedelta(days=1), "FOLLOWING"),
    )
    .execute(data)
)
assert result == [
    {"sum": 10, "idx": 0, "frame": [1, 3, 4, 2]},
    {"sum": 6, "idx": 0, "frame": [6]},
    {"sum": 15, "idx": 1, "frame": [1, 3, 4, 2, 5]},
    {"sum": 15, "idx": 2, "frame": [1, 3, 4, 2, 5]},
    {"sum": 15, "idx": 3, "frame": [1, 3, 4, 2, 5]},
    {"sum": 20, "idx": 4, "frame": [3, 4, 2, 5, 6]},
    {"sum": 18, "idx": 5, "frame": [5, 6, 7]},
    {"sum": 13, "idx": 6, "frame": [6, 7]},
    {"sum": 8, "idx": 7, "frame": [8]},
]
