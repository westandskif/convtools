import string
from datetime import date, datetime, timedelta, timezone
from time import time

import pytest

from convtools import conversion as c
from convtools._dt import DatetimeFormat, DatetimeParse, UnsupportedFormatCode


SUPPORTED_FMT_TOKENS = "%% %A %a %B %H %I %M %S %Y %b %d %f %m %p %u %w %y"

ALL_FMT_TOKENS = "%% %A %a %B %b %c %d %f %G %H %I %j %M %m %p %S %U %u %V %W %w %X %x %Y %y %Z %z"
# UNSUPPORTED = "%U %W %X %Z %c %j %x %z %G %V"


@pytest.fixture
def all_delimiters():
    return [" ", ", ", "\t"] + list(
        string.digits
        + string.ascii_letters
        + string.punctuation.replace("%", "")
    )


@pytest.fixture
def all_dates():
    return (
        [date(i, 12, 31) for i in range(1, 3000, 50)]
        + [date(i, 12, 31) for i in range(1900, 2100)]
        + [date(1999, 12, 31) + timedelta(days=i) for i in range(365 * 5)]
    )


@pytest.fixture
def all_datetimes():
    return (
        [datetime(i, 12, 31, 23, 59, 31, 987) for i in range(1, 3000, 50)]
        + [datetime(i, 12, 31, 23, 59, 31, 987) for i in range(1900, 2100)]
        + [
            datetime(1999, 12, 31, 23, 59, 31, 987) + timedelta(days=i)
            for i in range(365 * 5)
        ]
        + [datetime(1999, 12, 31, i, 59, 31, 987) for i in range(24)]
        + [
            datetime(1999, 12, 31, 23, 59, 31, i)
            for i in (1, 12, 123, 1234, 12345, 123456)
        ]
    )
