from datetime import date, datetime, time

import pytest

from convtools import conversion as c
from convtools._dt import LOCALE_BASED_MAPS, DatetimeFormat, _LocaleBasedMaps

from .test_dt_utils import (
    ALL_FMT_TOKENS,
    SUPPORTED_FMT_TOKENS,
    all_dates,
    all_datetimes,
    all_delimiters,
)


def test_datetime_format__ensure_supported():
    c_fmt = DatetimeFormat(SUPPORTED_FMT_TOKENS)
    assert c_fmt.to_code("data_", c_fmt._init_ctx()) is not None

    c_fmt = DatetimeFormat(ALL_FMT_TOKENS)
    assert c_fmt.to_code("data_", c_fmt._init_ctx()) is None


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
    try:
        result = c.item(0).format_dt(fmt).execute([dt])
    except Exception as exc_1:
        exc_2 = None
        try:
            dt.strftime(fmt)
        except Exception as e:
            exc_2 = e
        assert exc_1.__class__ is exc_2.__class__
    else:
        expected = dt.strftime(fmt)
        assert result == expected


def test_datetime_format_dt_wide(all_datetimes):
    fmt = SUPPORTED_FMT_TOKENS + r"""dea!"$%%&'#()*+,-./:;<=>?@[\]^_`{|}~"""
    fmt = LOCALE_BASED_MAPS.fix_strftime_format(fmt)
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


def test_datetime_format_literal_escapes():
    """Literal backslashes/control chars must match strftime, not be
    reinterpreted by the generated f-string compiler."""
    dt = datetime(2024, 1, 2, 3, 4, 5)
    formats = [
        r"\n%Y",
        r"\t%Y",
        r"\x41%Y",
        r"\\%Y",
        r"\N%Y",
        "\n%Y",
        "\t%Y",
        r"\"%Y",
        "\\",
        '"%Y"',
        "{%Y}",
    ]
    for fmt in formats:
        result = c.format_dt(fmt).execute(dt)
        expected = dt.strftime(fmt)
        assert result == expected, repr(fmt)


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


def test_datetime_format_time_uses_strftime():
    t = time(5, 6, 7)
    assert c.format_dt("%H:%M:%S").execute(t) == "05:06:07"
    fmt = "%H:%M:%S %c"
    assert c.format_dt(fmt).execute(t) == t.strftime(fmt)
    assert c.format_dt("%Y-%m-%d").execute(t) == t.strftime("%Y-%m-%d")


def test_strftime_fix_init_does_not_capture_locale_names():
    maps = _LocaleBasedMaps()
    maps.fix_strftime_format("%H:%M")
    assert maps.late_initialized is False
    assert maps._strftime_fix_initialized is True
    maps.fix_strftime_format("%Y")
    _ = maps.upper_y_format_is_supported
    assert maps.late_initialized is False

    maps_y = _LocaleBasedMaps()
    _ = maps_y.upper_y_format_is_supported
    assert maps_y.late_initialized is False
    assert maps_y._strftime_fix_initialized is True

    maps_names = _LocaleBasedMaps()
    _ = maps_names.hour_to_pct_lower_p
    assert maps_names.late_initialized is True
    assert maps_names._strftime_fix_initialized is True
