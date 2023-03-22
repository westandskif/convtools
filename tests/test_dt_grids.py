from datetime import date, datetime, timedelta, timezone
from time import time

import pytest

from convtools import DateGrid, DateTimeGrid
from convtools import conversion as c


def utc(*args, **kwargs):
    return datetime(*args, tzinfo=kwargs.pop("tzinfo", timezone.utc), **kwargs)


def test_date_grid():
    result = list(DateGrid("y").around(date(2000, 1, 1), date(2004, 1, 1)))
    assert result == [
        date(2000, 1, 1),
        date(2001, 1, 1),
        date(2002, 1, 1),
        date(2003, 1, 1),
        date(2004, 1, 1),
    ]
    result = list(DateGrid("1y").around(date(1999, 12, 31), date(2004, 1, 2)))
    assert result == [
        date(1999, 1, 1),
        date(2000, 1, 1),
        date(2001, 1, 1),
        date(2002, 1, 1),
        date(2003, 1, 1),
        date(2004, 1, 1),
    ]

    result = list(
        DateGrid("1y", mode="end_inclusive").around(
            date(1999, 12, 31), date(2004, 1, 2)
        )
    )
    assert result == [
        date(1999, 12, 31),
        date(2000, 12, 31),
        date(2001, 12, 31),
        date(2002, 12, 31),
        date(2003, 12, 31),
        date(2004, 12, 31),
    ]
    result = list(
        DateGrid("1y", mode="end").around(date(1999, 12, 31), date(2004, 1, 2))
    )
    assert result == [
        date(2000, 1, 1),
        date(2001, 1, 1),
        date(2002, 1, 1),
        date(2003, 1, 1),
        date(2004, 1, 1),
        date(2005, 1, 1),
    ]

    result = list(
        DateGrid("4y", "1y").around(date(2000, 1, 1), date(2010, 1, 1))
    )
    assert result == [
        date(1997, 1, 1),
        date(2001, 1, 1),
        date(2005, 1, 1),
        date(2009, 1, 1),
    ]
    result = list(
        DateGrid("4y", offset="1y", mode="end_inclusive").around(
            date(2000, 1, 1), date(2010, 1, 1)
        )
    )
    assert result == [
        date(2000, 12, 31),
        date(2004, 12, 31),
        date(2008, 12, 31),
        date(2012, 12, 31),
    ]

    result = list(DateGrid("mo").around(date(1999, 12, 31), date(2000, 3, 31)))
    assert result == [
        date(1999, 12, 1),
        date(2000, 1, 1),
        date(2000, 2, 1),
        date(2000, 3, 1),
    ]

    result = list(
        DateGrid("mo", mode="end_inclusive").around(
            date(1999, 12, 31), date(2000, 3, 31)
        )
    )
    assert result == [
        date(1999, 12, 31),
        date(2000, 1, 31),
        date(2000, 2, 29),
        date(2000, 3, 31),
    ]

    result = list(
        DateGrid("mo", mode="end").around(
            date(1999, 12, 31), date(2000, 3, 31)
        )
    )
    assert result == [
        date(2000, 1, 1),
        date(2000, 2, 1),
        date(2000, 3, 1),
        date(2000, 4, 1),
    ]

    result = list(
        DateGrid("3mo", "1mo").around(date(1999, 12, 31), date(2001, 3, 31))
    )
    assert result == [
        date(1999, 11, 1),
        date(2000, 2, 1),
        date(2000, 5, 1),
        date(2000, 8, 1),
        date(2000, 11, 1),
        date(2001, 2, 1),
    ]

    result = list(
        DateGrid("3mo", "1mo", mode="end_inclusive").around(
            date(1999, 12, 31), date(2001, 3, 31)
        )
    )
    assert result == [
        date(2000, 1, 31),
        date(2000, 4, 30),
        date(2000, 7, 31),
        date(2000, 10, 31),
        date(2001, 1, 31),
        date(2001, 4, 30),
    ]

    result = list(
        DateGrid("3mo", "1mo", mode="end").around(
            date(1999, 12, 31), date(2001, 3, 31)
        )
    )
    assert result == [
        date(2000, 2, 1),
        date(2000, 5, 1),
        date(2000, 8, 1),
        date(2000, 11, 1),
        date(2001, 2, 1),
        date(2001, 5, 1),
    ]

    result = list(DateGrid("mon").around(date(2000, 2, 10), date(2000, 3, 5)))
    assert result == [
        date(2000, 2, 7),
        date(2000, 2, 14),
        date(2000, 2, 21),
        date(2000, 2, 28),
    ]
    result = list(DateGrid("tue").around(date(2000, 2, 10), date(2000, 3, 5)))
    assert result == [
        date(2000, 2, 8),
        date(2000, 2, 15),
        date(2000, 2, 22),
        date(2000, 2, 29),
    ]

    result = list(DateGrid("2tue").around(date(2000, 2, 10), date(2000, 3, 5)))
    assert result == [date(2000, 2, 8), date(2000, 2, 22)]

    result = list(
        DateGrid("2tue", mode="end_inclusive").around(
            date(2000, 2, 10), date(2000, 3, 5)
        )
    )
    assert result == [date(2000, 2, 21), date(2000, 3, 6)]

    result = list(
        DateGrid("2tue", mode="end").around(
            date(2000, 2, 10), date(2000, 3, 5)
        )
    )
    assert result == [date(2000, 2, 22), date(2000, 3, 7)]

    result = list(DateGrid("10d").around(date(2000, 2, 10), date(2000, 3, 5)))
    assert result == [
        date(2000, 2, 10),
        date(2000, 2, 20),
        date(2000, 3, 1),
    ]
    result = list(
        DateGrid("10d", "-d").around(date(2000, 2, 10), date(2000, 3, 5))
    )
    assert result == [date(2000, 2, 9), date(2000, 2, 19), date(2000, 2, 29)]
    result = list(
        DateGrid("10d", "-d", mode="end_inclusive").around(
            date(2000, 2, 10), date(2000, 3, 5)
        )
    )
    assert result == [date(2000, 2, 18), date(2000, 2, 28), date(2000, 3, 9)]
    result = list(
        DateGrid("10d", "-d", mode="end").around(
            date(2000, 2, 10), date(2000, 3, 5)
        )
    )
    assert result == [date(2000, 2, 19), date(2000, 2, 29), date(2000, 3, 10)]


def test_datetime_grid():
    result = list(DateTimeGrid("y").around(utc(2000, 1, 1), utc(2004, 1, 1)))
    assert result == [
        datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2002, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2003, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2004, 1, 1, 0, 0, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("1y").around(
            utc(1999, 12, 31, 23, 59, 59, 999999), utc(2004, 1, 2)
        )
    )
    assert result == [
        datetime(1999, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2002, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2003, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2004, 1, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("1y", mode="end_inclusive").around(
            utc(1999, 12, 31), utc(2004, 1, 2)
        )
    )
    assert result == [
        datetime(1999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2001, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2002, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2003, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2004, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("1y", mode="end").around(
            utc(1999, 12, 31), utc(2004, 1, 2)
        )
    )
    assert result == [
        datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2002, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2003, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2004, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2005, 1, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("4y", "1y").around(utc(2000, 1, 1), utc(2010, 1, 1))
    )
    assert result == [
        datetime(1997, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2005, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2009, 1, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("4y", offset="1y", mode="end_inclusive").around(
            utc(2000, 1, 1), utc(2010, 1, 1)
        )
    )
    assert result == [
        datetime(2000, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2004, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2008, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2012, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("mo").around(utc(1999, 12, 31), utc(2000, 3, 31))
    )
    assert result == [
        datetime(1999, 12, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 3, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("mo", mode="end_inclusive").around(
            utc(1999, 12, 31, 23, 59, 59, 999999), utc(2000, 3, 31)
        )
    )
    assert result == [
        datetime(1999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 1, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 29, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 3, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("mo", mode="end").around(
            utc(1999, 12, 31), utc(2000, 3, 31)
        )
    )
    assert result == [
        datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 3, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 4, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("3mo", "1mo").around(utc(1999, 12, 31), utc(2001, 3, 31))
    )
    assert result == [
        datetime(1999, 11, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 5, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 8, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 11, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 2, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("3mo", "1mo", mode="end_inclusive").around(
            utc(1999, 12, 31), utc(2001, 3, 31)
        )
    )
    assert result == [
        datetime(2000, 1, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 4, 30, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 7, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 10, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2001, 1, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2001, 4, 30, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("3mo", "1mo", mode="end").around(
            utc(1999, 12, 31), utc(2001, 3, 31)
        )
    )
    assert result == [
        datetime(2000, 2, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 5, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 8, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 11, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 2, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2001, 5, 1, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("mon").around(utc(2000, 2, 10), utc(2000, 3, 5))
    )
    assert result == [
        datetime(2000, 2, 7, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 14, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 21, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 28, 0, 0, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("tue").around(utc(2000, 2, 10), utc(2000, 3, 5))
    )
    assert result == [
        datetime(2000, 2, 8, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 15, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 22, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 29, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("2tue").around(utc(2000, 2, 10), utc(2000, 3, 5))
    )
    assert result == [
        datetime(2000, 2, 8, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 22, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("2tue", mode="end_inclusive").around(
            utc(2000, 2, 10), utc(2000, 3, 5)
        )
    )
    assert result == [
        datetime(2000, 2, 21, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 3, 6, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("2tue", mode="end").around(
            utc(2000, 2, 10), utc(2000, 3, 5)
        )
    )
    assert result == [
        datetime(2000, 2, 22, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 3, 7, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("d").around(utc(2000, 2, 10, 12), utc(2000, 2, 12, 14))
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 11, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 12, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("10d").around(utc(2000, 2, 10), utc(2000, 3, 5))
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 20, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 3, 1, 0, 0, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("10d", "-d").around(utc(2000, 2, 10), utc(2000, 3, 5))
    )
    assert result == [
        datetime(2000, 2, 9, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 19, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 29, 0, 0, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("10d", "-d", mode="end_inclusive").around(
            utc(2000, 2, 10), utc(2000, 3, 5)
        )
    )
    assert result == [
        datetime(2000, 2, 18, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 28, 23, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 3, 9, 23, 59, 59, 999999, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("10d", "-d", mode="end").around(
            utc(2000, 2, 10), utc(2000, 3, 5)
        )
    )
    assert result == [
        datetime(2000, 2, 19, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 29, 0, 0, tzinfo=timezone.utc),
        datetime(2000, 3, 10, 0, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("h").around(
            utc(2000, 2, 10, 1, 12), utc(2000, 2, 10, 3, 13)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 1, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 2, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 3, 0, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("2h", "1h").around(
            utc(2000, 2, 10, 1, 12), utc(2000, 2, 10, 5, 13)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 1, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 3, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 5, 0, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("2h", "1h", mode="end_inclusive").around(
            utc(2000, 2, 10, 1, 12), utc(2000, 2, 10, 5, 13)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 2, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 4, 59, 59, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 6, 59, 59, 999999, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("2h", "1h", mode="end").around(
            utc(2000, 2, 10, 1, 12), utc(2000, 2, 10, 5, 13)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 3, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 5, 0, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 7, 0, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("1m", "10s").around(
            utc(2000, 2, 10, 0, 0), utc(2000, 2, 10, 0, 3)
        )
    )
    assert result == [
        datetime(2000, 2, 9, 23, 59, 10, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 10, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 1, 10, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 2, 10, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("1m", "10s", mode="end_inclusive").around(
            utc(2000, 2, 10, 0, 0), utc(2000, 2, 10, 0, 3)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, 9, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 1, 9, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 2, 9, 999999, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 3, 9, 999999, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("1m", "10s", mode="end").around(
            utc(2000, 2, 10, 0, 0), utc(2000, 2, 10, 0, 3)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, 10, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 1, 10, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 2, 10, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 3, 10, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("s").around(
            utc(2000, 2, 10, 0, 0, 1, 100), utc(2000, 2, 10, 0, 0, 2, 300)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, 1, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 2, tzinfo=timezone.utc),
    ]

    result = list(
        DateTimeGrid("500ms", "25us", mode="start").around(
            utc(2000, 2, 10, 0, 0, 0), utc(2000, 2, 10, 0, 0, 2)
        )
    )
    assert result == [
        datetime(2000, 2, 9, 23, 59, 59, 500025, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 0, 25, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 0, 500025, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 1, 25, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 1, 500025, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("500ms", "25us", mode="end_inclusive").around(
            utc(2000, 2, 10, 0, 0, 0), utc(2000, 2, 10, 0, 0, 2)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, 0, 24, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 0, 500024, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 1, 24, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 1, 500024, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 2, 24, tzinfo=timezone.utc),
    ]
    result = list(
        DateTimeGrid("500ms", "25us", mode="end").around(
            utc(2000, 2, 10, 0, 0, 0), utc(2000, 2, 10, 0, 0, 2)
        )
    )
    assert result == [
        datetime(2000, 2, 10, 0, 0, 0, 25, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 0, 500025, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 1, 25, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 1, 500025, tzinfo=timezone.utc),
        datetime(2000, 2, 10, 0, 0, 2, 25, tzinfo=timezone.utc),
    ]


def test_grid_exceptions():
    with pytest.raises(ValueError):
        DateGrid("sun", "1d")
    with pytest.raises(ValueError):
        DateTimeGrid("sun", "1s")
