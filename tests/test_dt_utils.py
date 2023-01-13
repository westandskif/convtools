from datetime import date, datetime, timedelta, timezone
from time import time

import pytest

from convtools import conversion as c
from convtools.dt import to_step


def utc(*args, **kwargs):
    return datetime(*args, tzinfo=kwargs.pop("tzinfo", timezone.utc), **kwargs)


def test_date_steps():
    for s in ("", "1", "asd", "1mo-", "1mo1s", "1mo2mo", "-mon", None):
        with pytest.raises(ValueError):
            to_step(s)

    for s in ("1y", "1mo"):
        for negative in (True, False):
            with pytest.raises(TypeError):
                to_step(f"{'-' if negative else ''}{s}").to_us()
            with pytest.raises(TypeError):
                to_step(f"{'-' if negative else ''}{s}").to_days()

    for s in ("mon", "2tue", "3wed", "thu", "fri", "sat", "sun", "1d", "-1d"):
        with pytest.raises(TypeError):
            to_step(s).to_months()

    for s in ("1h", "1m", "1s", "1ms", "1us"):
        for negative in (True, False):
            with pytest.raises(TypeError):
                to_step(f"{'-' if negative else ''}{s}").to_days()
            with pytest.raises(TypeError):
                to_step(f"{'-' if negative else ''}{s}").to_months()

    for s, months in [
        ("y", 12),
        ("1y", 12),
        ("2y", 24),
        ("101y", 101 * 12),
        ("mo", 1),
        ("1mo", 1),
        ("2mo", 2),
        ("101mo", 101),
        ("1y1mo", 13),
    ]:
        for negative in (True, False):
            assert to_step(
                f"{'-' if negative else ''}{s}"
            ).to_months() == months * (-1 if negative else 1)

    for s, days, day_of_week_offset in [
        ("sun", 7, 0),
        ("1mon", 1 * 7, 1),
        ("2tue", 2 * 7, 2),
        ("3wed", 3 * 7, 3),
        ("4thu", 4 * 7, 4),
        ("5fri", 5 * 7, 5),
        ("6sat", 6 * 7, 6),
    ]:
        step = to_step(s)
        assert (
            step.to_days() == days
            and step.day_of_week_offset == day_of_week_offset
        )

    for s, days in [
        ("d", 1),
        ("1d", 1),
        ("2d", 2),
        ("101d", 101),
        ("24h", 1),
        ("240h", 10),
        ("1440m", 1),
        ("14400m", 10),
        ("86400s", 1),
        ("864000s", 10),
        ("86400000ms", 1),
        ("864000000ms", 10),
        ("86400000000us", 1),
        ("864000000000us", 10),
    ]:
        for negative in (True, False):
            assert to_step(
                f"{'-' if negative else ''}{s}"
            ).to_days() == days * (-1 if negative else 1)

    for s, seconds in [
        ("1d", 86400),
        ("2d", 86400 * 2),
        ("101d", 86400 * 101),
        ("24h", 86400),
        ("240h", 86400 * 10),
        ("1440m", 86400),
        ("14400m", 86400 * 10),
        ("s", 1),
        ("86400s", 86400),
        ("864000s", 86400 * 10),
        ("86400000ms", 86400),
        ("864000000ms", 86400 * 10),
        ("86400000000us", 86400),
        ("864000000000us", 86400 * 10),
        (
            "11d12h13m14s15ms16us",
            11 * 86400 + 12 * 3600 + 13 * 60 + 14 + 15 * 0.001 + 16 * 1e-6,
        ),
    ]:
        for negative in (True, False):
            assert (
                to_step(f"{'-' if negative else ''}{s}").to_us()
                == seconds * (-1 if negative else 1) * 1000000
            )

    for delta, us in [
        (timedelta(days=2), 2 * 86400 * 1000000),
        (timedelta(microseconds=2), 2),
    ]:
        for negative in (True, False):
            sign = -1 if negative else 1
            assert to_step(delta * sign).to_us() == us * sign


def test_date_trunc():
    with pytest.raises(TypeError):
        c.date_trunc("1h")
    with pytest.raises(ValueError):
        c.date_trunc("1d", mode="abc")
    with pytest.raises(ValueError):
        c.date_trunc("1mon", "1d")
    with pytest.raises(ValueError):
        c.datetime_trunc("1mon", "1d")

    results = (
        c.iter(
            {
                "start": c.this.date_trunc("y", mode="start"),
                "end": c.date_trunc("y", mode="end"),
                "end_inclusive": c.date_trunc("y", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(
            [
                date(2000, 2, 2),
                date(2001, 3, 4),
            ]
        )
    )
    assert results == [
        {
            "end": date(2001, 1, 1),
            "end_inclusive": date(2000, 12, 31),
            "start": date(2000, 1, 1),
        },
        {
            "end": date(2002, 1, 1),
            "end_inclusive": date(2001, 12, 31),
            "start": date(2001, 1, 1),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.date_trunc("mo", mode="start"),
                "end": c.date_trunc("mo", mode="end"),
                "end_inclusive": c.date_trunc("mo", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(
            [
                date(2000, 2, 2),
                date(2001, 2, 4),
            ]
        )
    )
    assert results == [
        {
            "end": date(2000, 3, 1),
            "end_inclusive": date(2000, 2, 29),
            "start": date(2000, 2, 1),
        },
        {
            "end": date(2001, 3, 1),
            "end_inclusive": date(2001, 2, 28),
            "start": date(2001, 2, 1),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.date_trunc("4y", "1y", "start"),
                "end": c.date_trunc("4y", "1y", "end"),
                "end_inclusive": c.date_trunc("4y", "1y", "end_inclusive"),
            }
        )
        .as_type(list)
        .execute(
            [
                date(2000, 12, 31),
                date(2001, 2, 3),
                date(2006, 3, 4),
            ]
        )
    )
    assert results == [
        {
            "start": date(1997, 1, 1),
            "end": date(2001, 1, 1),
            "end_inclusive": date(2000, 12, 31),
        },
        {
            "start": date(2001, 1, 1),
            "end": date(2005, 1, 1),
            "end_inclusive": date(2004, 12, 31),
        },
        {
            "start": date(2005, 1, 1),
            "end": date(2009, 1, 1),
            "end_inclusive": date(2008, 12, 31),
        },
    ]

    dates = [
        date(2000, 1, 1),
        date(2000, 1, 2),
        date(2001, 1, 3),
        date(2001, 1, 4),
        date(2001, 1, 5),
        date(2001, 1, 6),
        date(2001, 1, 7),
        date(2001, 1, 8),
    ]
    results = (
        c.iter(
            {
                "start": c.date_trunc("sun", mode="start"),
                "end": c.date_trunc("sun", mode="end"),
                "end_inclusive": c.date_trunc("sun", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": date(2000, 1, 2),
            "end_inclusive": date(2000, 1, 1),
            "start": date(1999, 12, 26),
        },
        {
            "end": date(2000, 1, 9),
            "end_inclusive": date(2000, 1, 8),
            "start": date(2000, 1, 2),
        },
        {
            "end": date(2001, 1, 7),
            "end_inclusive": date(2001, 1, 6),
            "start": date(2000, 12, 31),
        },
        {
            "end": date(2001, 1, 7),
            "end_inclusive": date(2001, 1, 6),
            "start": date(2000, 12, 31),
        },
        {
            "end": date(2001, 1, 7),
            "end_inclusive": date(2001, 1, 6),
            "start": date(2000, 12, 31),
        },
        {
            "end": date(2001, 1, 7),
            "end_inclusive": date(2001, 1, 6),
            "start": date(2000, 12, 31),
        },
        {
            "end": date(2001, 1, 14),
            "end_inclusive": date(2001, 1, 13),
            "start": date(2001, 1, 7),
        },
        {
            "end": date(2001, 1, 14),
            "end_inclusive": date(2001, 1, 13),
            "start": date(2001, 1, 7),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.date_trunc("mon", mode="start"),
                "end": c.date_trunc("mon", mode="end"),
                "end_inclusive": c.date_trunc("mon", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": date(2000, 1, 3),
            "end_inclusive": date(2000, 1, 2),
            "start": date(1999, 12, 27),
        },
        {
            "end": date(2000, 1, 3),
            "end_inclusive": date(2000, 1, 2),
            "start": date(1999, 12, 27),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2001, 1, 1),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2001, 1, 1),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2001, 1, 1),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2001, 1, 1),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2001, 1, 1),
        },
        {
            "end": date(2001, 1, 15),
            "end_inclusive": date(2001, 1, 14),
            "start": date(2001, 1, 8),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.date_trunc("sat", mode="start"),
                "end": c.date_trunc("sat", mode="end"),
                "end_inclusive": c.date_trunc("sat", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": date(2000, 1, 8),
            "end_inclusive": date(2000, 1, 7),
            "start": date(2000, 1, 1),
        },
        {
            "end": date(2000, 1, 8),
            "end_inclusive": date(2000, 1, 7),
            "start": date(2000, 1, 1),
        },
        {
            "end": date(2001, 1, 6),
            "end_inclusive": date(2001, 1, 5),
            "start": date(2000, 12, 30),
        },
        {
            "end": date(2001, 1, 6),
            "end_inclusive": date(2001, 1, 5),
            "start": date(2000, 12, 30),
        },
        {
            "end": date(2001, 1, 6),
            "end_inclusive": date(2001, 1, 5),
            "start": date(2000, 12, 30),
        },
        {
            "end": date(2001, 1, 13),
            "end_inclusive": date(2001, 1, 12),
            "start": date(2001, 1, 6),
        },
        {
            "end": date(2001, 1, 13),
            "end_inclusive": date(2001, 1, 12),
            "start": date(2001, 1, 6),
        },
        {
            "end": date(2001, 1, 13),
            "end_inclusive": date(2001, 1, 12),
            "start": date(2001, 1, 6),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.date_trunc("2mon", mode="start"),
                "end": c.date_trunc("2mon", mode="end"),
                "end_inclusive": c.date_trunc("2mon", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": date(2000, 1, 10),
            "end_inclusive": date(2000, 1, 9),
            "start": date(1999, 12, 27),
        },
        {
            "end": date(2000, 1, 10),
            "end_inclusive": date(2000, 1, 9),
            "start": date(1999, 12, 27),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2000, 12, 25),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2000, 12, 25),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2000, 12, 25),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2000, 12, 25),
        },
        {
            "end": date(2001, 1, 8),
            "end_inclusive": date(2001, 1, 7),
            "start": date(2000, 12, 25),
        },
        {
            "end": date(2001, 1, 22),
            "end_inclusive": date(2001, 1, 21),
            "start": date(2001, 1, 8),
        },
    ]

    dates = [
        date(2000, 2, 27),
        date(2000, 2, 28),
        date(2000, 2, 29),
        date(2000, 3, 1),
        date(2000, 3, 2),
        date(2001, 2, 27),
        date(2001, 2, 28),
        date(2001, 3, 1),
        date(2001, 3, 2),
    ]
    results = (
        c.iter(
            {
                "start": c.date_trunc("3d", mode="start"),
                "end": c.date_trunc("3d", mode="end"),
                "end_inclusive": c.date_trunc("3d", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": date(2000, 2, 29),
            "end_inclusive": date(2000, 2, 28),
            "start": date(2000, 2, 26),
        },
        {
            "end": date(2000, 2, 29),
            "end_inclusive": date(2000, 2, 28),
            "start": date(2000, 2, 26),
        },
        {
            "end": date(2000, 3, 3),
            "end_inclusive": date(2000, 3, 2),
            "start": date(2000, 2, 29),
        },
        {
            "end": date(2000, 3, 3),
            "end_inclusive": date(2000, 3, 2),
            "start": date(2000, 2, 29),
        },
        {
            "end": date(2000, 3, 3),
            "end_inclusive": date(2000, 3, 2),
            "start": date(2000, 2, 29),
        },
        {
            "end": date(2001, 3, 1),
            "end_inclusive": date(2001, 2, 28),
            "start": date(2001, 2, 26),
        },
        {
            "end": date(2001, 3, 1),
            "end_inclusive": date(2001, 2, 28),
            "start": date(2001, 2, 26),
        },
        {
            "end": date(2001, 3, 4),
            "end_inclusive": date(2001, 3, 3),
            "start": date(2001, 3, 1),
        },
        {
            "end": date(2001, 3, 4),
            "end_inclusive": date(2001, 3, 3),
            "start": date(2001, 3, 1),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.date_trunc("3d", "2d", mode="start"),
                "end": c.date_trunc("3d", "2d", mode="end"),
                "end_inclusive": c.date_trunc(
                    "3d", "2d", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": date(2000, 2, 28),
            "end_inclusive": date(2000, 2, 27),
            "start": date(2000, 2, 25),
        },
        {
            "end": date(2000, 3, 2),
            "end_inclusive": date(2000, 3, 1),
            "start": date(2000, 2, 28),
        },
        {
            "end": date(2000, 3, 2),
            "end_inclusive": date(2000, 3, 1),
            "start": date(2000, 2, 28),
        },
        {
            "end": date(2000, 3, 2),
            "end_inclusive": date(2000, 3, 1),
            "start": date(2000, 2, 28),
        },
        {
            "end": date(2000, 3, 5),
            "end_inclusive": date(2000, 3, 4),
            "start": date(2000, 3, 2),
        },
        {
            "end": date(2001, 2, 28),
            "end_inclusive": date(2001, 2, 27),
            "start": date(2001, 2, 25),
        },
        {
            "end": date(2001, 3, 3),
            "end_inclusive": date(2001, 3, 2),
            "start": date(2001, 2, 28),
        },
        {
            "end": date(2001, 3, 3),
            "end_inclusive": date(2001, 3, 2),
            "start": date(2001, 2, 28),
        },
        {
            "end": date(2001, 3, 3),
            "end_inclusive": date(2001, 3, 2),
            "start": date(2001, 2, 28),
        },
    ]


def test_datetime_trunc():
    results = (
        c.iter(
            {
                "start": c.this.datetime_trunc("y", mode="start"),
                "end": c.datetime_trunc("y", mode="end"),
                "end_inclusive": c.datetime_trunc("y", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(
            [
                utc(2000, 2, 2),
                datetime(2001, 3, 4),
            ]
        )
    )
    assert results == [
        {
            "end": utc(2001, 1, 1),
            "end_inclusive": utc(2000, 12, 31, 23, 59, 59, 999999),
            "start": utc(2000, 1, 1),
        },
        {
            "end": datetime(2002, 1, 1),
            "end_inclusive": datetime(2001, 12, 31, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 1),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.datetime_trunc("mo", mode="start"),
                "end": c.datetime_trunc("mo", mode="end"),
                "end_inclusive": c.datetime_trunc("mo", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(
            [
                utc(2000, 2, 2),
                datetime(2001, 2, 4),
            ]
        )
    )
    assert results == [
        {
            "end": utc(2000, 3, 1),
            "end_inclusive": utc(2000, 2, 29, 23, 59, 59, 999999),
            "start": utc(2000, 2, 1),
        },
        {
            "end": datetime(2001, 3, 1),
            "end_inclusive": datetime(2001, 2, 28, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 1),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.datetime_trunc("4y", "1y", "start"),
                "end": c.datetime_trunc("4y", "1y", "end"),
                "end_inclusive": c.datetime_trunc("4y", "1y", "end_inclusive"),
            }
        )
        .as_type(list)
        .execute(
            [
                utc(2000, 12, 31),
                datetime(2001, 2, 3, 2),
                datetime(2006, 3, 4, 2),
            ]
        )
    )
    assert results == [
        {
            "start": utc(1997, 1, 1),
            "end": utc(2001, 1, 1),
            "end_inclusive": utc(2000, 12, 31, 23, 59, 59, 999999),
        },
        {
            "start": datetime(2001, 1, 1),
            "end": datetime(2005, 1, 1),
            "end_inclusive": datetime(2004, 12, 31, 23, 59, 59, 999999),
        },
        {
            "start": datetime(2005, 1, 1),
            "end": datetime(2009, 1, 1),
            "end_inclusive": datetime(2008, 12, 31, 23, 59, 59, 999999),
        },
    ]
    dates = [
        utc(2000, 1, 1, 15),
        datetime(2000, 1, 2, 11),
        datetime(2001, 1, 3, 12),
        datetime(2001, 1, 4, 13),
        datetime(2001, 1, 5, 14),
        datetime(2001, 1, 6, 15),
        datetime(2001, 1, 7, 16),
        datetime(2001, 1, 8, 17),
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("sun", mode="start"),
                "end": c.datetime_trunc("sun", mode="end"),
                "end_inclusive": c.datetime_trunc("sun", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 2),
            "end_inclusive": utc(2000, 1, 1, 23, 59, 59, 999999),
            "start": utc(1999, 12, 26),
        },
        {
            "end": datetime(2000, 1, 9),
            "end_inclusive": datetime(2000, 1, 8, 23, 59, 59, 999999),
            "start": datetime(2000, 1, 2),
        },
        {
            "end": datetime(2001, 1, 7),
            "end_inclusive": datetime(2001, 1, 6, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 31),
        },
        {
            "end": datetime(2001, 1, 7),
            "end_inclusive": datetime(2001, 1, 6, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 31),
        },
        {
            "end": datetime(2001, 1, 7),
            "end_inclusive": datetime(2001, 1, 6, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 31),
        },
        {
            "end": datetime(2001, 1, 7),
            "end_inclusive": datetime(2001, 1, 6, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 31),
        },
        {
            "end": datetime(2001, 1, 14),
            "end_inclusive": datetime(2001, 1, 13, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 7),
        },
        {
            "end": datetime(2001, 1, 14),
            "end_inclusive": datetime(2001, 1, 13, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 7),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("mon", mode="start"),
                "end": c.datetime_trunc("mon", mode="end"),
                "end_inclusive": c.datetime_trunc("mon", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 3),
            "end_inclusive": utc(2000, 1, 2, 23, 59, 59, 999999),
            "start": utc(1999, 12, 27),
        },
        {
            "end": datetime(2000, 1, 3),
            "end_inclusive": datetime(2000, 1, 2, 23, 59, 59, 999999),
            "start": datetime(1999, 12, 27),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 1),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 1),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 1),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 1),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 1),
        },
        {
            "end": datetime(2001, 1, 15),
            "end_inclusive": datetime(2001, 1, 14, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 8),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.datetime_trunc("sat", mode="start"),
                "end": c.datetime_trunc("sat", mode="end"),
                "end_inclusive": c.datetime_trunc("sat", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 8),
            "end_inclusive": utc(2000, 1, 7, 23, 59, 59, 999999),
            "start": utc(2000, 1, 1),
        },
        {
            "end": datetime(2000, 1, 8),
            "end_inclusive": datetime(2000, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2000, 1, 1),
        },
        {
            "end": datetime(2001, 1, 6),
            "end_inclusive": datetime(2001, 1, 5, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 30),
        },
        {
            "end": datetime(2001, 1, 6),
            "end_inclusive": datetime(2001, 1, 5, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 30),
        },
        {
            "end": datetime(2001, 1, 6),
            "end_inclusive": datetime(2001, 1, 5, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 30),
        },
        {
            "end": datetime(2001, 1, 13),
            "end_inclusive": datetime(2001, 1, 12, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 6),
        },
        {
            "end": datetime(2001, 1, 13),
            "end_inclusive": datetime(2001, 1, 12, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 6),
        },
        {
            "end": datetime(2001, 1, 13),
            "end_inclusive": datetime(2001, 1, 12, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 6),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("2mon", mode="start"),
                "end": c.datetime_trunc("2mon", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "2mon", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 10),
            "end_inclusive": utc(2000, 1, 9, 23, 59, 59, 999999),
            "start": utc(1999, 12, 27),
        },
        {
            "end": datetime(2000, 1, 10),
            "end_inclusive": datetime(2000, 1, 9, 23, 59, 59, 999999),
            "start": datetime(1999, 12, 27),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 25),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 25),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 25),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 25),
        },
        {
            "end": datetime(2001, 1, 8),
            "end_inclusive": datetime(2001, 1, 7, 23, 59, 59, 999999),
            "start": datetime(2000, 12, 25),
        },
        {
            "end": datetime(2001, 1, 22),
            "end_inclusive": datetime(2001, 1, 21, 23, 59, 59, 999999),
            "start": datetime(2001, 1, 8),
        },
    ]

    dates = [
        utc(2000, 2, 27, 15, 1),
        datetime(2000, 2, 28, 1, 10, 15, 250001),
        datetime(2000, 2, 29, 23, 30),
        datetime(2000, 3, 1, 1, 31),
        datetime(2000, 3, 2, 2, 32),
        datetime(2001, 2, 27, 3, 34),
        datetime(2001, 2, 28, 4, 40),
        datetime(2001, 3, 1, 5, 45),
        datetime(2001, 3, 2, 6, 50),
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("3d", mode="start"),
                "end": c.datetime_trunc("3d", mode="end"),
                "end_inclusive": c.datetime_trunc("3d", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 29),
            "end_inclusive": utc(2000, 2, 28, 23, 59, 59, 999999),
            "start": utc(2000, 2, 26),
        },
        {
            "end": datetime(2000, 2, 29),
            "end_inclusive": datetime(2000, 2, 28, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 26),
        },
        {
            "end": datetime(2000, 3, 3),
            "end_inclusive": datetime(2000, 3, 2, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 29),
        },
        {
            "end": datetime(2000, 3, 3),
            "end_inclusive": datetime(2000, 3, 2, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 29),
        },
        {
            "end": datetime(2000, 3, 3),
            "end_inclusive": datetime(2000, 3, 2, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 29),
        },
        {
            "end": datetime(2001, 3, 1),
            "end_inclusive": datetime(2001, 2, 28, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 26),
        },
        {
            "end": datetime(2001, 3, 1),
            "end_inclusive": datetime(2001, 2, 28, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 26),
        },
        {
            "end": datetime(2001, 3, 4),
            "end_inclusive": datetime(2001, 3, 3, 23, 59, 59, 999999),
            "start": datetime(2001, 3, 1),
        },
        {
            "end": datetime(2001, 3, 4),
            "end_inclusive": datetime(2001, 3, 3, 23, 59, 59, 999999),
            "start": datetime(2001, 3, 1),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("3d", "2d", mode="start"),
                "end": c.datetime_trunc("3d", "2d", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "3d", "2d", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 28),
            "end_inclusive": utc(2000, 2, 27, 23, 59, 59, 999999),
            "start": utc(2000, 2, 25),
        },
        {
            "end": datetime(2000, 3, 2),
            "end_inclusive": datetime(2000, 3, 1, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 28),
        },
        {
            "end": datetime(2000, 3, 2),
            "end_inclusive": datetime(2000, 3, 1, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 28),
        },
        {
            "end": datetime(2000, 3, 2),
            "end_inclusive": datetime(2000, 3, 1, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 28),
        },
        {
            "end": datetime(2000, 3, 5),
            "end_inclusive": datetime(2000, 3, 4, 23, 59, 59, 999999),
            "start": datetime(2000, 3, 2),
        },
        {
            "end": datetime(2001, 2, 28),
            "end_inclusive": datetime(2001, 2, 27, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 25),
        },
        {
            "end": datetime(2001, 3, 3),
            "end_inclusive": datetime(2001, 3, 2, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 28),
        },
        {
            "end": datetime(2001, 3, 3),
            "end_inclusive": datetime(2001, 3, 2, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 28),
        },
        {
            "end": datetime(2001, 3, 3),
            "end_inclusive": datetime(2001, 3, 2, 23, 59, 59, 999999),
            "start": datetime(2001, 2, 28),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.datetime_trunc("1h", mode="start"),
                "end": c.datetime_trunc("1h", mode="end"),
                "end_inclusive": c.datetime_trunc("1h", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 27, 16, 0),
            "end_inclusive": utc(2000, 2, 27, 15, 59, 59, 999999),
            "start": utc(2000, 2, 27, 15, 0),
        },
        {
            "end": datetime(2000, 2, 28, 2, 0),
            "end_inclusive": datetime(2000, 2, 28, 1, 59, 59, 999999),
            "start": datetime(2000, 2, 28, 1, 0),
        },
        {
            "end": datetime(2000, 3, 1, 0, 0),
            "end_inclusive": datetime(2000, 2, 29, 23, 59, 59, 999999),
            "start": datetime(2000, 2, 29, 23, 0),
        },
        {
            "end": datetime(2000, 3, 1, 2, 0),
            "end_inclusive": datetime(2000, 3, 1, 1, 59, 59, 999999),
            "start": datetime(2000, 3, 1, 1, 0),
        },
        {
            "end": datetime(2000, 3, 2, 3, 0),
            "end_inclusive": datetime(2000, 3, 2, 2, 59, 59, 999999),
            "start": datetime(2000, 3, 2, 2, 0),
        },
        {
            "end": datetime(2001, 2, 27, 4, 0),
            "end_inclusive": datetime(2001, 2, 27, 3, 59, 59, 999999),
            "start": datetime(2001, 2, 27, 3, 0),
        },
        {
            "end": datetime(2001, 2, 28, 5, 0),
            "end_inclusive": datetime(2001, 2, 28, 4, 59, 59, 999999),
            "start": datetime(2001, 2, 28, 4, 0),
        },
        {
            "end": datetime(2001, 3, 1, 6, 0),
            "end_inclusive": datetime(2001, 3, 1, 5, 59, 59, 999999),
            "start": datetime(2001, 3, 1, 5, 0),
        },
        {
            "end": datetime(2001, 3, 2, 7, 0),
            "end_inclusive": datetime(2001, 3, 2, 6, 59, 59, 999999),
            "start": datetime(2001, 3, 2, 6, 0),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("8h", "20s", mode="start"),
                "end": c.datetime_trunc("8h", "20s", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "8h", "20s", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 27, 16, 0, 20),
            "end_inclusive": utc(2000, 2, 27, 16, 0, 19, 999999),
            "start": utc(2000, 2, 27, 8, 0, 20),
        },
        {
            "end": datetime(2000, 2, 28, 8, 0, 20),
            "end_inclusive": datetime(2000, 2, 28, 8, 0, 19, 999999),
            "start": datetime(2000, 2, 28, 0, 0, 20),
        },
        {
            "end": datetime(2000, 3, 1, 0, 0, 20),
            "end_inclusive": datetime(2000, 3, 1, 0, 0, 19, 999999),
            "start": datetime(2000, 2, 29, 16, 0, 20),
        },
        {
            "end": datetime(2000, 3, 1, 8, 0, 20),
            "end_inclusive": datetime(2000, 3, 1, 8, 0, 19, 999999),
            "start": datetime(2000, 3, 1, 0, 0, 20),
        },
        {
            "end": datetime(2000, 3, 2, 8, 0, 20),
            "end_inclusive": datetime(2000, 3, 2, 8, 0, 19, 999999),
            "start": datetime(2000, 3, 2, 0, 0, 20),
        },
        {
            "end": datetime(2001, 2, 27, 8, 0, 20),
            "end_inclusive": datetime(2001, 2, 27, 8, 0, 19, 999999),
            "start": datetime(2001, 2, 27, 0, 0, 20),
        },
        {
            "end": datetime(2001, 2, 28, 8, 0, 20),
            "end_inclusive": datetime(2001, 2, 28, 8, 0, 19, 999999),
            "start": datetime(2001, 2, 28, 0, 0, 20),
        },
        {
            "end": datetime(2001, 3, 1, 8, 0, 20),
            "end_inclusive": datetime(2001, 3, 1, 8, 0, 19, 999999),
            "start": datetime(2001, 3, 1, 0, 0, 20),
        },
        {
            "end": datetime(2001, 3, 2, 8, 0, 20),
            "end_inclusive": datetime(2001, 3, 2, 8, 0, 19, 999999),
            "start": datetime(2001, 3, 2, 0, 0, 20),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.datetime_trunc("2m", mode="start"),
                "end": c.datetime_trunc("2m", mode="end"),
                "end_inclusive": c.datetime_trunc("2m", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 27, 15, 2),
            "end_inclusive": utc(2000, 2, 27, 15, 1, 59, 999999),
            "start": utc(2000, 2, 27, 15, 0),
        },
        {
            "end": datetime(2000, 2, 28, 1, 12),
            "end_inclusive": datetime(2000, 2, 28, 1, 11, 59, 999999),
            "start": datetime(2000, 2, 28, 1, 10),
        },
        {
            "end": datetime(2000, 2, 29, 23, 32),
            "end_inclusive": datetime(2000, 2, 29, 23, 31, 59, 999999),
            "start": datetime(2000, 2, 29, 23, 30),
        },
        {
            "end": datetime(2000, 3, 1, 1, 32),
            "end_inclusive": datetime(2000, 3, 1, 1, 31, 59, 999999),
            "start": datetime(2000, 3, 1, 1, 30),
        },
        {
            "end": datetime(2000, 3, 2, 2, 34),
            "end_inclusive": datetime(2000, 3, 2, 2, 33, 59, 999999),
            "start": datetime(2000, 3, 2, 2, 32),
        },
        {
            "end": datetime(2001, 2, 27, 3, 36),
            "end_inclusive": datetime(2001, 2, 27, 3, 35, 59, 999999),
            "start": datetime(2001, 2, 27, 3, 34),
        },
        {
            "end": datetime(2001, 2, 28, 4, 42),
            "end_inclusive": datetime(2001, 2, 28, 4, 41, 59, 999999),
            "start": datetime(2001, 2, 28, 4, 40),
        },
        {
            "end": datetime(2001, 3, 1, 5, 46),
            "end_inclusive": datetime(2001, 3, 1, 5, 45, 59, 999999),
            "start": datetime(2001, 3, 1, 5, 44),
        },
        {
            "end": datetime(2001, 3, 2, 6, 52),
            "end_inclusive": datetime(2001, 3, 2, 6, 51, 59, 999999),
            "start": datetime(2001, 3, 2, 6, 50),
        },
    ]

    results = (
        c.iter(
            {
                "start": c.datetime_trunc("5m", "250ms", mode="start"),
                "end": c.datetime_trunc("5m", "250ms", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "5m", "250ms", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )

    assert results == [
        {
            "end": utc(2000, 2, 27, 15, 5, 0, 250000),
            "end_inclusive": utc(2000, 2, 27, 15, 5, 0, 249999),
            "start": utc(2000, 2, 27, 15, 0, 0, 250000),
        },
        {
            "end": datetime(2000, 2, 28, 1, 15, 0, 250000),
            "end_inclusive": datetime(2000, 2, 28, 1, 15, 0, 249999),
            "start": datetime(2000, 2, 28, 1, 10, 0, 250000),
        },
        {
            "end": datetime(2000, 2, 29, 23, 30, 0, 250000),
            "end_inclusive": datetime(2000, 2, 29, 23, 30, 0, 249999),
            "start": datetime(2000, 2, 29, 23, 25, 0, 250000),
        },
        {
            "end": datetime(2000, 3, 1, 1, 35, 0, 250000),
            "end_inclusive": datetime(2000, 3, 1, 1, 35, 0, 249999),
            "start": datetime(2000, 3, 1, 1, 30, 0, 250000),
        },
        {
            "end": datetime(2000, 3, 2, 2, 35, 0, 250000),
            "end_inclusive": datetime(2000, 3, 2, 2, 35, 0, 249999),
            "start": datetime(2000, 3, 2, 2, 30, 0, 250000),
        },
        {
            "end": datetime(2001, 2, 27, 3, 35, 0, 250000),
            "end_inclusive": datetime(2001, 2, 27, 3, 35, 0, 249999),
            "start": datetime(2001, 2, 27, 3, 30, 0, 250000),
        },
        {
            "end": datetime(2001, 2, 28, 4, 40, 0, 250000),
            "end_inclusive": datetime(2001, 2, 28, 4, 40, 0, 249999),
            "start": datetime(2001, 2, 28, 4, 35, 0, 250000),
        },
        {
            "end": datetime(2001, 3, 1, 5, 45, 0, 250000),
            "end_inclusive": datetime(2001, 3, 1, 5, 45, 0, 249999),
            "start": datetime(2001, 3, 1, 5, 40, 0, 250000),
        },
        {
            "end": datetime(2001, 3, 2, 6, 50, 0, 250000),
            "end_inclusive": datetime(2001, 3, 2, 6, 50, 0, 249999),
            "start": datetime(2001, 3, 2, 6, 45, 0, 250000),
        },
    ]
    dates = [
        utc(2000, 2, 27, 15, 0, 1),
        datetime(2000, 2, 27, 15, 0, 2, 250001),
        datetime(2000, 2, 29, 16, 0, 3),
        datetime(2000, 2, 29, 16, 0, 4, 500000),
        datetime(2000, 2, 29, 20, 0, 5),
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("4s", mode="start"),
                "end": c.datetime_trunc("4s", mode="end"),
                "end_inclusive": c.datetime_trunc("4s", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 27, 15, 0, 4),
            "end_inclusive": utc(2000, 2, 27, 15, 0, 3, 999999),
            "start": utc(2000, 2, 27, 15, 0),
        },
        {
            "end": datetime(2000, 2, 27, 15, 0, 4),
            "end_inclusive": datetime(2000, 2, 27, 15, 0, 3, 999999),
            "start": datetime(2000, 2, 27, 15, 0),
        },
        {
            "end": datetime(2000, 2, 29, 16, 0, 4),
            "end_inclusive": datetime(2000, 2, 29, 16, 0, 3, 999999),
            "start": datetime(2000, 2, 29, 16, 0),
        },
        {
            "end": datetime(2000, 2, 29, 16, 0, 8),
            "end_inclusive": datetime(2000, 2, 29, 16, 0, 7, 999999),
            "start": datetime(2000, 2, 29, 16, 0, 4),
        },
        {
            "end": datetime(2000, 2, 29, 20, 0, 8),
            "end_inclusive": datetime(2000, 2, 29, 20, 0, 7, 999999),
            "start": datetime(2000, 2, 29, 20, 0, 4),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("3s", "-1us", mode="start"),
                "end": c.datetime_trunc("3s", "-1us", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "3s", "-1us", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 2, 27, 15, 0, 2, 999999),
            "end_inclusive": utc(2000, 2, 27, 15, 0, 2, 999998),
            "start": utc(2000, 2, 27, 14, 59, 59, 999999),
        },
        {
            "end": datetime(2000, 2, 27, 15, 0, 2, 999999),
            "end_inclusive": datetime(2000, 2, 27, 15, 0, 2, 999998),
            "start": datetime(2000, 2, 27, 14, 59, 59, 999999),
        },
        {
            "end": datetime(2000, 2, 29, 16, 0, 5, 999999),
            "end_inclusive": datetime(2000, 2, 29, 16, 0, 5, 999998),
            "start": datetime(2000, 2, 29, 16, 0, 2, 999999),
        },
        {
            "end": datetime(2000, 2, 29, 16, 0, 5, 999999),
            "end_inclusive": datetime(2000, 2, 29, 16, 0, 5, 999998),
            "start": datetime(2000, 2, 29, 16, 0, 2, 999999),
        },
        {
            "end": datetime(2000, 2, 29, 20, 0, 5, 999999),
            "end_inclusive": datetime(2000, 2, 29, 20, 0, 5, 999998),
            "start": datetime(2000, 2, 29, 20, 0, 2, 999999),
        },
    ]

    dates = [
        utc(2000, 1, 1, 0, 0, 0, 0),
        datetime(2000, 1, 1, 0, 0, 0, 1000),
        datetime(2000, 1, 1, 0, 0, 0, 4000),
        datetime(2000, 1, 1, 0, 0, 0, 7000),
        datetime(2000, 1, 1, 0, 0, 0, 10000),
        datetime(2000, 1, 1, 0, 0, 0, 15000),
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("6ms", mode="start"),
                "end": c.datetime_trunc("6ms", mode="end"),
                "end_inclusive": c.datetime_trunc("6ms", mode="end_inclusive"),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 1, 0, 0, 0, 6000),
            "end_inclusive": utc(2000, 1, 1, 0, 0, 0, 5999),
            "start": utc(2000, 1, 1, 0, 0),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 6000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 5999),
            "start": datetime(2000, 1, 1, 0, 0),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 6000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 5999),
            "start": datetime(2000, 1, 1, 0, 0),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 12000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 11999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 6000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 12000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 11999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 6000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 18000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 17999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 12000),
        },
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("2ms", "1ms", mode="start"),
                "end": c.datetime_trunc("2ms", "1ms", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "2ms", "1ms", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 1, 0, 0, 0, 1000),
            "end_inclusive": utc(2000, 1, 1, 0, 0, 0, 999),
            "start": utc(1999, 12, 31, 23, 59, 59, 999000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 3000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 2999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 1000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 5000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 4999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 3000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 9000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 8999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 7000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 11000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 10999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 9000),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 17000),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 16999),
            "start": datetime(2000, 1, 1, 0, 0, 0, 15000),
        },
    ]

    dates = [
        utc(2000, 1, 1, 0, 0, 0, 0),
        datetime(2000, 1, 1, 0, 0, 0, 5),
        datetime(2000, 1, 1, 0, 0, 0, 10),
        datetime(2000, 1, 1, 0, 0, 0, 15),
        datetime(2000, 1, 1, 0, 0, 0, 20),
        datetime(2000, 1, 1, 0, 0, 0, 25),
    ]
    results = (
        c.iter(
            {
                "start": c.datetime_trunc("4us", "-3us", mode="start"),
                "end": c.datetime_trunc("4us", "-3us", mode="end"),
                "end_inclusive": c.datetime_trunc(
                    "4us", "-3us", mode="end_inclusive"
                ),
            }
        )
        .as_type(list)
        .execute(dates)
    )
    assert results == [
        {
            "end": utc(2000, 1, 1, 0, 0, 0, 1),
            "end_inclusive": utc(2000, 1, 1, 0, 0),
            "start": utc(1999, 12, 31, 23, 59, 59, 999997),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 9),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 8),
            "start": datetime(2000, 1, 1, 0, 0, 0, 5),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 13),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 12),
            "start": datetime(2000, 1, 1, 0, 0, 0, 9),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 17),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 16),
            "start": datetime(2000, 1, 1, 0, 0, 0, 13),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 21),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 20),
            "start": datetime(2000, 1, 1, 0, 0, 0, 17),
        },
        {
            "end": datetime(2000, 1, 1, 0, 0, 0, 29),
            "end_inclusive": datetime(2000, 1, 1, 0, 0, 0, 28),
            "start": datetime(2000, 1, 1, 0, 0, 0, 25),
        },
    ]
