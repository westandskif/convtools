```python
from convtools import conversion as c

# Lazy iterator by default
converter = c.filter(c.this < 3).gen_converter()
assert list(converter(range(10))) == [0, 1, 2]

# Materialize into a container with `cast=`
assert c.filter(c.this < 3, cast=list).execute(range(10)) == [0, 1, 2]

# Chained after a concrete comprehension, preserves its container type
assert c.list_comp(c.this * 2).filter(c.this < 6).execute(range(5)) == [
    0,
    2,
    4,
]

```
