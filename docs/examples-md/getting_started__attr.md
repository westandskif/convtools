```python
from convtools import conversion as c

class Obj:
    a = 1

class Container:
    obj = Obj

assert c.attr("obj", "a").execute(Container, debug=True) == 1
assert c.attr("b", default=None).execute(Obj, debug=True) is None

```
