import io

from convtools import conversion as c
from convtools.contrib.tables import Table

tsv_buffer = io.StringIO("a\tc\n0\t-2\n2\t4\n1\t3\n")

# reads Iterable of rows
iterable_of_rows = (
    Table.from_rows([(0, -1), (1, 2)], header=["a", "b"]).join(
        Table
        # reads tab-separated CSV file or buffer
        .from_csv(
            tsv_buffer,  # or "ac.csv"
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
