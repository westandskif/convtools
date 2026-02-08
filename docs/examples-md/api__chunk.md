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
