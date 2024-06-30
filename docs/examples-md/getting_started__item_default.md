/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.item(1, default=-1).gen_converter(debug=True)

assert converter([10]) == -1

```
///

/// tab | debug stdout
```python
def converter(data_, *, __get_1_or_default=__naive_values__["__get_1_or_default"]):
    try:
        return __get_1_or_default(data_, 1, -1)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

