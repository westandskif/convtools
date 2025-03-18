/// tab | convtools
    new: true

```python
from datetime import date, datetime
from convtools import conversion as c

# SIMPLE DEFAULT
converter = c.date_parse("%m/%d/%Y", default=None).gen_converter(debug=True)
assert converter("some str") is None

# DEFAULT AS CONVERSION
converter = c.date_parse(
    "%m/%d/%Y", default=c.call_func(date.today)
).gen_converter(debug=True)
assert converter("some str") == date.today()

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

def _try_multiple(data_, *, __v_i=__naive_values__["__v_i"]):
    try:
        return _datetime_parse(data_).date()
    except __v_i:
        pass
    return None

def _converter(data_):
    try:
        return _try_multiple(data_)
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

def _try_multiple(data_, *, __v_e=__naive_values__["__v_e"], __today=__naive_values__["__today"]):
    try:
        return _datetime_parse(data_).date()
    except __v_e:
        pass
    return __today()

def _converter(data_):
    try:
        return _try_multiple(data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

