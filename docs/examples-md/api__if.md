/// tab | convtools
    new: true

```python
from convtools import conversion as c

# No. 1
converter = (
    c.iter(c.if_(c.this < 0, c.this * 2, c.this / 2))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter([-1, 0, 1]) == [-2, 0, 0.5]

# No. 2
converter = (
    c.iter(
        c.if_multiple(
            (c.this < 0, c.this * 2),
            (c.this == 0, 100),
            (c.this < 10, c.this / 2),
            else_=c.this / 10,
        )
    )
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter([-1, 0, 1, 20]) == [-2, 100, 0.5, 2]

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return [(((_i * 2) if (_i < 0) else (_i / 2))) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def if_multiple_(data_):
    if data_ < 0:
        return data_ * 2
    if data_ == 0:
        return 100
    if data_ < 10:
        return data_ / 2
    return data_ / 10

def _converter(data_):
    try:
        return [if_multiple_(_i) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

