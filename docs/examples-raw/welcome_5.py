import io
from decimal import Decimal

from convtools import conversion as c
from convtools.contrib.tables import Table

csv_buffer = io.StringIO(
    "order_id,price,qty,status\n"
    "a,20,2,paid\n"
    "a,30,3,refunded\n"
    "b,15,4,paid\n"
    "b,10,5,paid\n"
)

# Read a CSV (file path or buffer), infer header, and stream out a subset
pipe = (
    Table.from_csv(csv_buffer, header=True)  # or "orders.csv"
    .filter(c.col("status") == "paid")  # row-wise filter
    .update(total=c.col("price").as_type(Decimal) * c.col("qty").as_type(int))
    .take("order_id", "total")
    .into_iter_rows(dict)  # stream out or into_csv("output.csv")
)

assert list(pipe) == [
    {"order_id": "a", "total": Decimal("40")},
    {"order_id": "b", "total": Decimal("60")},
    {"order_id": "b", "total": Decimal("50")},
]
