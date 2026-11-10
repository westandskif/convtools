import io

from convtools.contrib.tables import Table

# READING CSV (file path or buffer)
assert list(
    Table.from_csv(
        io.StringIO("a,b\n1,2\n2,3\n"),  # or "ab.csv"
        header=True,
    ).into_iter_rows(dict)
    # .into_csv("output.csv")  # TO WRITE TO A FILE
) == [
    {"a": "1", "b": "2"},
    {"a": "2", "b": "3"},
]

# READING TSV
assert list(
    Table.from_csv(
        io.StringIO("a\tc\n2\t4\n1\t3\n"),
        header=True,
        dialect=Table.csv_dialect(delimiter="\t"),
    ).into_iter_rows(dict)
) == [
    {"a": "2", "c": "4"},
    {"a": "1", "c": "3"},
]

# READ TSV + SKIP EXISTING HEADER + REMAP COLUMNS
assert list(
    Table.from_csv(
        io.StringIO("a\tc\n2\t4\n1\t3\n"),
        header={"a": 1, "c": 0},
        skip_rows=1,
        dialect=Table.csv_dialect(delimiter="\t"),
    ).into_iter_rows(dict)
) == [
    {"a": "4", "c": "2"},
    {"a": "3", "c": "1"},
]
