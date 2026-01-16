/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = (
    c.zip_longest(
        c.item("a"),
        c.item("b"),
        fill_value="N/A",
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter({"a": [1, 2, 3], "b": [4, 5]}) == [
    (1, 4),
    (2, 5),
    (3, "N/A"),
]

```
///

/// tab | debug stdout
```python
def _converter(data_, *, __zip_longest=__naive_values__["__zip_longest"]):
    try:
        return list(__zip_longest(data_["a"], data_["b"], fillvalue="N/A"))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

