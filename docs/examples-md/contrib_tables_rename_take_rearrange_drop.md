/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows([("A", "b", "c"), (1, 2, 3), (2, 3, 4)], header=True)
        .rename({"A": "a"})
        .drop("b")
        .take("c", ...)  # MAKE "c" COLUMN THE FIRST ONE
        .into_iter_rows(dict)
    ) == [{"c": 3, "a": 1}, {"c": 4, "a": 2}]

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return (
            {
                "c": _i[2],
                "a": _i[0],
            }
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

