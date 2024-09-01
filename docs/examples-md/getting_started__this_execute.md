/// tab | convtools
    new: true

```python
from convtools import conversion as c

assert (c.this + 1).execute(1, debug=True) == 2

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
{ data-search-exclude }
///

