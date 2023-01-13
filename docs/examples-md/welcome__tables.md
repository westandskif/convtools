===! "convtools"
    ```python
    from convtools.contrib.tables import Table
    from convtools import conversion as c
    
    with c.OptionsCtx() as options:
        options.debug = True
    
        # reads Iterable of rows
        iterable_of_rows = (
            Table.from_rows([(0, -1), (1, 2)], header=["a", "b"]).join(
                Table
                # reads tab-separated CSV file
                .from_csv(
                    "tests/csvs/ac.csv",
                    header=True,
                    dialect=Table.csv_dialect(delimiter="\t"),
                )
                # transform column values
                .update(
                    a=c.col("a").as_type(float),
                    c=c.col("c").as_type(int),
                )
                # filter rows by condition
                .filter(c.col("c") >= 0),
                # joins on column "a" values
                on=["a"],
                how="inner",
            )
            # rearrange columns
            .take(..., "a")
            # this is a generator to consume (tuple, list are supported too)
            .into_iter_rows(dict)
        )
    
        assert list(iterable_of_rows) == [{"b": 2, "c": 3, "a": 1}]
    ```

=== "debug stdout"
    ```python
    def converter(data_):
        try:
            return (
                i
                for i in (
                    (
                        float(i_i[0]),
                        int(i_i[1]),
                    )
                    for i_i in data_
                )
                if (i[1] >= 0)
            )
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def aggregate_e(_none, data_, *, __v=__naive_values__["__v"]):
        agg_data_e_v0 = _none
        checksum_ = 0
    
        it_ = iter(data_)
        for row_e in it_:
            if agg_data_e_v0 is _none:
                agg_data_e_v0 = _d = defaultdict(list)
                _d[row_e[0]].append(row_e)
                globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
                break
    
        for row_e in it_:
            agg_data_e_v0[row_e[0]].append(row_e)
    
        return __v if (agg_data_e_v0 is _none) else (setattr(agg_data_e_v0, "default_factory", None) or agg_data_e_v0)
    
    def join_(left_, right_, _none):
        hash_to_right_items = aggregate_e(_none, right_)
        del right_
        for left_item in left_:
            left_key = left_item[0]
            right_items = hash_to_right_items[left_key] if (left_key in hash_to_right_items) else ()
            for right_item in right_items:
                yield left_item, right_item
    
    def converter(data_, *, right):
        global __none__
        _none = __none__
        try:
            return join_(data_, right, _none)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    def converter(data_):
        try:
            return ({"b": i[0][1], "c": i[1][1], "a": i[0][0]} for i in data_)
        except __exceptions_to_dump_sources:
            __convtools__code_storage.dump_sources()
            raise
    
    ```

