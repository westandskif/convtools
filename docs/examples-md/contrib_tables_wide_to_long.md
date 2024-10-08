/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows(
            [{"name": "John", "height": 200, "age": 30, "mood": "good"}]
        )
        .wide_to_long(
            col_for_names="metric", col_for_values="value", keep_cols=("name",)
        )
        .into_iter_rows(dict)
    ) == [
        {"name": "John", "metric": "height", "value": 200},
        {"name": "John", "metric": "age", "value": 30},
        {"name": "John", "metric": "mood", "value": "good"},
    ]

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return (
            (
                _i["name"],
                _i["height"],
                _i["age"],
                _i["mood"],
            )
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (
            new_row
            for row_ in data_
            for new_row in (
                (
                    row_[0],
                    "height",
                    row_[1],
                ),
                (
                    row_[0],
                    "age",
                    row_[2],
                ),
                (
                    row_[0],
                    "mood",
                    row_[3],
                ),
            )
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (
            {
                "name": _i[0],
                "metric": _i[1],
                "value": _i[2],
            }
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

