```python
from convtools import conversion as c

converter = c.filter(c.this < 3).gen_converter(debug=True)
assert list(converter(range(100))) == [0, 1, 2]

converter = c.this.filter(c.this < 3).gen_converter(debug=True)
assert list(converter(range(100))) == [0, 1, 2]

```
