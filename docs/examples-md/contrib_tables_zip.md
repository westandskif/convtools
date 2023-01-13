===! "convtools"
    ```python
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
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return (
                (
                    i[0][0],
                    i[0][1],
                    i[1][0],
                    i[1][1],
                )
                for i in data_
            )
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

