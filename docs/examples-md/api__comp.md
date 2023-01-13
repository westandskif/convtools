===! "convtools"
    ```python
    from convtools import conversion as c
    
    converter = c.iter(c.this + 1).gen_converter(debug=True)
    assert list(converter(range(3))) == [1, 2, 3]
    
    converter = c.item("objects").iter(c.this + 1).gen_converter(debug=True)
    assert list(converter({"objects": range(3)})) == [1, 2, 3]
    
    converter = c.list_comp(c.this + 1, where=c.this < 2).gen_converter(debug=True)
    assert converter(range(3)) == [1, 2]
    
    converter = c.dict_comp(c.this, c.this + 1).gen_converter(debug=True)
    assert converter(range(3)) == {0: 1, 1: 2, 2: 3}
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return ((i + 1) for i in data_)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return ((i + 1) for i in data_["objects"])
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return [(i + 1) for i in data_ if (i < 2)]
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return {i: (i + 1) for i in data_}
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

