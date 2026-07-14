```python
from convtools import conversion as c

assert c.escaped_string("1 + 1").execute(None) == 2
assert c.inline_expr("1 + 1").execute(None) == 2

assert c.inline_expr("{} + {}").pass_args(c.this, 1).execute(10) == 11
assert c.inline_expr("{a} + {b}").pass_args(a=c.this, b=1).execute(10) == 11

```
