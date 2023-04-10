===! "convtools"
    ```python
    from datetime import date, datetime
    from convtools import conversion as c
    
    # SINGLE FORMAT
    converter = c.date_parse("%m/%d/%Y").gen_converter(debug=True)
    assert converter("12/31/2020") == date(2020, 12, 31)
    
    # MULTIPLE FORMATS
    converter = (
        c.iter(c.date_parse("%m/%d/%Y", "%Y-%m-%d"))
        .as_type(list)
        .gen_converter(debug=True)
    )
    assert converter(["12/31/2020", "2021-01-01"]) == [
        date(2020, 12, 31),
        date(2021, 1, 1),
    ]
    
    # SAME FOR DATETIMES, BUT LET'S USE A METHOD
    converter = (
        c.item("dt").datetime_parse("%m/%d/%Y %H:%M").gen_converter(debug=True)
    )
    assert converter({"dt": "12/31/2020 15:40"}) == datetime(2020, 12, 31, 15, 40)
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __v=__naive_values__["__v"], __strptime=__naive_values__["__strptime"]):
        try:
            return __strptime(data_, __v).date()
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(
        data_, *, __date_parse=__naive_values__["__date_parse"], __v=__naive_values__["__v"], __v_e=__naive_values__["__v_e"], __v_i=__naive_values__["__v_i"]
    ):
        try:
            return [__date_parse(i, __v, __v_i, __v_e) for i in data_]
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

