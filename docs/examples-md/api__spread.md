/// tab | convtools
    new: true

```python
from convtools import conversion as c

# Basic spread: merge nested dict into parent
conv = c.dict(
    ("id", c.item("id")),
    c.spread(c.item("metadata")),
).gen_converter(debug=True)

assert conv({"id": 1, "metadata": {"name": "Alice", "age": 30}}) == {
    "id": 1,
    "name": "Alice",
    "age": 30,
}

# Multiple spreads in one dict
conv = c.dict(
    c.spread(c.item("a")),
    c.spread(c.item("b")),
).gen_converter()

assert conv({"a": {"x": 1}, "b": {"y": 2}}) == {"x": 1, "y": 2}

# Override behavior: later keys win
conv = c.dict(
    ("x", 1),
    c.spread(c.item("overrides")),
).gen_converter()

assert conv({"overrides": {"x": 999}}) == {"x": 999}

# Spread combined with optional items
conv = c.dict(
    ("a", 1),
    c.spread(c.item("extra")),
    (c.optional(c.item("key"), skip_value=None), c.item("val")),
).gen_converter()

assert conv({"extra": {"x": 10}, "key": "b", "val": 2}) == {
    "a": 1,
    "x": 10,
    "b": 2,
}
assert conv({"extra": {}, "key": None, "val": 2}) == {"a": 1}

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return {
            "id": data_["id"],
            **data_["metadata"],
        }
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

