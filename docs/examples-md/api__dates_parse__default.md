===! "convtools"
    ```python
    from datetime import date, datetime
    from convtools import conversion as c
    
    # SIMPLE DEFAULT
    converter = c.date_parse("%m/%d/%Y", default=None).gen_converter(debug=True)
    assert converter("some str") is None
    
    # DEFAULT AS CONVERSION
    converter = c.date_parse(
        "%m/%d/%Y", default=c.call_func(date.today)
    ).gen_converter(debug=True)
    assert converter("some str") == date.today()
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __v=__naive_values__["__v"], __v_i=__naive_values__["__v_i"], __date_parse=__naive_values__["__date_parse"]):
        try:
            return __date_parse(data_, __v, __v_i, None)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(
        data_, *, __v=__naive_values__["__v"], __today=__naive_values__["__today"], __v_e=__naive_values__["__v_e"], __date_parse=__naive_values__["__date_parse"]
    ):
        try:
            return __date_parse(data_, __v, __v_e, None) or __today()
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

