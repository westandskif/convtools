/// tab | convtools
    new: true

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
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return (
            {
                "a": _i[0],
                "b": _i[1],
            }
            for _i in data_
            if (((_i[1] < -2)))
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

