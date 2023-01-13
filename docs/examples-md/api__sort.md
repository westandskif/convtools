===! "convtools"
    ```python
    from convtools import conversion as c
    
    converter = c.this.sort(key=lambda x: x, reverse=True).gen_converter(
        debug=True
    )
    assert list(converter(range(3))) == [2, 1, 0]
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __lambda=__naive_values__["__lambda"]):
        try:
            return sorted(data_, key=__lambda, reverse=True)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

