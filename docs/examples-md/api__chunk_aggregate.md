===! "convtools"
    ```python
    from convtools import conversion as c
    
    converter = (
        c.chunk_by(size=3)
        .aggregate(
            {
                "x": c.ReduceFuncs.First(c.this),
                "y": c.ReduceFuncs.Last(c.this),
                "z": c.ReduceFuncs.Sum(c.this),
            }
        )
        .as_type(list)
        .gen_converter(debug=True)
    )
    assert converter([0, 1, 2, 3, 4, 5, 6, 7]) == [
        {"x": 0, "y": 2, "z": 3},
        {"x": 3, "y": 5, "z": 12},
        {"x": 6, "y": 7, "z": 13},
    ]
    ```

=== "debug stdout"
    ```python
    def aggregate_(_none, data_):
        agg_data__v0 = agg_data__v1 = agg_data__v2 = _none
    
        checksum_ = 0
        it_ = iter(data_)
        for row_ in it_:
            if agg_data__v0 is _none:
                checksum_ += 1
                agg_data__v0 = row_
                agg_data__v1 = row_
                agg_data__v2 = row_ or 0
            else:
                agg_data__v1 = row_
                agg_data__v2 += row_ or 0
            if checksum_ == 1:
                break
        for row_ in it_:
            agg_data__v1 = row_
            agg_data__v2 += row_ or 0
    
        return {
            "x": ((None if (agg_data__v0 is _none) else agg_data__v0)),
            "y": ((None if (agg_data__v1 is _none) else agg_data__v1)),
            "z": ((0 if (agg_data__v2 is _none) else agg_data__v2)),
        }
    
    def chunk_by(items_):
        items_ = iter(items_)
        try:
            item_ = next(items_)
        except StopIteration:
            return
        chunk_ = [item_]
        size_ = 1
        for item_ in items_:
            if size_ < 3:
                chunk_.append(item_)
                size_ = size_ + 1
            else:
                yield chunk_
                chunk_ = [item_]
                size_ = 1
        yield chunk_
    
    def converter(data_):
        global __none__
        _none = __none__
        try:
            return [aggregate_(_none, i) for i in chunk_by(data_)]
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

