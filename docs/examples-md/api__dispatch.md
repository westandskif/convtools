/// tab | convtools
    new: true

```python
from convtools import conversion as c


input_data = [
    {"version": "v1", "field1": 10},
    {"version": "v2", "field2": 20},
    {"version": "v3", "field": 30},
]

converter = (
    c.iter(
        c.this.dispatch(
            c.item("version"),
            {
                "v1": c.item("field1"),
                "v2": c.item("field2"),
            },
            default=c.item("field"),
        )
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter(input_data) == [10, 20, 30]

```
///

/// tab | debug stdout
```python
def branch(data_):
    return data_["field1"]

def branch_i(data_):
    return data_["field2"]

def branch_else(data_):
    return data_["field"]

def converter(data_, *, __v=__naive_values__["__v"], __branch_else=__naive_values__["__branch_else"]):
    try:
        return [__v.get(i["version"], __branch_else)(i) for i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

