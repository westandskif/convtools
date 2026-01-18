/// tab | convtools
    new: true

```python
from convtools.contrib.tables import Table

# READING JSONL (file with one JSON object per line)
# file content:
#   {"a": 1, "b": 2}
#   {"a": 3, "b": 4}
Table.from_rows([{"a": 1, "b": 2}, {"a": 3, "b": 4}]).into_jsonl(
    "output.jsonl"
)
assert list(
    Table.from_jsonl("output.jsonl").into_iter_rows(dict)
) == [
    {"a": 1, "b": 2},
    {"a": 3, "b": 4},
]

# READING JSONL WITH ARRAYS
# file content:
#   [1, 2, 3]
#   [4, 5, 6]
with open("arrays.jsonl", "w") as f:
    f.write("[1, 2, 3]\n[4, 5, 6]\n")

assert list(
    Table.from_jsonl("arrays.jsonl", header=["x", "y", "z"]).into_iter_rows(
        dict
    )
) == [
    {"x": 1, "y": 2, "z": 3},
    {"x": 4, "y": 5, "z": 6},
]

# READING + TRANSFORMING + WRITING
list(
    Table.from_jsonl("output.jsonl")
    .update(c=c.col("a") + c.col("b"))
    .into_jsonl("transformed.jsonl")
)
```
///

