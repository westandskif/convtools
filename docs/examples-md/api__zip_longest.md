```python
from convtools import conversion as c

converter = (
    c.zip_longest(
        c.item("a"),
        c.item("b"),
        fill_value="N/A",
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter({"a": [1, 2, 3], "b": [4, 5]}) == [
    (1, 4),
    (2, 5),
    (3, "N/A"),
]

```
