/// tab | convtools
    new: true

```python
from convtools import conversion as c

data = [
    {"a": 0, "b": 4},
    {"a": None, "b": 3},
    {"a": 1, "b": 2},
    {"a": 0, "b": 1},
]
with c.OptionsCtx() as options:
    options.debug = True
    result = sorted(
        data,
        key=c.sorting_key(
            c.item("a").desc(none_first=True),
            c.item("b"),
        ),
    )
assert result == [
    {"a": None, "b": 3},
    {"a": 1, "b": 2},
    {"a": 0, "b": 1},
    {"a": 0, "b": 4},
]

```
///

/// tab | debug stdout
```python
def _sorting_key_wrapper():
    def _sorting_key(data_):
        return (data_['a'] is not None, ReversedOrdering(data_['a']), data_['b'])
    return _sorting_key
def _converter(data_):
    try:
        return _sorting_key_wrapper()
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

```
///

