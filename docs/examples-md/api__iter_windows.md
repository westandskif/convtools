/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.iter_windows(3, step=1).as_type(list).gen_converter(debug=True)

assert converter(range(5)) == [
    (0,),
    (0, 1),
    (0, 1, 2),
    (1, 2, 3),
    (2, 3, 4),
    (3, 4),
    (4,),
]

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __iter_windows=__naive_values__["__iter_windows"]):
    try:
        return list(__iter_windows(data_, 3, 1))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

