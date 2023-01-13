===! "convtools"
    ```python
    from convtools import conversion as c
    
    args = ()
    
    c(
        {
            "-a": -c.item(0),
            "a + b": c.item(0) + c.item(1),
            "a - b": c.item(0) - c.item(1),
            "a * b": c.item(0) * c.item(1),
            "a / b": c.item(0) / c.item(1),
            "a // b": c.item(0) // c.item(1),
            "a % b": c.item(0) % c.item(1),
            "a == b": c.item(0) == c.item(1),
            "a >= b": c.item(0) >= c.item(1),
            "a <= b": c.item(0) <= c.item(1),
            "a < b": c.item(0) < c.item(1),
            "a > b": c.item(0) > c.item(1),
            "a or b": c.or_(c.item(0), c.item(1), *args),
            # "a or b": c.item(0).or_(c.item(1)),
            # "a or b": c.item(0) | c.item(1),
            "a and b": c.and_(c.item(0), c.item(1), *args),
            # "a and b": c.item(0).and_(c.item(1)),
            # "a and b": c.item(0) & c.item(1),
            "not a": ~c.item(0),
            "a is b": c.item(0).is_(c.item(1)),
            "a is not b": c.item(0).is_not(c.item(1)),
            "a in b": c.item(0).in_(c.item(1)),
            "a not in b": c.item(0).not_in(c.item(1)),
        }
    ).gen_converter(debug=True)
    ```

=== "debug stdout"
    ```python
    def converter(data_, *, __v=__naive_values__["__v"]):
        try:
            return {
                "-a": (-data_[0]),
                "a + b": (data_[0] + data_[1]),
                "a - b": (data_[0] - data_[1]),
                "a * b": (data_[0] * data_[1]),
                "a / b": (data_[0] / data_[1]),
                "a // b": (data_[0] // data_[1]),
                __v: (data_[0] % data_[1]),
                "a == b": (data_[0] == data_[1]),
                "a >= b": (data_[0] >= data_[1]),
                "a <= b": (data_[0] <= data_[1]),
                "a < b": (data_[0] < data_[1]),
                "a > b": (data_[0] > data_[1]),
                "a or b": (data_[0] or data_[1]),
                "a and b": (data_[0] and data_[1]),
                "not a": (not data_[0]),
                "a is b": (data_[0] is data_[1]),
                "a is not b": (data_[0] is not data_[1]),
                "a in b": (data_[0] in data_[1]),
                "a not in b": (data_[0] not in data_[1]),
            }
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

