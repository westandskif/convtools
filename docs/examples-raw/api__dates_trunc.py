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
