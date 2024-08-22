/// tab | convtools
    new: true

```python
from convtools import conversion as c

input_data = [{"a": 1, "b": 2}]

converter = c.list_comp(
    c.tap(
        c.Mut.set_item("c", c.item("a") + c.item("b")),
        c.Mut.del_item("a"),
        c.Mut.custom(c.this.call_method("update", c.input_arg("data"))),
    )
).gen_converter(debug=True)

assert converter(input_data, data={"d": 4}) == [{"b": 2, "c": 3, "d": 4}]

```
///

/// tab | debug stdout
```python
def tap__(data, data_):
    data_["c"] = data_["a"] + data_["b"]
    data_.pop("a")
    data_.update(data)
    return data_

def _converter(data_, *, data):
    try:
        return [tap__(data, _i) for _i in data_]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

