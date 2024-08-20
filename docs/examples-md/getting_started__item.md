/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.item(1).gen_converter(debug=True)

assert converter([10, 20]) == 20

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return data_[1]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

