/// tab | convtools
    new: true

```python
from convtools import conversion as c


class A:
    get_one = c.naive(1).gen_converter(class_method=True, debug=True)

    get_two = c.naive(2).gen_converter(method=True, debug=True)

    get_self = c.input_arg("self").gen_converter(signature="self", debug=True)


a = A()

assert A.get_one(None) == 1 and a.get_two(None) == 2 and a.get_self() is a

```
///

/// tab | debug stdout
```python
def _converter(cls, data_):
    try:
        return 1
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(self, data_):
    try:
        return 2
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(self):
    try:
        return self
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

