```python
from convtools import conversion as c

# 1. Per-converter debug flag
c.item("orders").pipe(
    c.list_comp({"id": c.item("id"), "total": c.item("qty") * c.item("price")})
).gen_converter(debug=True)

# 2. Scoped debug context
with c.OptionsCtx() as options:
    options.debug = True
    c.item(1).gen_converter()

```

Printed output:

```python
def _converter(data_):
    try:
        return [
            {
                "id": _i["id"],
                "total": (_i["qty"] * _i["price"]),
            }
            for _i in data_["orders"]
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _converter(data_):
    try:
        return data_[(1)]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise
```
