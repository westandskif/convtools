/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = (c.this + c.input_arg("increment")).gen_converter(debug=True)

assert converter(10, increment=5) == 15

```
///

/// tab | debug stdout
```python
def _converter(data_, *, increment):
    try:
        return (data_ + increment)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

```
///

