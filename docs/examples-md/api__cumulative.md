===! "convtools"
    ```python
    from convtools import conversion as c
    
    assert (
        c.iter(c.cumulative(c.this, c.this + c.PREV))
        .as_type(list)
        .execute([0, 1, 2, 3, 4], debug=True)
    ) == [0, 1, 3, 6, 10]
    ```

=== "debug stdout"
    ```python
    def pipe_(_labels, input_):
        result_ = (input_ + _labels["474b017de2b8412183fea44f9ef10fe3"]) if ("474b017de2b8412183fea44f9ef10fe3" in _labels) else input_
        _labels["474b017de2b8412183fea44f9ef10fe3"] = result_
        return result_
    
    def converter(data_):
        _labels = {}
        try:
            return [pipe_(_labels, i) for i in data_]
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

