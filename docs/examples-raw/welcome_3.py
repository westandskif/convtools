from convtools import conversion as c

orders = [
    {"user": "a", "amount": 20, "status": "paid"},
    {"user": "a", "amount": 30, "status": "refunded"},
    {"user": "b", "amount": 15, "status": "paid"},
    {"user": "b", "amount": 10, "status": "paid"},
]

group_and_sum_paid = (
    c.group_by(c.item("user"))
    .aggregate(
        {
            "user": c.item("user"),
            "paid_total": c.ReduceFuncs.Sum(
                c.item("amount"),
                where=c.item("status") == "paid",
            ),
        }
    )
    .sort(key=c.item("paid_total").desc())
    .gen_converter()
)

assert group_and_sum_paid(orders) == [
    {"user": "b", "paid_total": 25},
    {"user": "a", "paid_total": 20},
]
