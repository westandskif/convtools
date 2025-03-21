/// tab | convtools
    new: true

```python
from datetime import datetime
from convtools import conversion as c

assert c.this.pipe(int).execute("123", debug=True) == 123

converter = (
    c.item("dt").pipe(datetime.strptime, "%m/%d/%Y").gen_converter(debug=True)
)
assert converter({"dt": "12/25/2000"}) == datetime(2000, 12, 25)

```
///

/// tab | debug stdout
```python
def _converter(data_):
    try:
        return int(data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_, *, __strptime=__naive_values__["__strptime"], __v=__naive_values__["__v"]):
    try:
        return __strptime(data_["dt"], __v)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

