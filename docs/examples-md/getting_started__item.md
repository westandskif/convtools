```python
from convtools import conversion as c

converter = c.item(1).gen_converter()

assert converter([10, 20]) == 20

```
