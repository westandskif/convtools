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
