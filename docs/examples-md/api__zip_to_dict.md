```python
from convtools import conversion as c

converter = (
    c.iter(
        c.zip(
            a=c.repeat(c.item("a")),
            b=c.item("b"),
        )
    )
    .flatten()
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter([{"a": 1, "b": [2, 3]}, {"a": 10, "b": [4, 5]}]) == [
    {"a": 1, "b": 2},
    {"a": 1, "b": 3},
    {"a": 10, "b": 4},
    {"a": 10, "b": 5},
]

```
