/// tab | convtools
    new: true

```python
from convtools import conversion as c

# BY VALUES
assert c.chunk_by(c.item(0), c.item(1)).as_type(list).execute(
    [(0, 0), (0, 0), (0, 1), (1, 1), (1, 1)], debug=True
) == [[(0, 0), (0, 0)], [(0, 1)], [(1, 1), (1, 1)]]

# BY SIZE
assert c.chunk_by(size=3).as_type(list).execute(range(5), debug=True) == [
    [0, 1, 2],
    [3, 4],
]

# BY VALUE AND SIZE
assert c.chunk_by(c.this // 10, size=3).as_type(list).execute(
    [0, 1, 2, 3, 10, 19, 21, 24, 25], debug=True
) == [[0, 1, 2], [3], [10, 19], [21, 24, 25]]

# BY CONDITION
assert (
    c.chunk_by_condition(c.this - c.CHUNK.item(-1) < 10)
    .as_type(list)
    .execute([1, 5, 15, 20, 29, 40, 50, 58], debug=True)
) == [[1, 5], [15, 20, 29], [40], [50, 58]]

```
///

/// tab | debug stdout
```python
def _chunk_by(items_):
    items_ = iter(items_)
    try:
        item_ = next(items_)
    except StopIteration:
        return
    chunk_ = [item_]
    chunk_item_signature = (
        item_[0],
        item_[1],
    )
    for item_ in items_:
        new_item_signature = (
            item_[0],
            item_[1],
        )
        if chunk_item_signature == new_item_signature:
            chunk_.append(item_)
        else:
            yield chunk_
            chunk_ = [item_]
            chunk_item_signature = new_item_signature
    yield chunk_

def _converter(data_):
    try:
        return list(_chunk_by(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _chunk_by(items_):
    items_ = iter(items_)
    try:
        item_ = next(items_)
    except StopIteration:
        return
    chunk_ = [item_]
    size_ = 1
    for item_ in items_:
        if size_ < 3:
            chunk_.append(item_)
            size_ = size_ + 1
        else:
            yield chunk_
            chunk_ = [item_]
            size_ = 1
    yield chunk_

def _converter(data_):
    try:
        return list(_chunk_by(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _chunk_by(items_):
    items_ = iter(items_)
    try:
        item_ = next(items_)
    except StopIteration:
        return
    chunk_ = [item_]
    chunk_item_signature = item_ // 10
    size_ = 1
    for item_ in items_:
        new_item_signature = item_ // 10
        if chunk_item_signature == new_item_signature and size_ < 3:
            chunk_.append(item_)
            size_ = size_ + 1
        else:
            yield chunk_
            chunk_ = [item_]
            chunk_item_signature = new_item_signature
            size_ = 1
    yield chunk_

def _converter(data_):
    try:
        return list(_chunk_by(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _chunk_by_condition(items_):
    items_ = iter(items_)
    try:
        chunk_ = [next(items_)]
    except StopIteration:
        return

    for item_ in items_:
        if (item_ - chunk_[-1]) < 10:
            chunk_.append(item_)
        else:
            yield chunk_
            chunk_ = [item_]

    yield chunk_

def _converter(data_):
    try:
        return list(_chunk_by_condition(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

