```python
from convtools import conversion as c

converter = (
    c.iter(
        c.zip(
            c.repeat(c.item("a")),
            c.item("b"),
        )
    )
    .flatten()
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter([{"a": 1, "b": [2, 3]}, {"a": 10, "b": [4, 5]}]) == [
    (1, 2),
    (1, 3),
    (10, 4),
    (10, 5),
]

```
