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

    # get by "department" key and then call method "strip"
    department = c.item("department").call_method("strip")
    first_name = c.item("first_name").call_method("capitalize")
    last_name = c.item("last_name").call_method("capitalize")

    # call "format" method of a string and pass first & last names as
    # parameters
    full_name = c("{} {}").call_method("format", first_name, last_name)
    date_of_birth = c.item("dob")

    # partially initialized "strptime"
    parse_date = c.call_func(
        datetime.strptime, c.this(), "%Y-%m-%d"
    ).call_method("date")

    conv = (
        c.item("objects")
        .pipe(
            c.generator_comp(
                {
                    "id": c.item("id"),
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "date_of_birth": c.if_(
                        date_of_birth,
                        date_of_birth.pipe(parse_date),
                        None,
                    ),
                    "salary": c.call_func(
                        Decimal,
                        c.item("salary").call_method("replace", ",", ""),
                    ),
                    # pass a hardcoded dict and to get value by "department"
                    # key
                    "department_id": c.naive(
                        {
                            "D1": 10,
                            "D2": 11,
                            "D3": 12,
                        }
                    ).item(department),
                    "date": c.item("date").pipe(parse_date),
                }
            )
        )
        .pipe(
            c.dict_comp(
                c.item("id"),  # key
                # write a python code expression, format with passed parameters
                c.inline_expr("{employee_cls}(**{kwargs})").pass_args(
                    employee_cls=Employee,
                    kwargs=c.this(),
                ),  # value
            )
        )
        .gen_converter(debug=True)
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
