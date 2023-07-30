===! "convtools"
    ```python
    from datetime import date, datetime
    from convtools import conversion as c
    
    # optimized
    converter = c.format_dt("%m/%d/%Y %H:%M %p").gen_converter(debug=True)
    assert converter(datetime(2023, 7, 27, 12, 13)) == "07/27/2023 12:13 PM"
    
    # falls back to even faster standard isoformat()
    converter = c.format_dt("%Y-%m-%d").gen_converter(debug=True)
    assert converter(date(2020, 12, 31)) == "2020-12-31"
    
    # falls back to standard strftime()
    converter = c.format_dt("%c").gen_converter(debug=True)
    assert converter(date(2020, 12, 31)) == "Thu Dec 31 00:00:00 2020"
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __datetime=__naive_values__["__datetime"], __v=__naive_values__["__v"]):
        try:
            is_datetime = isinstance(data_, __datetime)
            hour = data_.hour if is_datetime else 0
            return f"{data_.month:02}/{data_.day:02}/{data_.year:04} {hour:02}:{(data_.minute if is_datetime else 0):02} {__v[hour // 12]}"
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_, *, __datetime=__naive_values__["__datetime"]):
        try:
            return data_.date().isoformat() if isinstance(data_, __datetime) else data_.isoformat()
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_, *, __v=__naive_values__["__v"], __datetime=__naive_values__["__datetime"], __strftime=__naive_values__["__strftime"]):
        try:
            return __strftime(data_, __v)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

