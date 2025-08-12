```python
from convtools import conversion as c
from convtools.contrib.tables import Table
from decimal import Decimal

# tests/csvs/orders.csv
"""
order_id,price,qty,status
a,20,2,paid
a,30,3,refunded
b,15,4,paid
b,10,5,paid
"""

# Read a CSV, infer header, and stream out a subset
pipe = (
    Table.from_csv("tests/csvs/orders.csv", header=True)  # stream in
    .filter(c.col("status") == "paid")  # row-wise filter
    .update(total=c.col("price").as_type(Decimal) * c.col("qty").as_type(int))
    .take("order_id", "total")
    .into_iter_rows(dict)  # stream out or .into_csv("out.csv")
)

assert list(pipe) == [
    {"order_id": "a", "total": Decimal("40")},
    {"order_id": "b", "total": Decimal("60")},
    {"order_id": "b", "total": Decimal("50")},
]

```
