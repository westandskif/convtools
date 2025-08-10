/// tab | convtools
    new: true

```python
from convtools import conversion as c

with c.OptionsCtx() as opts:
    opts.debug = True
    c.item(1).gen_converter()

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return data_[1]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

