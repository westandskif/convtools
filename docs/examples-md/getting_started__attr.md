/// tab | convtools
    new: true

```python
from convtools import conversion as c

class Obj:
    a = 1

class Container:
    obj = Obj

assert c.attr("obj", "a").execute(Container, debug=True) == 1
assert c.attr("b", default=None).execute(Obj, debug=True) is None

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return data_.obj.a
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __get_attr_deep_default_simple=__naive_values__["__get_attr_deep_default_simple"]):
    try:
        return __get_attr_deep_default_simple(data_, "b", None)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

