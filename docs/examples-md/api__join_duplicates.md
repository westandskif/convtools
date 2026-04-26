```python
from convtools import conversion as c


left = [{"id": 1, "value": "a"}, {"id": 1, "value": "b"}]
right = [{"id": 1, "value": "x"}, {"id": 1, "value": "y"}]

conv = (
    c.join(c.item(0), c.item(1), c.LEFT.item("id") == c.RIGHT.item("id"))
    .as_type(list)
    .gen_converter()
)

assert conv((left, right)) == [
    ({"id": 1, "value": "a"}, {"id": 1, "value": "x"}),
    ({"id": 1, "value": "a"}, {"id": 1, "value": "y"}),
    ({"id": 1, "value": "b"}, {"id": 1, "value": "x"}),
    ({"id": 1, "value": "b"}, {"id": 1, "value": "y"}),
]

```
