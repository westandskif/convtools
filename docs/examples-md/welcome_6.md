```python
from convtools import conversion as c

with c.OptionsCtx() as options:
    options.debug = True
    converter = c.list_comp(
        {"id": c.item("id"), "total": c.item("qty") * c.item("price")}
    ).gen_converter()

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
            for _i in data_
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise
```
