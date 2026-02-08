```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows(
            [
                {"dept": 1, "year": 2023, "currency": "USD", "revenue": 100},
                {"dept": 1, "year": 2024, "currency": "USD", "revenue": 300},
                {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 200},
                {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 111},
            ]
        )
        .pivot(
            rows=["year", "dept"],
            columns=["currency"],
            values={
                "sum": c.ReduceFuncs.Sum(c.col("revenue")),
                "min": c.ReduceFuncs.Min(c.col("revenue")),
            },
        )
        .into_iter_rows(dict)
    ) == [
        {
            "CNY - min": None,
            "CNY - sum": None,
            "USD - min": 100,
            "USD - sum": 100,
            "dept": 1,
            "year": 2023,
        },
        {
            "CNY - min": 111,
            "CNY - sum": 311,
            "USD - min": 300,
            "USD - sum": 300,
            "dept": 1,
            "year": 2024,
        },
    ]

```
