/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.this.as_type(list).gen_converter(debug=True)

assert converter(range(2)) == [0, 1]

```
///

/// tab | debug stdout
```python
def converter(data_):
    try:
        return list(data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

