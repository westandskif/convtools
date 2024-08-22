/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.filter(c.this < 3).gen_converter(debug=True)
assert list(converter(range(100))) == [0, 1, 2]

converter = c.this.filter(c.this < 3).gen_converter(debug=True)
assert list(converter(range(100))) == [0, 1, 2]

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return (_i for _i in data_ if ((_i < 3)))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (_i for _i in data_ if ((_i < 3)))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

