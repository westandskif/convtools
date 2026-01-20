# Contrib / Tables

`Table` is a streaming helper for tabular data. It builds a pipeline of
convtools conversions so you can reshape, enrich, filter, and combine rows
without loading the entire dataset into memory.

/// admonition
    type: warning

* **`Table` is single-pass: the underlying iterable is consumed once. If you need to reuse data, materialize it or reopen the source.**
* **If you want to use `Table` inside conversions, [read this first](./contrib_tables.md#using-tables-inside-conversions).**
///

## Header handling and duplicate columns

`header` supports multiple forms:

* `True` - infer a header from the first row. For list/tuple input, the first
  row becomes the header and is not part of the data. For dict input, keys are
  used as column names and the row remains part of the data.
* `False` - treat input as headerless; columns are numbered (`COLUMN_0`,
  `COLUMN_1`, ...).
* `list` / `tuple` - explicit column names.
* `dict` - keys are column names, values are indexes (or keys) used to pull data.
* `None` - infer only if the first row is a dict; otherwise behave like `False`.

`duplicate_columns` controls how repeated column names are handled:

* `raise` - raise `ValueError`.
* `mangle` - rename duplicates to `name`, `name_1`, `name_2`, ...
* `keep` - keep duplicates; when referenced by name, the first one wins.
* `drop` - skip duplicates entirely.

Defaults differ by constructor: `from_rows` uses `raise`, while `from_csv` and
`from_jsonl` use `mangle`.

## Read / output rows

### `Table.from_rows`

Initialize a table from an iterable of rows.

Arguments:

* `rows` - iterable of `dict`, `tuple`, or `list` is treated as a multi-column
  table; any other type is treated as a single-column table.
* `header` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns).
* `duplicate_columns` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns).
* `skip_rows` - number of rows to skip before header handling; default is 0.

----

### `Table.into_iter_rows`

Return processed rows as an iterator.

Arguments:

* `type_` - must be `dict`, `tuple`, or `list`.
* `include_header` - when `True`, prepend a header row (ignored for `dict`).

{!examples-md/contrib_tables_read_rows.md!}

## Read CSV-like

### `Table.from_csv`

Initialize a table from a CSV-like file.

Arguments:

* `filepath_or_buffer` - a filepath or a buffer acceptable by `csv.reader`.
* `header` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns).
* `duplicate_columns` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns).
* `skip_rows` - number of rows to skip before header handling; default is 0.
* `dialect` - a dialect acceptable by `csv.reader`. Use
  `Table.csv_dialect(delimiter="\t")` for tab-separated files.
* `encoding` - default is `utf-8`.

----

### `Table.into_csv`

Write the results to a CSV-like file.

Arguments:

* `filepath_or_buffer` - a filepath or something `csv.writer` can write to.
* `include_header` - whether to emit the header; default is `True`.
* `dialect` - a dialect acceptable by `csv.writer`. Use
  `Table.csv_dialect(delimiter="\t")` for tab-separated files.
* `encoding` - default is `utf-8`.

{!examples-md/contrib_tables_read_csv.md!}

## Read JSONL

### `Table.from_jsonl`

Initialize a table from a JSONL (JSON Lines) file. Each line must be a valid
JSON object or array. Empty lines are silently skipped.

Arguments:

* `filepath_or_buffer` - a filepath or a text buffer to read from.
* `header` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns).
* `duplicate_columns` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns).
* `skip_rows` - number of rows to skip before header handling; default is 0.
* `encoding` - default is `utf-8`.

----

### `Table.into_jsonl`

Write the results to a JSONL file (one JSON object per line).

Arguments:

* `filepath_or_buffer` - a filepath or a text buffer to write to.
* `encoding` - default is `utf-8`.

{!examples-md/contrib_tables_read_jsonl.md!}

## Rename, take / rearrange, drop columns

* `rename(columns)` renames columns:
  * `tuple` / `list` define new column names (length must match the current
    number of columns).
  * `dict` maps old column names to new ones.
* `take(*column_names)` keeps only specified columns (order matters).
  * `take` can accept `...` to include all non-mentioned columns, which makes
    reordering easy: `table.take("c", "d", ...)`.
* `drop(*column_names)` drops specified columns, keeping the rest as-is.

{!examples-md/contrib_tables_rename_take_rearrange_drop.md!}

## Add, update columns

Use `update` to add or replace columns and `update_all` to apply conversions
to every existing column.

* `update(**column_to_conversion)` takes keyword arguments where keys are
  column names and values are conversions applied row-wise.
* `update_all(*conversions)` composes conversions and applies them to each
  value in each column.

Use `c.col("column name")` to reference column values.

{!examples-md/contrib_tables_add_update.md!}

## Filter rows

To filter rows, pass a conversion to the `filter` method. Rows are kept when
the conversion returns a truthy value.

Use `c.col("column name")` to reference column values.

{!examples-md/contrib_tables_filter.md!}

## Join tables

Use `join` to combine two tables. Arguments:

* `table` - another table to join with.
* `on` - either:
  * a join conversion like `c.LEFT.col("a") == c.RIGHT.col("A")`, or
  * an iterable of column names to join on.
* `how` - one of `"inner"`, `"left"`, `"right"`, `"full"`.
* `suffixes` - a tuple of two strings (left and right) to be concatenated with
  conflicting column names. Default is `("_LEFT", "_RIGHT")`. Columns listed in
  `on` (when `on` is an iterable of names) are not suffixed.

{!examples-md/contrib_tables_join.md!}

## Chain tables

`chain` concatenates tables vertically (appends rows).

Arguments:

* `table` - table to chain.
* `fill_value` - value used to fill gaps when columns don't align; default is
  `None`.

{!examples-md/contrib_tables_chain.md!}

## Zip tables

`zip` concatenates tables horizontally (combines columns row-by-row).

Arguments:

* `table` - table to zip.
* `fill_value` - value used to fill gaps; default is `None`.

/// admonition
    type: warning

* Before using this method, please make sure you are not looking for
  `Table.join`.
* Be cautious with using `.into_iter_rows(dict)` here, because by default
  `zip` uses the `"keep"` `duplicate_columns` strategy. If column names collide,
  `dict` will keep only the first occurrence.
///

{!examples-md/contrib_tables_zip.md!}

## Explode table

`explode` transforms a table with columns containing lists into a table with
values of those lists, repeating values of other columns.

Arguments:

* `column_name` - first column with iterables to explode.
* `*other_column_names` - additional columns to explode together.
* `fill_value` - value used to pad shorter arrays when exploding multiple
  columns together; default is `None`.

When multiple columns are provided, they are exploded together using
`zip_longest` semantics (like PostgreSQL's multiple `unnest` in the same
`SELECT`). Shorter arrays are padded with `fill_value`.

{!examples-md/contrib_tables_explode.md!}

## Wide to long

`wide_to_long` turns a table from wide to long form, converting each input row
into multiple rows with fewer columns.

Arguments:

* `col_for_names` - name of the column with names of processed columns.
* `col_for_values` - name of the column with values of processed columns.
* `prepare_name` - callable or conversion to prepare a name.
* `prepare_value` - callable or conversion to prepare a value.
* `keep_cols` - column names to keep as-is.

{!examples-md/contrib_tables_wide_to_long.md!}

## Pivot

`pivot` aggregates data and creates a pivot table.

Arguments:

* `rows` - columns to group by.
* `columns` - columns to take names of new columns from.
* `values` - mapping of name to reducer of column value/values.
* `prepare_column_names` - callable to create column names from column names and
  reducer name.

{!examples-md/contrib_tables_pivot.md!}

## Using tables inside conversions

`Table` cannot be used directly inside other conversions because it would
introduce a second code-generation layer.

You can still use piping to callables:

{!examples-md/contrib_tables_pipe.md!}

/// admonition
    type: note

Keep in mind that unlike conversions, `Table` doesn't have `gen_converter`,
so the code cannot be generated once during a warm-up and reused. Tables
generate their code on each run.
///
