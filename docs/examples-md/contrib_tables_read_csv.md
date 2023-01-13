===! "convtools"
    ```python
    from convtools import conversion as c
    from convtools.contrib.tables import Table
    
    with c.OptionsCtx() as options:
        options.debug = True
    
        # READING CSV
        assert list(
            Table
            .from_csv("tests/csvs/ab.csv", header=True)
            .into_iter_rows(dict)
            # .into_csv("output.csv")  # TO WRITE TO A FILE
        ) == [
            {"a": "1", "b": "2"},
            {"a": "2", "b": "3"},
        ]
    
        # READING TSV
        assert list(
            Table.from_csv(
                "tests/csvs/ac.csv",
                header=True,
                dialect=Table.csv_dialect(delimiter="\t"),
            ).into_iter_rows(dict)
        ) == [
            {"a": "2", "c": "4"},
            {"a": "1", "c": "3"},
        ]
    
        # READ TSV + SKIP EXISTING HEADER + REMAP COLUMNS
        assert list(
            Table.from_csv(
                "tests/csvs/ac.csv",
                header={"a": 1, "c": 0},
                skip_rows=1,
                dialect=Table.csv_dialect(delimiter="\t"),
            ).into_iter_rows(dict)
        ) == [
            {"a": "4", "c": "2"},
            {"a": "3", "c": "1"},
        ]
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return ({"a": i[0], "b": i[1]} for i in data_)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return ({"a": i[0], "c": i[1]} for i in data_)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return ({"a": i[1], "c": i[0]} for i in data_)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```
