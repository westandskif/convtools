from datetime import date, datetime
from decimal import Decimal

from convtools import conversion as c


def test_doc__index_intro():

    # ======== #
    # GROUP BY #
    # ======== #
    input_data = [
        {"a": 5, "b": "foo"},
        {"a": 10, "b": "foo"},
        {"a": 10, "b": "bar"},
        {"a": 10, "b": "bar"},
        {"a": 20, "b": "bar"},
    ]

    conv = (
        c.group_by(c.item("b"))
        .aggregate(
            {
                "b": c.item("b"),
                "a_first": c.ReduceFuncs.First(c.item("a")),
                "a_max": c.ReduceFuncs.Max(c.item("a")),
            }
        )
        .gen_converter(debug=True)
    )

    assert conv(input_data) == [
        {"b": "foo", "a_first": 5, "a_max": 10},
        {"b": "bar", "a_first": 10, "a_max": 20},
    ]

    # ========= #
    # AGGREGATE #
    # ========= #
    conv = c.aggregate(
        {
            # list of "a" values where "b" equals to "bar"
            "a": c.ReduceFuncs.Array(c.item("a")).filter(c.item("b") == "bar"),
            # "b" value of a row where "a" has Max value
            "b": c.ReduceFuncs.MaxRow(
                c.item("a"),
            ).item("b", default=None),
        }
    ).gen_converter(debug=True)

    assert conv(input_data) == {"a": [10, 10, 20], "b": "bar"}

    # ==== #
    # JOIN #
    # ==== #
    collection_1 = [
        {"id": 1, "name": "Nick"},
        {"id": 2, "name": "Joash"},
        {"id": 3, "name": "Bob"},
    ]
    collection_2 = [
        {"ID": "3", "age": 17, "country": "GB"},
        {"ID": "2", "age": 21, "country": "US"},
        {"ID": "1", "age": 18, "country": "CA"},
    ]
    input_data = (collection_1, collection_2)

    conv = (
        c.join(
            c.item(0),
            c.item(1),
            c.and_(
                c.LEFT.item("id") == c.RIGHT.item("ID").as_type(int),
                c.RIGHT.item("age") >= 18,
            ),
            how="left",
        )
        .pipe(
            c.list_comp(
                {
                    "id": c.item(0, "id"),
                    "name": c.item(0, "name"),
                    "age": c.item(1, "age", default=None),
                    "country": c.item(1, "country", default=None),
                }
            )
        )
        .gen_converter(debug=True)
    )

    assert conv(input_data) == [
        {"id": 1, "name": "Nick", "age": 18, "country": "CA"},
        {"id": 2, "name": "Joash", "age": 21, "country": "US"},
        {"id": 3, "name": "Bob", "age": None, "country": None},
    ]
