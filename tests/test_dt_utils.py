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
