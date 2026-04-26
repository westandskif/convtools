from datetime import datetime
from convtools import conversion as c

data = {"obj": {"args": (1, 2), "kwargs": {"mode": "verbose"}}}

class A:
    @classmethod
    def f(cls, *args, **kwargs):
        return len(args) + len(kwargs)

# Option 1
converter = c.apply_func(
    A.f, c.item("obj", "args"), c.item("obj", "kwargs")
).gen_converter(debug=True)
assert converter(data) == 3

# Option 2
converter = (
    c.naive(A)
    .apply_method("f", c.item("obj", "args"), c.item("obj", "kwargs"))
    .gen_converter(debug=True)
)
assert converter(data) == 3

# Option 3
converter = (
    c.naive(A.f)
    .apply(c.item("obj", "args"), c.item("obj", "kwargs"))
    .gen_converter(debug=True)
)
assert converter(data) == 3
