from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    input_data = [["a", "b"], [1, 2], [3, 4]]
    converter = (
        c.this.pipe(
            lambda it: Table.from_rows(it, header=True).into_iter_rows(dict)
        )
        .as_type(list)
        .gen_converter()
    )
    assert converter(input_data) == [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
    ]
