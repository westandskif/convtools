/// tab | convtools
    new: true

```python
from convtools import conversion as c

# expect doesn't change input
converter = (
    c.iter(c.expect(c.this < 3, "too big") ** 10)
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(range(3)) == [0, 1, 1024]

# error_msg can be conversion itself
converter = (
    c.item("a")
    .expect(
        condition=c.this.len() > 3,
        error_msg=c.call_func("{} is too short".format, c.this),
    )
    .gen_converter(debug=True)
)
try:
    converter({"a": "val"})
except c.ExpectException as e:
    assert str(e) == "val is too short"

```
///

/// tab | debug stdout
```python
def _expect(data_):
    if data_ < 3:
        return data_
    raise ExpectException("too big")

def _converter(data_):
    try:
        return [(_expect(_i) ** 10) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _expect(data_, *, __format=__naive_values__["__format"]):
    if len(data_) > 3:
        return data_
    raise ExpectException(__format(data_))

def _converter(data_):
    try:
        return _expect(data_["a"])
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

