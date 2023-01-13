from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows([("A", "b", "c"), (1, 2, 3), (2, 3, 4)], header=True)
        .rename({"A": "a"})
        .drop("b")
        .take("c", ...)  # MAKE "c" COLUMN THE FIRST ONE
        .into_iter_rows(dict)
    ) == [{"c": 3, "a": 1}, {"c": 4, "a": 2}]
