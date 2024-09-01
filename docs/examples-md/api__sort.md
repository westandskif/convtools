/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.this.sort(key=lambda x: x, reverse=True).gen_converter(
    debug=True
)
assert list(converter(range(3))) == [2, 1, 0]


data = [
    {"a": 0, "b": 4},
    {"a": None, "b": 3},
    {"a": 1, "b": 2},
    {"a": 0, "b": 1},
]
converter = c.this.sort(
    key=(
        c.item("a").desc(none_first=True),
        c.item("b"),
    )
).gen_converter(debug=True)
assert converter(data) == [
    {"a": None, "b": 3},
    {"a": 1, "b": 2},
    {"a": 0, "b": 1},
    {"a": 0, "b": 4},
]

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __lambda=__naive_values__["__lambda"]):
    try:
        return sorted(data_, key=__lambda, reverse=True)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _sorting_key_wrapper():
    def _sorting_key(data_):
        return (data_["a"] is not None, ReversedOrdering(data_["a"]), data_["b"])

    return _sorting_key

def _converter(data_):
    try:
        return sorted(data_, key=_sorting_key_wrapper())
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

