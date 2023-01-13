from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .zip(
            Table.from_rows([(10, 3), (20, 4)], ["a", "c"]),
            fill_value=0,
        )
        .into_iter_rows(tuple, include_header=True)
    ) == [("a", "b", "a", "c"), (1, 2, 10, 3), (2, 3, 20, 4)]
