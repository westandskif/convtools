from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

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
