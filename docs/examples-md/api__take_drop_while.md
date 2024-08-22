/// tab | convtools
    new: true

```python
from itertools import count
from convtools import conversion as c

converter = c.take_while(c.this < 3).as_type(list).gen_converter(debug=True)
assert converter(count()) == [0, 1, 2]


converter = c.drop_while(c.this < 3).as_type(list).gen_converter(debug=True)
assert converter(range(5)) == [3, 4]

```
///

/// tab | debug stdout
```python
def take_while_(it_):
    for item_ in it_:
        if item_ < 3:
            yield item_
        else:
            break

def _converter(data_):
    try:
        return list(take_while_(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def drop_while_(it_, *, __chain=__naive_values__["__chain"]):
    it_ = iter(it_)
    for item_ in it_:
        if not ((item_ < 3)):
            break
    else:
        return ()
    return __chain((item_,), it_)

def _converter(data_):
    try:
        return list(drop_while_(data_))
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

