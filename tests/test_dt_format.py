from datetime import date, datetime

import pytest

from convtools import conversion as c
from convtools._dt import DatetimeFormat

from .test_dt_utils import (
    ALL_FMT_TOKENS,
    SUPPORTED_FMT_TOKENS,
    all_dates,
    all_datetimes,
    all_delimiters,
)


def test_datetime_format__ensure_supported():
    c_fmt = DatetimeFormat(SUPPORTED_FMT_TOKENS)
    assert c_fmt._to_code("data_", c_fmt._init_ctx()) is not None

    c_fmt = DatetimeFormat(ALL_FMT_TOKENS)
    assert c_fmt._to_code("data_", c_fmt._init_ctx()) is None


@pytest.mark.parametrize(
    "dt",
    [
        datetime(2020, 12, 31, 0, 59, 31, 987),
        date(2004, 2, 29),
    ],
)
@pytest.mark.parametrize(
    "fmt",
    [
        ALL_FMT_TOKENS,
        "%Y %",
        "%Y-%m-%d",
    ],
)
def test_datetime_format__unsupported(dt, fmt):
    result = c.item(0).format_dt(fmt).execute([dt])
    expected = dt.strftime(fmt)
    assert result == expected


def test_datetime_format_dt_wide(all_datetimes):
    fmt = SUPPORTED_FMT_TOKENS + r"""dea!"$%%&'#()*+,-./:;<=>?@[\]^_`{|}~"""
    f1 = c.item(0).format_dt(fmt).gen_converter()
    f2 = c.format_dt(fmt).gen_converter()
    for dt in all_datetimes:
        for dt_ in (dt, dt.date()):
            result1 = f1([dt])
            result2 = f2(dt)
            expected = dt.strftime(fmt)
            assert result1 == expected
            assert result2 == expected


def test_datetime_format_delimiter_wide(all_delimiters):
    dt = datetime(2020, 12, 31, 0, 59, 31, 987)

    fmt_pieces = ("%m", "%d", "%Y", "%B", "%B")
    for delimiter in all_delimiters:
        fmt = delimiter.join(fmt_pieces)
        expected = dt.strftime(fmt)
        result = c.item(0).format_dt(fmt).execute((dt,))
        assert result == expected
        result_2 = c.format_dt(fmt).execute(dt)
        assert result_2 == expected


def test_datetime_format_exceptions():
    for bad_fmt in (123,):
        with pytest.raises(ValueError):
            c.format_dt(bad_fmt)

    fmt = "%m/%d/%Y %H"
    for bad_dt in (None, 123, "24f", date(2020, 12, 31)):
        exc_1 = exc_2 = None
        try:
            c.format_dt(fmt).execute(bad_dt)
        except Exception as e:
            exc_1 = e

        try:
            bad_dt.strftime(fmt)
        except Exception as e:
            exc_2 = e

        assert exc_1.__class__ is exc_2.__class__
