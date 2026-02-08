```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows([(1, -2), (2, -3)], ["a", "b"])
        .update(c=c.col("a") + c.col("b"))  # ADDING NEW COLUMN: "c"
        .update(c=c.call_func(abs, c.col("c")))  # UPDATING NEW COLUMN: "c"
        .into_iter_rows(dict)
    ) == [{"a": 1, "b": -2, "c": 1}, {"a": 2, "b": -3, "c": 1}]

```
