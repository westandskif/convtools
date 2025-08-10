```python
from convtools import conversion as c

rows = [
    {"name": "ada", "score": 10},
    {"name": "grace", "score": 12},
    {"name": "linus", "score": 9},
]

to_names = (
    c.iter(c.item("name").pipe(str.title))
    .as_type(list)  # return a list, not a generator
    .gen_converter()
)

assert to_names(rows) == ["Ada", "Grace", "Linus"]

```
