from convtools import conversion as c


totals_by_region = (
    c.group_by(c.item("region"))
    .aggregate(
        {
            "region": c.item("region"),
            "total": c.ReduceFuncs.Sum(c.item("amount")),
        }
    )
    .gen_converter()
)
assert totals_by_region(
    [{"region": "EU", "amount": 10}, {"region": "EU", "amount": 5}]
) == [{"region": "EU", "total": 15}]
