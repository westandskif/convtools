from datetime import date, datetime, timedelta, timezone
from time import time

import pytest

from convtools import conversion as c


def test_date_parse():
    assert c.date_parse("%Y-%m-%d").execute("2020-01-31") == date(2020, 1, 31)
    assert c.item(0).date_parse("%Y-%m-%d").execute(("2020-01-31",)) == date(
        2020, 1, 31
    )
    assert c.date_parse("%Y-%m-%d", "%m/%d/%Y").execute("1/31/2020") == date(
        2020, 1, 31
    )

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
