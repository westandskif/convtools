```python
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
            "neighbors": (
                c.WindowFuncs.RowPreceding(1).item("amount", default=None),
                c.WindowFuncs.RowFollowing(1).item("amount", default=None),
            ),
        }
    )
    .over(order_by=c.item("day"))
    .execute(data)
)
assert result == [
    {"row": (1, 5), "neighbors": (None, 7)},
    {"row": (2, 7), "neighbors": (5, 3)},
    {"row": (3, 3), "neighbors": (7, 8)},
    {"row": (4, 8), "neighbors": (3, None)},
]

```
