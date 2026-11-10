```python
from convtools import conversion as c

converter = c(
    {
        "-a": -c.item(0),
        "a + b": c.item(0) + c.item(1),
        "a - b": c.item(0) - c.item(1),
        "a * b": c.item(0) * c.item(1),
        "a ** b": c.item(0) ** c.item(1),
        "a / b": c.item(0) / c.item(1),
        "a // b": c.item(0) // c.item(1),
        "a % b": c.item(0) % c.item(1),
        "a == b": c.item(0) == c.item(1),
        "a != b": c.item(0) != c.item(1),
        "eq": c.eq(c.item(0), c.item(1), 6),
        "a >= b": c.item(0) >= c.item(1),
        "a <= b": c.item(0) <= c.item(1),
        "a < b": c.item(0) < c.item(1),
        "a > b": c.item(0) > c.item(1),
        # `|`, `&`, `~` compile to Python's logical `or`, `and`, `not` (not bitwise)
        "or": c.or_(c.item(0), c.item(1)),
        "or_pipe": c.item(0) | c.item(1),
        "and": c.and_(c.item(0), c.item(1)),
        "and_amp": c.item(0) & c.item(1),
        "not": c.not_(c.item(0)),
        "not_tilde": ~c.item(0),
        "a is None": c.item(0).is_(None),
        "a is not None": c.item(0).is_not(None),
        "a in b": c.item(0).in_(c.item(2)),
        "a not in b": c.item(0).not_in(c.item(2)),
    }
).gen_converter()

assert converter((6, 2, [2, 6])) == {
    "-a": -6,
    "a + b": 8,
    "a - b": 4,
    "a * b": 12,
    "a ** b": 36,
    "a / b": 3.0,
    "a // b": 3,
    "a % b": 0,
    "a == b": False,
    "a != b": True,
    "eq": False,
    "a >= b": True,
    "a <= b": False,
    "a < b": False,
    "a > b": True,
    "or": 6,
    "or_pipe": 6,  # `6 or 2` -> 6 (logical `or`, not `6 | 2`)
    "and": 2,
    "and_amp": 2,  # `6 and 2` -> 2 (logical `and`, not `6 & 2`)
    "not": False,
    "not_tilde": False,  # `not 6` -> False (logical `not`, not `~6`)
    "a is None": False,
    "a is not None": True,
    "a in b": True,
    "a not in b": False,
}

```
