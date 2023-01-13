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
