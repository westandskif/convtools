/// tab | convtools
    new: true

```python
from convtools import conversion as c

collection_1 = [
    {"id": 1, "name": "Nick"},
    {"id": 2, "name": "Joash"},
    {"id": 3, "name": "Bob"},
]
collection_2 = [
    {"ID": "3", "age": 17, "country": "GB"},
    {"ID": "2", "age": 21, "country": "US"},
    {"ID": "1", "age": 18, "country": "CA"},
]
input_data = (collection_1, collection_2)

conv = (
    c.join(
        c.item(0),
        c.item(1),
        c.and_(
            c.LEFT.item("id") == c.RIGHT.item("ID").as_type(int),
            c.RIGHT.item("age") >= 18,
        ),
        how="left",
    )
    .pipe(
        c.list_comp(
            {
                "id": c.item(0, "id"),
                "name": c.item(0, "name"),
                "age": c.item(1, "age", default=None),
                "country": c.item(1, "country", default=None),
            }
        )
    )
    .gen_converter(debug=True)
)

assert conv(input_data) == [
    {"id": 1, "name": "Nick", "age": 18, "country": "CA"},
    {"id": 2, "name": "Joash", "age": 21, "country": "US"},
    {"id": 3, "name": "Bob", "age": None, "country": None},
]

```
///

/// tab | debug stdout
```python
def aggregate_i(_none, data_, *, __v=__naive_values__["__v"]):
    agg_data_i_v0 = _none

    checksum_ = 0
    it_ = iter(data_)
    for row_i in it_:
        if row_i["age"] >= 18:
            if agg_data_i_v0 is _none:
                agg_data_i_v0 = defaultdict(list)
                agg_data_i_v0[int(row_i["ID"])].append(row_i)
                checksum_ += 1
            else:
                agg_data_i_v0[int(row_i["ID"])].append(row_i)
        if checksum_ == 1:
            globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
            break
    for row_i in it_:
        if row_i["age"] >= 18:
            agg_data_i_v0[int(row_i["ID"])].append(row_i)

    return __v if (agg_data_i_v0 is _none) else (setattr(agg_data_i_v0, "default_factory", None) or agg_data_i_v0)

def join_(left_, right_, _none):
    hash_to_right_items = aggregate_i(_none, right_)
    del right_
    for left_item in left_:
        left_key = left_item["id"]
        right_items = iter(((hash_to_right_items[left_key] if (left_key in hash_to_right_items) else ())))
        right_item = next(right_items, _none)
        if right_item is _none:
            yield left_item, None
        else:
            yield left_item, right_item
            for right_item in right_items:
                yield left_item, right_item

def _converter(data_, *, __get_item_deep_default_simple=__naive_values__["__get_item_deep_default_simple"]):
    global __none__
    _none = __none__
    try:
        return [
            {
                "id": _i_e[0]["id"],
                "name": _i_e[0]["name"],
                "age": __get_item_deep_default_simple(_i_e, 1, "age", None),
                "country": __get_item_deep_default_simple(_i_e, 1, "country", None),
            }
            for _i_e in join_(data_[0], data_[1], _none)
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

