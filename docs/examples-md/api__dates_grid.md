```python
from datetime import date, datetime
from convtools import DateGrid, DateTimeGrid
from convtools import conversion as c

# MONTHS
assert list(DateGrid("mo").around(date(1999, 12, 20), date(2000, 1, 3))) == [
    date(1999, 12, 1),
    date(2000, 1, 1),
]

# ENDS OF QUARTERS
assert list(
    DateGrid("3mo", mode="end_inclusive").around(
        date(1999, 12, 20), date(2000, 12, 3)
    )
) == [
    date(1999, 12, 31),
    date(2000, 3, 31),
    date(2000, 6, 30),
    date(2000, 9, 30),
    date(2000, 12, 31),
]

# EVERY 4TH THURSDAY
assert list(DateGrid("4thu").around(date(1999, 12, 20), date(2000, 5, 3))) == [
    date(1999, 12, 16),
    date(2000, 1, 13),
    date(2000, 2, 10),
    date(2000, 3, 9),
    date(2000, 4, 6),
]

# EVERY 8 HOURS SHIFTED BY 6 HOURS
assert list(
    DateTimeGrid("8h", "6h").around(
        datetime(2000, 2, 28, 15, 0), datetime(2000, 3, 1, 15, 0)
    )
) == [
    datetime(2000, 2, 28, 14, 0),
    datetime(2000, 2, 28, 22, 0),
    datetime(2000, 2, 29, 6, 0),
    datetime(2000, 2, 29, 14, 0),
    datetime(2000, 2, 29, 22, 0),
    datetime(2000, 3, 1, 6, 0),
    datetime(2000, 3, 1, 14, 0),
]

```
