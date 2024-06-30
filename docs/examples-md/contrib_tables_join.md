/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    # JOIN ON COLUMN NAMES
    assert list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            how="inner",
            on=["a"],
        )
        .into_iter_rows(dict)
    ) == [
        {"a": 1, "b": 2, "c": 3},
        {"a": 2, "b": 3, "c": 4},
    ]

    # JOIN ON CONDITION
    assert list(
        Table.from_rows([(1, 2), (2, 30)], ["a", "b"])
        .join(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            how="full",
            on=c.and_(
                c.LEFT.col("a") == c.RIGHT.col("a"),
                c.LEFT.col("b") < c.RIGHT.col("c"),
            ),
        )
        .into_iter_rows(dict)
    ) == [
        {"a_LEFT": 1, "b": 2, "a_RIGHT": 1, "c": 3},
        {"a_LEFT": 2, "b": 30, "a_RIGHT": None, "c": None},
        {"a_LEFT": None, "b": None, "a_RIGHT": 2, "c": 4},
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
        if agg_data_i_v0 is _none:
            checksum_ += 1
            agg_data_i_v0 = defaultdict(list)
            agg_data_i_v0[row_i[0]].append(row_i)
        else:
            agg_data_i_v0[row_i[0]].append(row_i)
        if checksum_ == 1:
            globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
            break
    for row_i in it_:
        agg_data_i_v0[row_i[0]].append(row_i)

    return __v if (agg_data_i_v0 is _none) else (setattr(agg_data_i_v0, "default_factory", None) or agg_data_i_v0)

def join_(left_, right_, _none):
    hash_to_right_items = aggregate_i(_none, right_)
    del right_
    for left_item in left_:
        left_key = left_item[0]
        right_items = hash_to_right_items[left_key] if (left_key in hash_to_right_items) else ()
        for right_item in right_items:
            yield left_item, right_item

def converter(data_, *, right):
    global __none__
    _none = __none__
    try:
        return join_(data_, right, _none)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def converter(data_):
    try:
        return ({"a": i[0][0], "b": i[0][1], "c": i[1][1]} for i in data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def aggregate_e(_none, data_, *, __v=__naive_values__["__v"]):
    agg_data_e_v0 = _none

    checksum_ = 0
    it_ = iter(data_)
    for row_e in it_:
        if agg_data_e_v0 is _none:
            checksum_ += 1
            agg_data_e_v0 = defaultdict(list)
            agg_data_e_v0[row_e[0]].append(row_e)
        else:
            agg_data_e_v0[row_e[0]].append(row_e)
        if checksum_ == 1:
            globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
            break
    for row_e in it_:
        agg_data_e_v0[row_e[0]].append(row_e)

    return __v if (agg_data_e_v0 is _none) else (setattr(agg_data_e_v0, "default_factory", None) or agg_data_e_v0)

def join_(left_, right_, _none):
    yielded_right_ids = set()
    hash_to_right_items = aggregate_e(_none, right_)
    del right_
    for left_item in left_:
        left_key = left_item[0]
        right_items = iter((((i for i in hash_to_right_items[left_key] if (((left_item[1] < i[1])))) if (left_key in hash_to_right_items) else ())))
        right_item = next(right_items, _none)
        if right_item is _none:
            yield left_item, None
        else:
            yielded_right_ids.add(id(right_item))
            yield left_item, right_item
            for right_item in right_items:
                yielded_right_ids.add(id(right_item))
                yield left_item, right_item
    yield from (
        (None, right_item) for right_item in (item for items in hash_to_right_items.values() for item in items) if id(right_item) not in yielded_right_ids
    )

def converter(data_, *, right):
    global __none__
    _none = __none__
    try:
        return join_(data_, right, _none)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def converter(data_):
    try:
        return (
            {
                "a_LEFT": ((None if (i[0] is None) else i[0][0])),
                "b": ((None if (i[0] is None) else i[0][1])),
                "a_RIGHT": ((None if (i[1] is None) else i[1][0])),
                "c": ((None if (i[1] is None) else i[1][1])),
            }
            for i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

