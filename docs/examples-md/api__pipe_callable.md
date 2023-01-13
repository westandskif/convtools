===! "convtools"
    ```python
    from datetime import datetime
    from convtools import conversion as c
    
    assert c.this.pipe(int).execute("123", debug=True) == 123
    
    converter = (
        c.item("dt").pipe(datetime.strptime, "%m/%d/%Y").gen_converter(debug=True)
    )
    assert converter({"dt": "12/25/2000"}) == datetime(2000, 12, 25)
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return int(data_)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_, *, __v=__naive_values__["__v"], __strptime=__naive_values__["__strptime"]):
        try:
            return __strptime(data_["dt"], __v)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

