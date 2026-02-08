```python
from convtools import conversion as c

converter = c.iter(c.this + 1).gen_converter(debug=True)
assert list(converter(range(3))) == [1, 2, 3]

converter = c.item("objects").iter(c.this + 1).gen_converter(debug=True)
assert list(converter({"objects": range(3)})) == [1, 2, 3]

converter = c.list_comp(c.this + 1, where=c.this < 2).gen_converter(debug=True)
assert converter(range(3)) == [1, 2]

converter = c.dict_comp(c.this, c.this + 1).gen_converter(debug=True)
assert converter(range(3)) == {0: 1, 1: 2, 2: 3}

```
