from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    # JOIN ON COLUMN NAMES
    assert list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            how="inner",
            on=["a"],
        )
        .into_iter_rows(dict)
    ) == [
        {"a": 1, "b": 2, "c": 3},
        {"a": 2, "b": 3, "c": 4},
    ]

    # JOIN ON CONDITION
    assert list(
        Table.from_rows([(1, 2), (2, 30)], ["a", "b"])
        .join(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            how="full",
            on=c.and_(
                c.LEFT.col("a") == c.RIGHT.col("a"),
                c.LEFT.col("b") < c.RIGHT.col("c"),
            ),
        )
        .into_iter_rows(dict)
    ) == [
        {"a_LEFT": 1, "b": 2, "a_RIGHT": 1, "c": 3},
        {"a_LEFT": 2, "b": 30, "a_RIGHT": None, "c": None},
        {"a_LEFT": None, "b": None, "a_RIGHT": 2, "c": 4},
    ]
