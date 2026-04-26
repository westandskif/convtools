from io import StringIO

from convtools import conversion as c
from convtools.contrib.tables import Table

# READING JSONL (file with one JSON object per line)
output = StringIO(
    '{"a": 1, "b": 2}\n'
    '{"a": 3, "b": 4}\n'
)
assert list(Table.from_jsonl(output).into_iter_rows(dict)) == [
    {"a": 1, "b": 2},
    {"a": 3, "b": 4},
]

# READING JSONL WITH ARRAYS
arrays = StringIO("[1, 2, 3]\n[4, 5, 6]\n")
assert list(
    Table.from_jsonl(arrays, header=["x", "y", "z"]).into_iter_rows(dict)
) == [
    {"x": 1, "y": 2, "z": 3},
    {"x": 4, "y": 5, "z": 6},
]

# READING + TRANSFORMING + WRITING
output.seek(0)
transformed = StringIO()
result = (
    Table.from_jsonl(output)
    .update(c=c.col("a") + c.col("b"))
    .into_jsonl(transformed)
)
assert result is None

transformed.seek(0)
assert list(Table.from_jsonl(transformed).into_iter_rows(dict)) == [
    {"a": 1, "b": 2, "c": 3},
    {"a": 3, "b": 4, "c": 7},
]
