/// tab | convtools
    new: true

```python
from datetime import datetime
from convtools import conversion as c

data = {"obj": {"args": (1, 2), "kwargs": {"mode": "verbose"}}}

class A:
    @classmethod
    def f(cls, *args, **kwargs):
        return len(args) + len(kwargs)

# No. 1
converter = c.apply_func(
    A.f, c.item("obj", "args"), c.item("obj", "kwargs")
).gen_converter(debug=True)
assert converter(data) == 3

# No. 2
converter = (
    c.naive(A)
    .apply_method("f", c.item("obj", "args"), c.item("obj", "kwargs"))
    .gen_converter(debug=True)
)
assert converter(data) == 3

# No. 3
converter = (
    c.naive(A.f)
    .apply(c.item("obj", "args"), c.item("obj", "kwargs"))
    .gen_converter(debug=True)
)
assert converter(data) == 3

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __f=__naive_values__["__f"]):
    try:
        return __f(*data_["obj"]["args"], **data_["obj"]["kwargs"])
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __A=__naive_values__["__A"]):
    try:
        return __A.f(*data_["obj"]["args"], **data_["obj"]["kwargs"])
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __f=__naive_values__["__f"]):
    try:
        return __f(*data_["obj"]["args"], **data_["obj"]["kwargs"])
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

