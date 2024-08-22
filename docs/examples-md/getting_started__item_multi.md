/// tab | convtools
    new: true

```python
from convtools import conversion as c

converter = c.item(1, "value").gen_converter(debug=True)

assert converter([{"value": 10}, {"value": 20}]) == 20

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return data_[1]["value"]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

