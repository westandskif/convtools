===! "convtools"
    ```python
    from convtools import conversion as c
    
    converter = c(
        {
            "a": c.item(0),
            "b": c.optional(c.item(1), skip_if=c.item(1) < 10),
            "c": c.optional(c.item(0) + c.item(1), keep_if=c.item(0)),
            "d": c.optional(c.item(0), skip_value=1),
        }
    ).gen_converter(debug=True)
    
    assert converter((1, 2)) == {"a": 1, "c": 3}
    ```

=== "debug stdout"
    ```python
    def optional_items_generator(data_):
        yield (
            "a",
            data_[0],
        )
        if not (data_[1] < 10):
            yield (
                "b",
                data_[1],
            )
        if data_[0]:
            yield (
                "c",
                (data_[0] + data_[1]),
            )
        if data_[0] != 1:
            yield (
                "d",
                data_[0],
            )
    
    def converter(data_):
        try:
            return dict(optional_items_generator(data_))
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

