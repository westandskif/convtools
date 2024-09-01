/// tab | convtools
    new: true

```python
from convtools import conversion as c

c.item(1).gen_converter(debug=True)

with c.OptionsCtx() as options:
    options.debug = True
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

def _converter(data_):
    try:
        return data_[1]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

