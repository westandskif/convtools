from datetime import date, datetime

import pytest

from convtools import conversion as c

from .test_dt_utils import (
    ALL_FMT_TOKENS,
    SUPPORTED_FMT_TOKENS,
    all_dates,
    all_datetimes,
    all_delimiters,
)


@pytest.mark.parametrize(
    "fmt_pieces",
    [
        ("%Y", "%m", "%d", "%H", "%M", "%S", "%f"),
        ("%Y", "%m", "%d", "%I", "%M", "%S", "%f", "%p"),
        ("%y", "%j", "%H", "%M", "%S", "%f"),
    ],
)
def test_datetime_parse_delimiter_wide(fmt_pieces, all_delimiters):
    dt = datetime(2020, 12, 31, 23, 59, 12, 123456)
    for delimiter in all_delimiters:
        fmt = delimiter.join(fmt_pieces)
        dt_str = dt.strftime(fmt)
        result = c.item(0).datetime_parse(fmt).execute((dt_str,))
        result = c.datetime_parse(fmt).execute(dt_str)
        assert result == dt


def test_date_parse_delimiter_wide(all_delimiters):
    dt = date(2020, 12, 31)
    fmt_pieces = ("%Y", "%m", "%d")
    for delimiter in all_delimiters:
        fmt = delimiter.join(fmt_pieces)
        dt_str = dt.strftime(fmt)
        result = c.item(0).date_parse(fmt).execute((dt_str,))
        result = c.date_parse(fmt).execute(dt_str)
        assert result == dt


@pytest.mark.parametrize(
    "fmt_pieces",
    [
        ("%Y", "%m", "%d", "%H", "%M", "%S", "%f"),
        ("%%", "%Y", "%m", "%d", "%I", "%M", "%S", "%f", "%p"),
    ],
)
def test_datetime_parse_dt_wide(fmt_pieces, all_datetimes):
    fmt = " ".join(fmt_pieces)
    for dt in all_datetimes:
        dt_str = dt.strftime(fmt)
        result = c.item(0).datetime_parse(fmt).execute((dt_str,))
        result = c.datetime_parse(fmt).execute(dt_str)
        assert result == dt


@pytest.mark.parametrize(
    "fmt",
    ["%Y-%m-%d", "%m/%d/%Y"],
)
def test_date_parse_dt_wide(fmt, all_dates):
    for dt in all_dates:
        dt_str = dt.strftime(fmt)
        result = c.item(0).date_parse(fmt).execute((dt_str,))
        result = c.date_parse(fmt).execute(dt_str)
        assert result == dt


def test_datetime_parse_defaults():
    assert c.datetime_parse("%Y").execute("2000") == datetime(2000, 1, 1)


def test_dt_parse_base_n_multiple_formats():
    with c.OptionsCtx() as options:
        options.debug = False
        assert c.date_parse("%Y-%m-%d").execute("2020-01-31") == date(
            2020, 1, 31
        )
        assert c.item(0).date_parse("%Y-%m-%d").execute(
            ("2020-01-31",)
        ) == date(2020, 1, 31)
        assert c.date_parse("%Y-%m-%d", "%m/%d/%Y").execute(
            "1/31/2020"
        ) == date(2020, 1, 31)

        assert c.datetime_parse("%Y-%m-%d %H:%M").execute(
            "2020-01-31 15:40"
        ) == datetime(2020, 1, 31, 15, 40)
        assert c.item(0).datetime_parse("%Y-%m-%d %H:%M").execute(
            ("2020-01-31 15:40",)
        ) == datetime(2020, 1, 31, 15, 40)
        assert c.datetime_parse("%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M").execute(
            "1/31/2020 15:40"
        ) == datetime(2020, 1, 31, 15, 40)

    with pytest.raises(ValueError):
        assert c.date_parse("%Y-%m-%d", "%m/%d/%Y", "%Y_%m_%d").execute(
            "2020__1__31"
        )
    with pytest.raises(ValueError):
        assert c.datetime_parse("%Y-%m-%d", "%m/%d/%Y", "%Y_%m_%d").execute(
            "2020__1__31"
        )

    t = [1]
    result = c.date_parse("%Y-%m-%d", default=t).execute("1/1/2000")
    assert result == t and result is not t
    result = c.datetime_parse("%Y-%m-%d", default=t).execute("1/1/2000")
    assert result == t and result is not t


@pytest.mark.parametrize(
    "method,result",
    [
        ("date_parse", date(2020, 1, 1)),
        ("datetime_parse", datetime(2020, 1, 1)),
    ],
)
def test_date_parse_default_once(method, result):
    # testing that default is evaluated only when needed
    flag = True

    def f():
        nonlocal flag
        if flag:
            flag = False
        else:
            raise ValueError
        return 1

    converter = getattr(c, method)(
        "%Y-%m-%d", default=c.call_func(f)
    ).gen_converter()
    for i in range(2):
        assert converter("2020-01-01") == result
    assert converter("1/1/2020") == 1
    with pytest.raises(ValueError):
        assert converter("1/1/2020")


@pytest.mark.parametrize("method", ["date_parse", "datetime_parse"])
@pytest.mark.parametrize("main_format", ["%Y-%m-%d"])
@pytest.mark.parametrize("other_formats", [(), ("%Y_%m_%d", "%Y__%m__%d")])
@pytest.mark.parametrize(
    "default", [None, c.naive(None), c.call_func(lambda: None)]
)
def test_date_parse_default(method, main_format, other_formats, default):
    assert (
        getattr(c, method)(
            main_format, *other_formats, default=default
        ).execute("1/1/2000")
        is None
    )


@pytest.mark.parametrize(
    "dt",
    [
        datetime(2020, 12, 31, 0, 59, 31, 987),
        datetime(2020, 12, 31, 13, 59, 31, 987),
    ],
)
@pytest.mark.parametrize(
    "fmt",
    [
        "%H",
        "%Y %I",
        "%Y %p",
    ],
)
def test_datetime_parse__unsupported(dt, fmt):
    dt_str = dt.strftime(fmt)
    result = c.item(0).datetime_parse(fmt).execute([dt_str])
    expected = datetime.strptime(dt_str, fmt)
    assert expected == result


def test_datetime_parse_exceptions():
    for bad_fmt in (123,):
        with pytest.raises(ValueError):
            c.datetime_parse(bad_fmt)

    for bad_fmt in ("%Y %",):
        f = c.datetime_parse(bad_fmt).gen_converter()
        with pytest.raises(ValueError):
            f("2000 %")
