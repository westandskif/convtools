from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    # Single column explode
    assert list(
        Table.from_rows([{"a": 1, "b": [1, 2, 3]}, {"a": 10, "b": [4, 5, 6]}])
        .explode("b")
        .into_iter_rows(tuple, include_header=True)
    ) == [
        ("a", "b"),
        (1, 1),
        (1, 2),
        (1, 3),
        (10, 4),
        (10, 5),
        (10, 6),
    ]

    # Multi-column explode with zip_longest semantics
    # Shorter arrays are padded with None
    assert list(
        Table.from_rows(
            [{"a": 1, "b": [2, 3], "c": [10, 20, 30]}],
        )
        .explode("b", "c")
        .into_iter_rows(tuple, include_header=True)
    ) == [
        ("a", "b", "c"),
        (1, 2, 10),
        (1, 3, 20),
        (1, None, 30),
    ]
