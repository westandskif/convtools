/// tab | convtools
    new: true

```python
from convtools import conversion as c

assert (
    c.iter(
        c.cumulative_reset("abc")
        .iter(c.cumulative(c.this, c.this + c.PREV, label_name="abc"))
        .as_type(list)
    )
    .as_type(list)
    .execute([[0, 1, 2], [3, 4]], debug=True)
) == [[0, 1, 3], [3, 7]]

```
///

/// tab | debug stdout
```python
def pipe_(_labels, input_):
    result_ = (input_ + _labels["abc"]) if ("abc" in _labels) else input_
    _labels["abc"] = result_
    return result_

def _converter(data_):
    _labels = {}
    try:
        return [[pipe_(_labels, _i_i) for _i_i in (_labels.pop("abc", None), _i)[1]] for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

