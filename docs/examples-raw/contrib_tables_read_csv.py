from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    # READING CSV
    # file content:
    #   a,b
    #   1,2
    #   2,3
    assert list(
        Table
        .from_csv("tests/csvs/ab.csv", header=True)
        .into_iter_rows(dict)
        # .into_csv("output.csv")  # TO WRITE TO A FILE
    ) == [
        {"a": "1", "b": "2"},
        {"a": "2", "b": "3"},
    ]

    # READING TSV
    # file content:
    #   a\tb
    #   1\t2
    #   2\t3
    assert list(
        Table.from_csv(
            "tests/csvs/ac.csv",
            header=True,
            dialect=Table.csv_dialect(delimiter="\t"),
        ).into_iter_rows(dict)
    ) == [
        {"a": "2", "c": "4"},
        {"a": "1", "c": "3"},
    ]

    # READ TSV + SKIP EXISTING HEADER + REMAP COLUMNS
    # file content:
    #   a\tb
    #   1\t2
    #   2\t3
    assert list(
        Table.from_csv(
            "tests/csvs/ac.csv",
            header={"a": 1, "c": 0},
            skip_rows=1,
            dialect=Table.csv_dialect(delimiter="\t"),
        ).into_iter_rows(dict)
    ) == [
        {"a": "4", "c": "2"},
        {"a": "3", "c": "1"},
    ]
