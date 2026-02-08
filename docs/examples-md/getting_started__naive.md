```python
from convtools import conversion as c

VALUE_TO_VERBOSE = {
    1: "ACTIVE",
    2: "INACTIVE",
}
converter = c.naive(VALUE_TO_VERBOSE).item(c.this).gen_converter(debug=True)

assert converter(2) == "INACTIVE"

```
