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
