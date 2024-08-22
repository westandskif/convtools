/// tab | convtools
    new: true

```python
from convtools import conversion as c

conversion = c.this + 1
converter = conversion.gen_converter(debug=True)

assert converter(1) == 2

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return data_ + 1
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

