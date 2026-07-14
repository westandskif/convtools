from convtools.contrib.tables import Table

assert list(
    Table.from_rows(
        [{"name": "John", "height": 200, "age": 30, "mood": "good"}]
    )
    .wide_to_long(
        col_for_names="metric", col_for_values="value", keep_cols=("name",)
    )
    .into_iter_rows(dict)
) == [
    {"name": "John", "metric": "height", "value": 200},
    {"name": "John", "metric": "age", "value": 30},
    {"name": "John", "metric": "mood", "value": "good"},
]
