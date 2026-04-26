```python
from convtools import conversion as c


input_data = {
    "orders": [
        {"store": "east", "sku": "A", "qty": 2},
        {"store": "east", "sku": "B", "qty": 1},
        {"store": "west", "sku": "A", "qty": 3},
    ],
    "prices": [
        {"store": "east", "sku": "A", "price": 10},
        {"store": "east", "sku": "B", "price": 8},
        {"store": "west", "sku": "A", "price": 12},
    ],
}

conv = (
    c.join(
        c.item("orders"),
        c.item("prices"),
        c.and_(
            c.LEFT.item("store") == c.RIGHT.item("store"),
            c.LEFT.item("sku") == c.RIGHT.item("sku"),
        ),
    )
    .pipe(
        c.list_comp(
            {
                "store": c.item(0, "store"),
                "sku": c.item(0, "sku"),
                "qty": c.item(0, "qty"),
                "price": c.item(1, "price"),
            }
        )
    )
    .gen_converter()
)

assert conv(input_data) == [
    {"store": "east", "sku": "A", "qty": 2, "price": 10},
    {"store": "east", "sku": "B", "qty": 1, "price": 8},
    {"store": "west", "sku": "A", "qty": 3, "price": 12},
]

```
