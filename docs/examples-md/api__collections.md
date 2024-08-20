/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c(
    {
        "a": c.item(0),
        "b": c.item(1),
        "c": c.item(0) + c.item(1),
        # keys are dynamic too
        c.call_func("d{}".format, c.item(0)): "key is dynamic",
    }
).gen_converter(debug=True)

assert converter((1, 2)) == {"a": 1, "b": 2, "c": 3, "d1": "key is dynamic"}


assert c([1, c.this, 2]).execute(None, debug=True) == [1, None, 2]

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __format=__naive_values__["__format"]):
    try:
        return {
            "a": data_[0],
            "b": data_[1],
            "c": (data_[0] + data_[1]),
            __format(data_[0]): "key is dynamic",
        }
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return [
            1,
            data_,
            2,
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

