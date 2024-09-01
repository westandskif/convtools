/// tab | convtools
    new: true

```python
from convtools import conversion as c

# SIMPLE UNIQUE
converter = c.iter_unique().as_type(list).gen_converter(debug=True)
assert converter([0, 0, 0, 1, 1, 2]) == [0, 1, 2]

# UNIQUE BY MODULO OF 3
converter = (
    c.iter_unique(by_=c.this % 3).as_type(list).gen_converter(debug=True)
)
assert converter(range(10)) == [0, 1, 2]

# UNIQUE BY ID, YIELD NAMES
converter = (
    c.item("data")
    .iter_unique(c.item("name"), by_=c.item("id"))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(
    {
        "data": [
            {"name": "foo", "id": 1},
            {"name": "foo", "id": 1},
            {"name": "bar", "id": 1},
            {"name": "def", "id": 2},
        ]
    }
) == ["foo", "def"]

```
///

/// tab | debug stdout
```python
def _iter_unique(data_):
    s_ = set()
    s_add = s_.add
    for item_ in data_:
        if item_ not in s_:
            s_add(item_)
            yield item_

def _converter(data_):
    try:
        return list(_iter_unique(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _iter_unique(data_):
    s_ = set()
    s_add = s_.add
    for item_ in data_:
        by_ = item_ % 3
        if by_ not in s_:
            s_add(by_)
            yield item_

def _converter(data_):
    try:
        return list(_iter_unique(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _iter_unique(data_):
    s_ = set()
    s_add = s_.add
    for item_ in data_:
        by_ = item_["id"]
        if by_ not in s_:
            s_add(by_)
            yield item_["name"]

def _converter(data_):
    try:
        return list(_iter_unique(data_["data"]))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

