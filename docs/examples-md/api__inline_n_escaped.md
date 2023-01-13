===! "convtools"
    ```python
    from convtools import conversion as c
    
    assert c.escaped_string("1 + 1").execute(None, debug=True) == 2
    assert c.inline_expr("1 + 1").execute(None, debug=True) == 2
    
    assert (
        c.inline_expr("{} + {}").pass_args(c.this, 1).execute(10, debug=True) == 11
    )
    assert (
        c.inline_expr("{a} + {b}").pass_args(a=c.this, b=1).execute(10, debug=True)
        == 11
    )
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return 1 + 1
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return 1 + 1
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return data_ + 1
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return data_ + 1
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

