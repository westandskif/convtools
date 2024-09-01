/// tab | convtools
    new: true

```python
from convtools import conversion as c

data = [(i % 2, i) for i in range(10)]

assert (
    c.unordered_chunk_by(c.item(0)).as_type(list).execute(data, debug=True)
) == [
    [(0, 0), (0, 2), (0, 4), (0, 6), (0, 8)],
    [(1, 1), (1, 3), (1, 5), (1, 7), (1, 9)],
]

assert (
    c.unordered_chunk_by(c.item(0), size=4)
    .as_type(list)
    .execute(data, debug=True)
) == [
    [(0, 0), (0, 2), (0, 4), (0, 6)],
    [(1, 1), (1, 3), (1, 5), (1, 7)],
    [(0, 8)],
    [(1, 9)],
]

assert (
    c.unordered_chunk_by(
        c.item(0),
        size=4,
        max_items_in_memory=6,
        portion_to_pop_on_max_memory_hit=0.5,
    )
    .as_type(list)
    .execute(data, debug=True)
) == [
    [(0, 0), (0, 2), (0, 4)],
    [(1, 1), (1, 3), (1, 5), (1, 7)],
    [(0, 6), (0, 8)],
    [(1, 9)],
]

```
///

/// tab | debug stdout
```python
def _unordered_chunk_by(items_):
    key_to_chunk = defaultdict(list)
    for item_ in items_:
        key_to_chunk[item_[0]].append(item_)
    yield from key_to_chunk.values()

def _converter(data_):
    try:
        return list(_unordered_chunk_by(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _unordered_chunk_by(items_):
    key_to_chunk = defaultdict(list)
    for item_ in items_:
        key_ = item_[0]
        chunk_ = key_to_chunk[key_]
        chunk_.append(item_)
        if len(chunk_) == 4:
            del key_to_chunk[key_]
            yield chunk_
            continue
    yield from key_to_chunk.values()

def _converter(data_):
    try:
        return list(_unordered_chunk_by(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def _unordered_chunk_by(items_):
    key_to_chunk = defaultdict(list)
    items_in_memory = 0
    for item_ in items_:
        key_ = item_[0]
        chunk_ = key_to_chunk[key_]
        chunk_.append(item_)
        items_in_memory += 1
        if len(chunk_) == 4:
            del key_to_chunk[key_]
            items_in_memory -= 4
            yield chunk_
            continue
        if items_in_memory == 6:
            while key_to_chunk and items_in_memory > 3.0:
                key, chunk_ = next(iter(key_to_chunk.items()))
                items_in_memory -= len(chunk_)
                del key_to_chunk[key]
                yield chunk_
    yield from key_to_chunk.values()

def _converter(data_):
    try:
        return list(_unordered_chunk_by(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
{ data-search-exclude }
///

