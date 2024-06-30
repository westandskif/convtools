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
            "dt_min": c.ReduceFuncs.Min(c.item("dt")).pipe(str),
            "dt_max": c.ReduceFuncs.Max(c.item("dt")).pipe(str),
            "idx": c.WindowFuncs.RowIndex(),
            "frame": c.ReduceFuncs.Array(c.item("b")),
        }
    )
    .over(
        order_by=c.item("dt"),
        frame_mode="GROUPS",
        frame_start=(1, "PRECEDING"),
        frame_end=(1, "FOLLOWING"),
    )
    .execute(data)
)
# fmt: off
assert result == [
    {"dt_min": "2020-01-01", "dt_max": "2020-01-02", "idx": 0, "frame": [1, 6, 3, 4, 2]},
    {"dt_min": "2020-01-01", "dt_max": "2020-01-02", "idx": 1, "frame": [1, 6, 3, 4, 2]},
    {"dt_min": "2020-01-01", "dt_max": "2020-01-03", "idx": 2, "frame": [1, 6, 3, 4, 2, 5]},
    {"dt_min": "2020-01-01", "dt_max": "2020-01-03", "idx": 3, "frame": [1, 6, 3, 4, 2, 5]},
    {"dt_min": "2020-01-01", "dt_max": "2020-01-03", "idx": 4, "frame": [1, 6, 3, 4, 2, 5]},
    {"dt_min": "2020-01-02", "dt_max": "2020-01-04", "idx": 5, "frame": [3, 4, 2, 5, 6]},
    {"dt_min": "2020-01-03", "dt_max": "2020-01-05", "idx": 6, "frame": [5, 6, 7]},
    {"dt_min": "2020-01-04", "dt_max": "2020-01-07", "idx": 7, "frame": [6, 7, 8]},
    {"dt_min": "2020-01-05", "dt_max": "2020-01-07", "idx": 8, "frame": [7, 8]},
]
# fmt: on
