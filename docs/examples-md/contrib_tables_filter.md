```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows([(1, -2), (2, -3)], header=["a", "b"])
        .filter(c.col("b") < -2)
        .into_iter_rows(dict)
    ) == [{"a": 2, "b": -3}]

```
