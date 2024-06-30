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
def converter(data_):
    try:
        return data_.obj.a
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def attr_or_default(default_, data_):
    try:
        return data_.b
    except AttributeError:
        return default_

def converter(data_):
    try:
        return attr_or_default(None, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

