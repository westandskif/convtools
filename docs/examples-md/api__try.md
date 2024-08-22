/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = (
    c.iter(
        c.try_(c.item(0) / c.item(1))
        .except_(ZeroDivisionError, value=c.this, re_raise_if=c.item(0) == 0)
        .except_(TypeError, None)
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter([(1, 2), (3, 0), (4, "abc")]) == [0.5, (3, 0), None]

```
///

/// tab | debug stdout
```python
def _except_(data_):
    try:
        return data_[0] / data_[1]
    except ZeroDivisionError as exc_:
        if data_[0] == 0:
            raise
        return data_
    except TypeError as exc_:
        return None

def _converter(data_):
    try:
        return [_except_(_i) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

