/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .chain(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            fill_value=0,
        )
        .into_iter_rows(dict)
    ) == [
        {"a": 1, "b": 2, "c": 0},
        {"a": 2, "b": 3, "c": 0},
        {"a": 1, "b": 0, "c": 3},
        {"a": 2, "b": 0, "c": 4},
    ]

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return (
            (
                _i[0],
                _i[1],
                0,
            )
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (
            (
                _i[0],
                0,
                _i[1],
            )
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (
            {
                "a": _i[0],
                "b": _i[1],
                "c": _i[2],
            }
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

