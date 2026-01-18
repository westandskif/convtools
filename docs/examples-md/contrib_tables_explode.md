/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    # Single column explode
    assert list(
        Table.from_rows([{"a": 1, "b": [1, 2, 3]}, {"a": 10, "b": [4, 5, 6]}])
        .explode("b")
        .into_iter_rows(tuple, include_header=True)
    ) == [
        ("a", "b"),
        (1, 1),
        (1, 2),
        (1, 3),
        (10, 4),
        (10, 5),
        (10, 6),
    ]

    # Multi-column explode with zip_longest semantics
    # Shorter arrays are padded with None
    assert list(
        Table.from_rows(
            [{"a": 1, "b": [2, 3], "c": [10, 20, 30]}],
        )
        .explode("b", "c")
        .into_iter_rows(tuple, include_header=True)
    ) == [
        ("a", "b", "c"),
        (1, 2, 10),
        (1, 3, 20),
        (1, None, 30),
    ]

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return (
            (
                _i["a"],
                _i["b"],
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
                row_[0],
                value_,
            )
            for row_ in data_
            for value_ in row_[1]
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (
            (
                _i["a"],
                _i["b"],
                _i["c"],
            )
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __zip_longest=__naive_values__["__zip_longest"]):
    try:
        return (
            (
                row_[0],
                values_[0],
                values_[1],
            )
            for row_ in data_
            for values_ in __zip_longest(row_[1], row_[2])
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

