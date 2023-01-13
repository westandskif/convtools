from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    # NO HEADER PROVIDED
    assert list(
        Table.from_rows([(1, 2, 3), (2, 3, 4)]).into_iter_rows(dict)
    ) == [
        {"COLUMN_0": 1, "COLUMN_1": 2, "COLUMN_2": 3},
        {"COLUMN_0": 2, "COLUMN_1": 3, "COLUMN_2": 4},
    ]

    # HEADER IS PROVIDED
    assert list(
        Table.from_rows(
            [[1, 2, 3], [2, 3, 4]], header=["a", "b", "c"]
        ).into_iter_rows(dict)
    ) == [
        {"a": 1, "b": 2, "c": 3},
        {"a": 2, "b": 3, "c": 4},
    ]

    # INFERS HEADER ON DEMAND
    assert list(
        Table.from_rows(
            [["a", "b", "c"], [1, 2, 3], [2, 3, 4]], header=True
        ).into_iter_rows(dict)
    ) == [
        {"a": 1, "b": 2, "c": 3},
        {"a": 2, "b": 3, "c": 4},
    ]

    # INFERS HEADER AUTOMATICALLY BECAUSE THE FIRST ELEMENT IS A DICT
    assert list(
        Table.from_rows([{"a": 1, "b": 2}, {"a": 2, "b": 3}]).into_iter_rows(
            tuple, include_header=True
        )
    ) == [("a", "b"), (1, 2), (2, 3)]
