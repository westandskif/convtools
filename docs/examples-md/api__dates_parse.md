/// tab | convtools
    new: true

```python
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
assert converter({"dt": "12/31/2020 15:40"}) == datetime(
    2020, 12, 31, 15, 40
)

```
///

/// tab | debug stdout
```python
def _datetime_parse(data_, *, __v=__naive_values__["__v"], __datetime=__naive_values__["__datetime"]):
    match = __v.match(data_)
    if not match:
        raise ValueError("time data %r does not match format %r" % (data_, """%m/%d/%Y"""))
    if len(data_) != match.end():
        raise ValueError("unconverted data remains: %s" % data_[match.end() :])
    groups_ = match.groups()
    return __datetime(int(groups_[2]), int(groups_[0]), int(groups_[1]), 0, 0, 0, 0)

def _converter(data_):
    try:
        return _datetime_parse(data_).date()
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _datetime_parse(data_, *, __v=__naive_values__["__v"], __datetime=__naive_values__["__datetime"]):
    match = __v.match(data_)
    if not match:
        raise ValueError("time data %r does not match format %r" % (data_, """%m/%d/%Y"""))
    if len(data_) != match.end():
        raise ValueError("unconverted data remains: %s" % data_[match.end() :])
    groups_ = match.groups()
    return __datetime(int(groups_[2]), int(groups_[0]), int(groups_[1]), 0, 0, 0, 0)

def _datetime_parse_e(data_, *, __v_q=__naive_values__["__v_q"], __datetime=__naive_values__["__datetime"]):
    match = __v_q.match(data_)
    if not match:
        raise ValueError("time data %r does not match format %r" % (data_, """%Y-%m-%d"""))
    if len(data_) != match.end():
        raise ValueError("unconverted data remains: %s" % data_[match.end() :])
    groups_ = match.groups()
    return __datetime(int(groups_[0]), int(groups_[1]), int(groups_[2]), 0, 0, 0, 0)

def _try_multiple(data_, *, __v_i=__naive_values__["__v_i"]):
    try:
        return _datetime_parse(data_).date()
    except __v_i:
        pass
    return _datetime_parse_e(data_).date()

def _converter(data_):
    try:
        return [_try_multiple(_i) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _datetime_parse(data_, *, __v=__naive_values__["__v"], __datetime=__naive_values__["__datetime"]):
    match = __v.match(data_)
    if not match:
        raise ValueError("time data %r does not match format %r" % (data_, """%m/%d/%Y %H:%M"""))
    if len(data_) != match.end():
        raise ValueError("unconverted data remains: %s" % data_[match.end() :])
    groups_ = match.groups()
    return __datetime(int(groups_[2]), int(groups_[0]), int(groups_[1]), int(groups_[3]), int(groups_[4]), 0, 0)

def _converter(data_):
    try:
        return _datetime_parse(data_["dt"])
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

