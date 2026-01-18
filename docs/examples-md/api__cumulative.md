/// tab | convtools
    new: true

```python
from convtools import conversion as c

assert (
    c.iter(c.cumulative(c.this, c.this + c.PREV))
    .as_type(list)
    .execute([0, 1, 2, 3, 4], debug=True)
) == [0, 1, 3, 6, 10]

```
///

/// tab | debug stdout
```python
def pipe_(_labels, input_):
    result_ = (input_ + _labels["2fcdbf26f0ce490fb4f4587a06a3f66f"]) if ("2fcdbf26f0ce490fb4f4587a06a3f66f" in _labels) else input_
    _labels["2fcdbf26f0ce490fb4f4587a06a3f66f"] = result_
    return result_

def _converter(data_):
    _labels = {}
    try:
        return [pipe_(_labels, _i) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

