/// tab | convtools
    new: true

```python
from convtools import conversion as c

# DEFAULT CONDITION
converter = (
    c.iter(c.this.and_then(c.this.as_type(int)))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(["1", None, 2.0]) == [1, None, 2]

# CUSTOM CONDITION
converter = (
    c.iter(c.this.and_then(c.this + 10, condition=c.this != 1))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(range(3)) == [10, 1, 12]

```
///

/// tab | debug stdout
```python
def converter(data_):
    try:
        return [(i and int(i)) for i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def converter(data_):
    try:
        return [(((i + 10) if (i != 1) else i)) for i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

