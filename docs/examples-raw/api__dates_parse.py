from datetime import date, datetime
from convtools import conversion as c

# SINGLE FORMAT
converter = c.date_parse("%m/%d/%Y").gen_converter(debug=True)
assert converter("12/31/2020") == date(2020, 12, 31)

# MULTIPLE FORMATS
converter = (
    c.iter(c.date_parse("%m/%d/%Y", "%Y-%m-%d"))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(["12/31/2020", "2021-01-01"]) == [
    date(2020, 12, 31),
    date(2021, 1, 1),
]

# SAME FOR DATETIMES, BUT LET'S USE A METHOD
converter = (
    c.item("dt").datetime_parse("%m/%d/%Y %H:%M").gen_converter(debug=True)
)
assert converter({"dt": "12/31/2020 15:40"}) == datetime(2020, 12, 31, 15, 40)
