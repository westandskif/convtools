```python
from convtools import conversion as c

# Title‑case a name in an incoming dict
to_title = c.item("name").pipe(str.title).gen_converter()

assert to_title({"name": "jane doe"}) == "Jane Doe"

```
