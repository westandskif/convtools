/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = (
    c.iter(
        (c.item("value") + 1).pipe(
            c.if_(c.this < 0, c.this * c.this, c.this * 2)
        )
    )
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter([{"value": -4}, {"value": 2}]) == [9, 6]

```
///

/// tab | debug stdout
```python
def pipe_(input_):
    return (input_ * input_) if (input_ < 0) else (input_ * 2)

def converter(data_):
    try:
        return [pipe_((i["value"] + 1)) for i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

