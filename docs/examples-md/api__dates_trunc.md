/// tab | convtools
    new: true

```python
from datetime import date, datetime
from convtools import conversion as c

# TRUNCATE TO MONTHS
converter = c.iter(c.date_trunc("mo")).as_type(list).gen_converter(debug=True)
assert converter(
    [
        date(1999, 12, 31),
        date(2000, 1, 10),
        date(2000, 2, 20),
    ]
) == [date(1999, 12, 1), date(2000, 1, 1), date(2000, 2, 1)]

# TRUNCATE TO MONTHS, RETURNS INCLUSIVE ENDS
converter = (
    c.iter(c.date_trunc("mo", mode="end_inclusive"))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(
    [
        date(1999, 12, 31),
        date(2000, 1, 10),
        date(2000, 2, 20),
    ]
) == [date(1999, 12, 31), date(2000, 1, 31), date(2000, 2, 29)]

# TRUNCATE TO 8h GRID, SHIFTED 6h FORWARD
converter = (
    c.iter(
        {
            "start": c.datetime_trunc("8h", "6h"),
            "end_inclusive": c.datetime_trunc(
                "8h", "6h", mode="end_inclusive"
            ),
        }
    )
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(
    [
        datetime(1999, 12, 31, 21, 1),
        datetime(2000, 1, 1, 2, 2),
        datetime(2000, 1, 1, 9, 3),
        datetime(2000, 1, 1, 15, 4),
    ]
) == [
    {
        "start": datetime(1999, 12, 31, 14, 0),
        "end_inclusive": datetime(1999, 12, 31, 21, 59, 59, 999999),
    },
    {
        "start": datetime(1999, 12, 31, 22, 0),
        "end_inclusive": datetime(2000, 1, 1, 5, 59, 59, 999999),
    },
    {
        "start": datetime(2000, 1, 1, 6, 0),
        "end_inclusive": datetime(2000, 1, 1, 13, 59, 59, 999999),
    },
    {
        "start": datetime(2000, 1, 1, 14, 0),
        "end_inclusive": datetime(2000, 1, 1, 21, 59, 59, 999999),
    },
]

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __date_trunc_to_month=__naive_values__["__date_trunc_to_month"]):
    try:
        return [__date_trunc_to_month(_i, 1, 0, 1) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __date_trunc_to_month=__naive_values__["__date_trunc_to_month"]):
    try:
        return [__date_trunc_to_month(_i, 1, 0, 3) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __datetime_trunc_to_microsecond=__naive_values__["__datetime_trunc_to_microsecond"]):
    try:
        return [
            {
                "start": __datetime_trunc_to_microsecond(_i, 28800000000, 21600000000, 1),
                "end_inclusive": __datetime_trunc_to_microsecond(_i, 28800000000, 21600000000, 3),
            }
            for _i in data_
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

