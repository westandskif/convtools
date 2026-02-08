```python
from convtools import conversion as c

converter = c.item(1, "value").gen_converter(debug=True)

assert converter([{"value": 10}, {"value": 20}]) == 20

```
