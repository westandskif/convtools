from convtools import conversion as c


data = [
    {"day": 1, "amount": 5},
    {"day": 2, "amount": 7},
    {"day": 3, "amount": 3},
    {"day": 4, "amount": 8},
]

result = (
    c.this.window(
        {
            "row": (
                c.WindowFuncs.Row().item("day"),
                c.WindowFuncs.Row().item("amount"),
            ),
            "rolling_sum": c.ReduceFuncs.Sum(c.item("amount")),
        }
    )
    .over(
        order_by=c.item("day"),
        frame_mode="ROWS",
        frame_start=(1, "PRECEDING"),
        frame_end="CURRENT ROW",
    )
    .execute(data)
)
assert result == [
    {"row": (1, 5), "rolling_sum": 5},
    {"row": (2, 7), "rolling_sum": 12},
    {"row": (3, 3), "rolling_sum": 10},
    {"row": (4, 8), "rolling_sum": 11},
]
