/// tab | convtools
    new: true

```python
from convtools import conversion as c

input_data = [
    {"a": 5, "b": "foo"},
    {"a": 10, "b": "foo"},
    {"a": 10, "b": "bar"},
    {"a": 10, "b": "bar"},
    {"a": 20, "b": "bar"},
]

# list of "a" values where "b" equals to "bar"
# "b" value of a row where "a" has Max value
conv = c.aggregate(
    {
        "a": c.ReduceFuncs.Array(c.item("a"), where=c.item("b") == "bar"),
        "b": c.ReduceFuncs.MaxRow(
            c.item("a"),
        ).item("b", default=None),
    }
).gen_converter(debug=True)

assert conv(input_data) == {"a": [10, 10, 20], "b": "bar"}

```
///

/// tab | debug stdout
```python
def aggregate_(_none, data_, *, __get_item_deep_default_simple=__naive_values__["__get_item_deep_default_simple"]):
    agg_data__v0 = agg_data__v1 = _none

    checksum_ = 0
    it_ = iter(data_)
    for row_ in it_:
        if row_["a"] is not None:
            if agg_data__v1 is _none:
                agg_data__v1 = (row_["a"], row_)
                checksum_ += 1
            elif agg_data__v1[0] < row_["a"]:
                agg_data__v1 = (row_["a"], row_)
        if row_["b"] == "bar":
            if agg_data__v0 is _none:
                agg_data__v0 = [row_["a"]]
                checksum_ += 1
            else:
                agg_data__v0.append(row_["a"])
        if checksum_ == 2:
            globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
            break
    for row_ in it_:
        if row_["a"] is not None:
            if agg_data__v1[0] < row_["a"]:
                agg_data__v1 = (row_["a"], row_)
        if row_["b"] == "bar":
            agg_data__v0.append(row_["a"])

    return {
        "a": ((None if (agg_data__v0 is _none) else agg_data__v0)),
        "b": __get_item_deep_default_simple(((None if (agg_data__v1 is _none) else agg_data__v1[1])), "b", None),
    }

def _converter(data_):
    global __none__
    _none = __none__
    try:
        return aggregate_(_none, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

