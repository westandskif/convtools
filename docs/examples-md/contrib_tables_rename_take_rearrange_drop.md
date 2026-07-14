```python
from convtools.contrib.tables import Table

assert list(
    Table.from_rows([("A", "b", "c"), (1, 2, 3), (2, 3, 4)], header=True)
    .rename({"A": "a"})
    .drop("b")
    .take("c", ...)  # MAKE "c" COLUMN THE FIRST ONE
    .into_iter_rows(dict)
) == [{"c": 3, "a": 1}, {"c": 4, "a": 2}]

```
