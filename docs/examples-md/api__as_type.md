```python
from convtools import conversion as c

converter = c.this.as_type(list).gen_converter(debug=True)

assert converter(range(2)) == [0, 1]

```
