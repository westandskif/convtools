/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    input_data = [["a", "b"], [1, 2], [3, 4]]
    converter = (
        c.this.pipe(
            lambda it: Table.from_rows(it, header=True).into_iter_rows(dict)
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter(input_data) == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
    ]

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __lambda=__naive_values__["__lambda"]):
    try:
        return list(__lambda(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return (
            {
                "a": _i[0],
                "b": _i[1],
            }
            for _i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

