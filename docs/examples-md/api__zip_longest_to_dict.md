```python
from convtools import conversion as c

converter = (
    c.zip_longest(
        x=c.item("a"),
        y=c.item("b"),
        fill_value="N/A",
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter({"a": [1, 2, 3], "b": [4, 5]}) == [
    {"x": 1, "y": 4},
    {"x": 2, "y": 5},
    {"x": 3, "y": "N/A"},
]

```
