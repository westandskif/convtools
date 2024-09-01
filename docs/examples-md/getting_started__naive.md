/// tab | convtools
    new: true

```python
from convtools import conversion as c

VALUE_TO_VERBOSE = {
    1: "ACTIVE",
    2: "INACTIVE",
}
converter = c.naive(VALUE_TO_VERBOSE).item(c.this).gen_converter(debug=True)

assert converter(2) == "INACTIVE"

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __v=__naive_values__["__v"]):
    try:
        return __v[data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

