/// tab | convtools
    new: true

```python
from convtools import conversion as c

input_data = [{"StoreID": " 123", "Quantity": "123"}]

# define a conversion (sometimes you may want to do this dynamically)
#  takes iterable and returns iterable of dicts, stopping before the first
#  one with quantity >= 1000, splitting into chunks of size = 1000
conversion = (
    c.iter(
        {
            "id": c.item("StoreID").call_method("strip"),
            "quantity": c.item("Quantity").as_type(int),
        }
    )
    .take_while(c.item("quantity") < 1000)
    .pipe(c.chunk_by(c.item("id"), size=1000))
    .as_type(list)
)

# compile the conversion into an ad hoc function and run it
converter = conversion.gen_converter(debug=True)

# run it as any function
assert converter(input_data) == [[{"id": "123", "quantity": 123}]]

# OR in case of a one-shot use, skip the gen_converter part
conversion.execute(input_data)

```
///

/// tab | debug stdout
```python
def take_while_q(it_q):
    for item_q in it_q:
        if item_q["quantity"] < 1000:
            yield item_q
        else:
            break

def _chunk_by(items_):
    items_ = iter(items_)
    try:
        item_ = next(items_)
    except StopIteration:
        return
    chunk_ = [item_]
    chunk_item_signature = item_["id"]
    size_ = 1
    for item_ in items_:
        new_item_signature = item_["id"]
        if chunk_item_signature == new_item_signature and size_ < 1000:
            chunk_.append(item_)
            size_ = size_ + 1
        else:
            yield chunk_
            chunk_ = [item_]
            chunk_item_signature = new_item_signature
            size_ = 1
    yield chunk_

def pipe_i_e(input_):
    return list(_chunk_by(input_))

def pipe_(input_):
    return pipe_i_e(take_while_q(input_))

def _converter(data_):
    try:
        return pipe_(
            (
                {
                    "id": _i["StoreID"].strip(),
                    "quantity": int(_i["Quantity"]),
                }
                for _i in data_
            )
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

