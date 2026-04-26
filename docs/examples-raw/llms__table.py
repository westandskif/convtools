from convtools import conversion as c
from convtools.contrib.tables import Table


rows = [{"name": "Ada", "score": "10"}]
result = (
    Table.from_rows(rows)
    .update(score=c.col("score").as_type(int))
    .into_iter_rows(dict)
)
assert list(result) == [{"name": "Ada", "score": 10}]
