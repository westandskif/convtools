===! "convtools"
    ```python
    from convtools import conversion as c
    
    converter = (
        c.iter(
            c.zip(
                a=c.repeat(c.item("a")),
                b=c.item("b"),
            )
        )
        .flatten()
        .as_type(list)
        .gen_converter(debug=True)
    )
    
    assert converter([{"a": 1, "b": [2, 3]}, {"a": 10, "b": [4, 5]}]) == [
        {"a": 1, "b": 2},
        {"a": 1, "b": 3},
        {"a": 10, "b": 4},
        {"a": 10, "b": 5},
    ]
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __from_iterable=__naive_values__["__from_iterable"], __repeat=__naive_values__["__repeat"]):
        try:
            return list(__from_iterable((({"a": i_i[0], "b": i_i[1]} for i_i in zip(__repeat(i["a"]), i["b"])) for i in data_)))
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

