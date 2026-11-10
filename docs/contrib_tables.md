# Contrib / Tables

/// admonition | Prerequisites
    type: info

Start with [Basics](./basics.md) for conversion fundamentals used inside
`Table.update`, `Table.filter`, `Table.join`, and `Table.pivot`.
///

`Table` is a streaming helper for tabular data. It builds a pipeline of
convtools conversions so you can reshape, enrich, filter, and combine rows
while keeping row-wise work incremental where possible.

/// admonition
    type: warning

* **`Table` is single-pass: the underlying iterable is consumed once. If you need to reuse data, materialize it or reopen the source.**
* **If you want to use `Table` inside conversions, [read this first](./contrib_tables.md#using-tables-inside-conversions).**
///

Single-pass does not mean that every operation uses constant memory. The
pipeline is consumed once, but some operations must retain state:

| Operation shape | Execution behavior |
| --------------- | ------------------ |
| Row-wise `filter`, `update`, `update_all`, `rename`, `take`, and `drop` | Process rows incrementally. |
| `join` | Builds matching state for right-side rows; memory grows with that side of the join. |
| `pivot` | Consumes and aggregates the input before it can determine the output columns. |
| `into_iter_rows`, `into_csv`, and `into_jsonl` | Terminal operations which consume the pipeline; only `into_iter_rows` returns an iterator. |

Materialize a result yourself only when it needs to be reused. Otherwise, pass
the iterator returned by `into_iter_rows` onward or write directly to a file.

Inspect a table's current column names at any point with `table.columns` (or
`table.get_columns()`), which returns a `list[str]`.

## End-to-end pipeline

This example reads tabular inputs, transforms and filters one side, joins the
tables, rearranges the result columns, and returns a row iterator:

--8<-- "docs/examples-md/welcome__tables.md"

## Header handling and duplicate columns

`header` supports multiple forms:

* `True` - infer a header from the first row. For list/tuple input, the first
  row becomes the header and is not part of the data. For dict input, the first
  row's keys become column names, and that first row's values are still emitted
  as data.
* `False` - treat input as headerless; columns are numbered (`COLUMN_0`,
  `COLUMN_1`, ...).
* `list` / `tuple` - explicit column names.
* `dict` - keys are column names, values are indexes (or keys) used to pull data.
* `None` - infer only if the first row is a dict; otherwise behave like `False`.
  When inferred from a dict, the first row is still emitted as data.

`duplicate_columns` controls how repeated column names are handled:

* `raise` - raise `ValueError`.
* `mangle` - rename duplicates to `name`, `name_1`, `name_2`, ..., skipping
  names that are already taken.
* `keep` - keep duplicates; when referenced by name, the first one wins.
  `Table.drop` removes only the first column of each given name.
* `drop` - skip duplicates entirely.

Defaults differ by constructor: `from_rows` uses `raise`, while `from_csv` and
`from_jsonl` use `mangle`.

## Read / output rows

### `Table.from_rows`

Initialize a table from an iterable of rows.

Arguments:

* `rows` - iterable of `dict`, `tuple`, or `list` is treated as a multi-column
  table; any other type is treated as a single-column table.
* `header` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns); default is `None`.
* `duplicate_columns` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns); default is `"raise"`.
* `skip_rows` - number of rows to skip before header handling; default is `0`.

----

### `Table.into_iter_rows`

Return processed rows as an iterator.

Arguments:

* `type_` - `tuple` (default), `dict`, or `list`.
* `include_header` - when `True`, prepend a header row (ignored for `dict`;
  default is `None`).

When the first row already has the requested type and no column changes are
pending, rows pass through unchanged, so the output row type is guaranteed
only for homogeneous input.

--8<-- "docs/examples-md/contrib_tables_read_rows.md"

## Read CSV-like

### `Table.from_csv`

Initialize a table from a CSV-like file.

Arguments:

* `filepath_or_buffer` - a filepath or a buffer acceptable by `csv.reader`.
* `header` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns); default is `None`.
* `duplicate_columns` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns); default is `"mangle"`.
* `skip_rows` - number of non-empty records to skip before header handling;
  default is 0. Empty lines are skipped and do not count. A whitespace-only
  line is a one-column record: it counts toward `skip_rows`, and once past
  skipping it is yielded, or raises the ragged-row `ValueError` when the
  fixed width is not 1. The first record kept after skipping fixes the row
  width; a later record of a different width raises `ValueError` with the
  1-based physical line number.
* `dialect` - a dialect name or object acceptable by `csv.reader` (default is
  `"excel"`). Use `Table.csv_dialect(...)` to customize dialect options without
  defining a `csv.Dialect` subclass; it accepts `delimiter`, `quotechar`,
  `escapechar`, `doublequote`, `skipinitialspace`, `lineterminator`, and
  `quoting` (all defaulting to `csv.excel`).
* `encoding` - default is `"utf-8"`.

----

### `Table.into_csv`

Write the results to a CSV-like file.

This is a terminal writer method: it consumes the table pipeline, writes rows
to the target, and returns `None`.

Arguments:

* `filepath_or_buffer` - a filepath or something `csv.writer` can write to.
* `include_header` - whether to emit the header; default is `True`.
* `dialect` - a dialect name or object acceptable by `csv.writer` (default is
  `"excel"`), including `Table.csv_dialect(...)`.
* `encoding` - default is `"utf-8"`.

--8<-- "docs/examples-md/contrib_tables_read_csv.md"

## Read JSONL

### `Table.from_jsonl`

Initialize a table from a JSONL (JSON Lines) file. Each line must be a valid
JSON object or array. Empty lines are silently skipped.

Arguments:

* `filepath_or_buffer` - a filepath or a text buffer to read from.
* `header` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns); default is `None`.
* `duplicate_columns` - see [Header handling and duplicate columns](./contrib_tables.md#header-handling-and-duplicate-columns); default is `"mangle"`.
* `skip_rows` - number of non-empty records to skip before header handling;
  blank and whitespace-only lines are skipped and do not count; default is 0.
* `encoding` - default is `"utf-8"`.

----

### `Table.into_jsonl`

Write the results to a JSONL file (one JSON object per line).

This is a terminal writer method: it consumes the table pipeline, writes rows
to the target, and returns `None`.

Arguments:

* `filepath_or_buffer` - a filepath or a text buffer to write to.
* `encoding` - default is `"utf-8"`.

--8<-- "docs/examples-md/contrib_tables_read_jsonl.md"

## Rename, take / rearrange, drop columns

* `table.columns` (property) / `table.get_columns()` returns the current list
  of column names (`list[str]`).
* `rename(columns)` renames columns:
  * `tuple` / `list` define new column names (length must match the current
    number of columns).
  * `dict` maps old column names to new ones.
* `take(*column_names)` keeps only specified columns (order matters).
  * `take` can accept `...` to include all non-mentioned columns, which makes
    reordering easy: `table.take("c", "d", ...)`.
* `drop(*column_names)` drops specified columns, keeping the rest as-is.

--8<-- "docs/examples-md/contrib_tables_rename_take_rearrange_drop.md"

## Add, update columns

Use `update` to add or replace columns and `update_all` to apply conversions
to every existing column.

* `update(**column_to_conversion)` takes keyword arguments where keys are
  column names and values are conversions applied row-wise.
* `update_all(*conversions)` composes conversions and applies them to each
  value in each column (`c.this` refers to the current cell value, while
  `c.col("...")` reads another column from the same row).

Use `c.col("column name")` to reference column values.

--8<-- "docs/examples-md/contrib_tables_add_update.md"

## Filter rows

To filter rows, pass a conversion to the `filter` method. Rows are kept when
the conversion returns a truthy value.

Use `c.col("column name")` to reference column values.

--8<-- "docs/examples-md/contrib_tables_filter.md"

## Join tables

Use `join(table, on, how, suffixes=("_LEFT", "_RIGHT"))` to combine two tables.
Arguments:

* `table` - another table to join with.
* `on` - either:
  * a join conversion like `c.LEFT.col("a") == c.RIGHT.col("A")`,
  * a single column name (`str`), or
  * an iterable of column names to join on.
* `how` (required; no default) - one of `"inner"`, `"left"`, `"right"`,
  `"full"` (`"outer"` is accepted as an alias for `"full"`).
* `suffixes` - a tuple of two strings (left and right) concatenated with
  conflicting column names; default is `("_LEFT", "_RIGHT")`. Columns named in
  `on` (when `on` is a column name or iterable of names) are not suffixed.

--8<-- "docs/examples-md/contrib_tables_join.md"

## Chain tables

`chain` concatenates tables vertically (appends rows).

Arguments:

* `table` - table to chain.
* `fill_value` - value used to fill gaps when columns don't align; default is
  `None`.

Tables with duplicate names (`duplicate_columns="keep"`) keep them only on
the identical-schema fast path; otherwise columns align by name using the
first column of each name.

--8<-- "docs/examples-md/contrib_tables_chain.md"

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

--8<-- "docs/examples-md/contrib_tables_zip.md"

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

--8<-- "docs/examples-md/contrib_tables_explode.md"

## Wide to long

`wide_to_long` turns a table from wide to long form, converting each input row
into multiple rows with fewer columns.

Arguments:

* `col_for_names` - name of the column receiving collapsed column names;
  default is `"name"`.
* `col_for_values` - name of the column receiving collapsed column values;
  default is `"value"`.
* `prepare_name` - optional callable or conversion to prepare each column name;
  default is `None`.
* `prepare_value` - optional callable or conversion to prepare each value;
  default is `None`.
* `keep_cols` - sequence of column names to keep as-is; default is `()`.

--8<-- "docs/examples-md/contrib_tables_wide_to_long.md"

## Pivot

`pivot` aggregates data and creates a pivot table.

Arguments:

* `rows` - columns to group by.
* `columns` - columns to take names of new columns from.
* `values` - mapping of name to reducer of column value/values.
* `prepare_column_names` - callable to create column names from column names and
  reducer name. By default, each generated column is named by joining the
  pivot column value(s) and reducer name with `" - "`, after converting every
  part to `str`; for example, `columns=["currency"]` and a `"sum"` reducer can
  produce `"USD - sum"`.

--8<-- "docs/examples-md/contrib_tables_pivot.md"

## Using tables inside conversions

`Table` cannot be used directly inside other conversions because it would
introduce a second code-generation layer.

You can still use piping to callables:

--8<-- "docs/examples-md/contrib_tables_pipe.md"

/// admonition
    type: note

Keep in mind that unlike conversions, `Table` doesn't have `gen_converter`,
so the code cannot be generated once during a warm-up and reused. Tables
generate their code on each run.
///
