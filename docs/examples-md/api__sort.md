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
