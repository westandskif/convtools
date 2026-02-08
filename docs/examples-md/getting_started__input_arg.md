```python
from convtools import conversion as c

converter = (c.this + c.input_arg("increment")).gen_converter(debug=True)

assert converter(10, increment=5) == 15

```
