```python
from convtools import conversion as c

converter = c(
    {
        "a": c.item(0),
        "b": c.optional(c.item(1), skip_if=c.item(1) < 10),
        "c": c.optional(c.item(0) + c.item(1), keep_if=c.item(0)),
        "d": c.optional(c.item(0), skip_value=1),
    }
).gen_converter(debug=True)

assert converter((1, 2)) == {"a": 1, "c": 3}

```
