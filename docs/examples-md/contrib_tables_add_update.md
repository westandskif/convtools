/// tab | convtools
    new: true

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
///

/// tab | debug stdout
```python
def converter(data_):
    try:
        return (
            {"a": i[0], "b": i[1], "c": abs(i[2])}
            for i in (
                (
                    i_i[0],
                    i_i[1],
                    (i_i[0] + i_i[1]),
                )
                for i_i in data_
            )
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

