===! "convtools"
    ```python
    from datetime import datetime
    from convtools import conversion as c
    
    # No. 1
    converter = c.call_func(datetime.strptime, c.this, "%m/%d/%Y").gen_converter(
        debug=True
    )
    
    assert converter("12/31/2000") == datetime(2000, 12, 31)
    
    # No. 2
    converter = (
        c.naive(datetime)
        .call_method("strptime", c.this, "%m/%d/%Y")
        .gen_converter(debug=True)
    )
    
    assert converter("12/31/2000") == datetime(2000, 12, 31)
    
    # No. 3
    assert (
        c.naive(datetime.strptime)
        .call(c.this, "%m/%d/%Y")
        .execute("12/31/2000", debug=True)
    ) == datetime(2000, 12, 31)
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __strptime=__naive_values__["__strptime"], __v=__naive_values__["__v"]):
        try:
            return __strptime(data_, __v)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_, *, __datetime=__naive_values__["__datetime"], __v=__naive_values__["__v"]):
        try:
            return __datetime.strptime(data_, __v)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_, *, __strptime=__naive_values__["__strptime"], __v=__naive_values__["__v"]):
        try:
            return __strptime(data_, __v)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

