```python
from convtools import conversion as c

converter = (
    c.iter(
        c.try_(c.item(0) / c.item(1))
        .except_(ZeroDivisionError, value=c.this, re_raise_if=c.item(0) == 0)
        .except_(TypeError, None)
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter([(1, 2), (3, 0), (4, "abc")]) == [0.5, (3, 0), None]

```
