from datetime import date, datetime
from decimal import Decimal

from convtools import conversion as c


def test_doc__index_deserialization():
    class Employee:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    input_data = {
        "objects": [
            {
                "id": 1,
                "first_name": "john",
                "last_name": "black",
                "dob": None,
                "salary": "1,000.00",
                "department": "D1 ",
                "date": "2000-01-01",
            },
            {
                "id": 2,
                "first_name": "bob",
                "last_name": "wick",
                "dob": "1900-01-01",
                "salary": "1,001.00",
                "department": "D3 ",
                "date": "2000-01-01",
            },
        ]
    }

    # prepare a few conversions to reuse
    c_strip = c.this().call_method("strip")
    c_capitalize = c.this().call_method("capitalize")
    c_decimal = c.this().call_method("replace", ",", "").as_type(Decimal)
    c_date = c.call_func(datetime.strptime, c.this(), "%Y-%m-%d").call_method(
        "date"
    )
    # reusing c_date
    c_optional_date = c.if_(c.this(), c_date, None)

    first_name = c.item("first_name").pipe(c_capitalize)
    last_name = c.item("last_name").pipe(c_capitalize)
    # call "format" method of a string and pass first & last names as
    # parameters
    full_name = c("{} {}").call_method("format", first_name, last_name)

    conv = (
        c.item("objects")
        .pipe(
            c.generator_comp(
                {
                    "id": c.item("id"),
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "date_of_birth": c.item("dob").pipe(c_optional_date),
                    "salary": c.item("salary").pipe(c_decimal),
                    # pass a hardcoded dict and to get value by "department"
                    # key
                    "department_id": c.naive(
                        {
                            "D1": 10,
                            "D2": 11,
                            "D3": 12,
                        }
                    ).item(c.item("department").pipe(c_strip)),
                    "date": c.item("date").pipe(c_date),
                }
            )
        )
        .pipe(
            c.dict_comp(
                c.item("id"),  # key
                c.apply_func(  # value
                    Employee,
                    args=(),
                    kwargs=c.this(),
                ),
            )
        )
        .gen_converter(debug=True)  # to see print generated code
    )

    result = conv(input_data)
    assert result[1].kwargs == {
        "date": date(2000, 1, 1),
        "date_of_birth": None,
        "department_id": 10,
        "first_name": "John",
        "full_name": "John Black",
        "id": 1,
        "last_name": "Black",
        "salary": Decimal("1000.00"),
    }
    assert result[2].kwargs == {
        "date": date(2000, 1, 1),
        "date_of_birth": date(1900, 1, 1),
        "department_id": 12,
        "first_name": "Bob",
        "full_name": "Bob Wick",
        "id": 2,
        "last_name": "Wick",
        "salary": Decimal("1001.00"),
    }
