```python
from convtools import conversion as c

conversion = c.this + 1
converter = conversion.gen_converter(debug=True)

assert converter(1) == 2

```
