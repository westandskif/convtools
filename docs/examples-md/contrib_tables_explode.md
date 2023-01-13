===! "convtools"
    ```python
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
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return (
                (
                    i["a"],
                    i["b"],
                )
                for i in data_
            )
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return (
                (
                    row_[0],
                    value_,
                )
                for row_ in data_
                for value_ in row_[1]
            )
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

