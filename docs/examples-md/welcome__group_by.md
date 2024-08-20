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

conv = (
    c.group_by(c.item("b"))
    .aggregate(
        {
            "b": c.item("b"),
            "a_first": c.ReduceFuncs.First(c.item("a"), where=c.item("a") > 5),
            "a_max": c.ReduceFuncs.Max(c.item("a")),
        }
    )
    .gen_converter(debug=True)
)

assert conv(input_data) == [
    {"b": "foo", "a_first": 10, "a_max": 10},
    {"b": "bar", "a_first": 10, "a_max": 20},
]

```
///

/// tab | debug stdout
```python
class AggData_:
    __slots__ = ["v0", "v1"]

    def __init__(self, _none=__none__):
        self.v0 = _none
        self.v1 = _none

def group_by_(_none, data_):
    signature_to_agg_data_ = defaultdict(AggData_)

    for row_ in data_:
        _r0_ = row_["a"]
        agg_data_ = signature_to_agg_data_[row_["b"]]
        if _r0_ is not None:
            if agg_data_.v1 is _none:
                agg_data_.v1 = _r0_
            elif agg_data_.v1 < _r0_:
                agg_data_.v1 = _r0_
        if _r0_ > 5:
            if agg_data_.v0 is _none:
                agg_data_.v0 = _r0_

    return [
        {
            "b": signature_,
            "a_first": ((None if (agg_data_.v0 is _none) else agg_data_.v0)),
            "a_max": ((None if (agg_data_.v1 is _none) else agg_data_.v1)),
        }
        for signature_, agg_data_ in signature_to_agg_data_.items()
    ]

def _converter(data_):
    global __none__
    _none = __none__
    try:
        return group_by_(_none, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

