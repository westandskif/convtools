/// tab | convtools
    new: true

```python
from datetime import datetime
from convtools import conversion as c

converter = (
    c.this.add_label({"a": c.item("a")})
    .item("b")
    .iter({"a": c.label("a"), "b": c.this})
    .as_type(list)
    .gen_converter(debug=True)
)
# SAME
converter_2 = (
    c.this.pipe(c.item("b"), label_input={"a": c.item("a")})
    .iter({"a": c.label("a"), "b": c.this})
    .as_type(list)
    .gen_converter(debug=True)
)
input_data = {
    "a": 1,
    "b": [2, 3, 4],
}
expected_output = [{"a": 1, "b": 2}, {"a": 1, "b": 3}, {"a": 1, "b": 4}]
assert (
    converter(input_data) == expected_output
    and converter_2(input_data) == expected_output
)


# BETTER WITHOUT LABELS (HERE IT'S POSSIBLE)
converter_3 = (
    c.zip(a=c.repeat(c.item("a")), b=c.item("b"))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter_3(input_data) == expected_output

```
///

/// tab | debug stdout
```python
def pipe_(_labels, input_):
    _labels["a"] = input_["a"]
    return input_

def _converter(data_):
    _labels = {}
    try:
        return [
            {
                "a": _labels["a"],
                "b": _i,
            }
            for _i in pipe_(_labels, data_)["b"]
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def pipe_(_labels, input_):
    _labels["a"] = input_["a"]
    return [
        {
            "a": _labels["a"],
            "b": _i,
        }
        for _i in input_["b"]
    ]

def _converter(data_):
    _labels = {}
    try:
        return pipe_(_labels, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __repeat=__naive_values__["__repeat"]):
    try:
        return [
            {
                "a": _i[0],
                "b": _i[1],
            }
            for _i in zip(__repeat(data_["a"]), data_["b"])
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

