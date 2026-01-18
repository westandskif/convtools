# Contrib / Tables

`Table` is a helper to work with table-like data. It infers the header from the
first row or accepts yours and allows you to massage columns and rows in a
stream-friendly manner (_without operations which require to consume the whole
sequence_).

/// admonition
    type: warning

* **`Table` data can only be consumed once: since a table takes an iterable, there's no way to iterate the second time.**
* **If you want to use `Table` inside conversions, [read this first](./contrib_tables.md#using-tables-inside-conversions).**
///


## Read / Output rows

**`Table.from_rows`** allows to initialize a table with an iterable of rows.
Arguments are as follows:

* `rows` - iterable of `dict`, `tuple`, `list` is considered as multi-column
  table, any other types as single-column one.
* `header` supports multiple types
	* `bool` - whether to infer the header or not. Default is None with the
	  only exception: when an iterable of dicts is accepted, unless
	  `header=False` it automatically infers the header from the first dict.
	* `list` and `tuple` - specify column names
    * `dict` - keys specify column names, values are indexes to be used to get
      column values
* `duplicate_columns`
	* **`raise` - the default for `from_rows`**. It raises `ValueError` when
	  encounters duplicate column names
    * `mangle` - it mangles duplicate column names like: `a`, `a_1`, `a_2`
	* `keep` - duplicate columns are left as is, but when referenced the first
	  one is used
    * `drop` - duplicate columns are skipped
* `skip_rows` - number of rows to be skipped at the beginning, default is 0

----

**`into_iter_rows`** method outputs the results as an iterator of rows,
arguments are:

* `type_` should be exactly one of the following: `dict`, `tuple`, `list`
* `include_header=None` whether to emit header or not

{!examples-md/contrib_tables_read_rows.md!}



## Read CSV-like

`Table.from_csv` initializes a table by reading a csv-like file, arguments are:

* `filepath_or_buffer` - a filepath or something the built-in `csv.reader` can
  read (iterator of lines)
* `header` supports multiple types
    * `bool` - whether to infer the header or not
	* `list` and `tuple` - specify column names
    * `dict` - keys specify column names, values are indexes to be used to get
      column values
* `duplicate_columns`
	* `raise` - It raises `ValueError` when encounters duplicate column names
	* **`mangle` - the default for `from_csv`**. It mangles duplicate column
	  names like: `a`, `a_1`, `a_2`
	* `keep` - duplicate columns are left as is, but when referenced the first
	  one is used
    * `drop` - duplicate columns are skipped
* `skip_rows` - number of rows to be skipped at the beginning, default is 0
* `dialect` - a dialect acceptable for the built-in `csv.reader`. There's a
  helper method to create dialects without defining classes:
  `Table.csv_dialect(delimiter="\t")` for tab-separated files.
* `encoding` - default is `utf-8`

----

**`into_csv`** method writes the results to a csv-like file, arguments are:

* `filepath_or_buffer` - a filepath or something `csv.writer` can write to
* `dialect` - a dialect acceptable by `csv.writer`. There's a
  helper method to create dialects without defining classes:
  `Table.csv_dialect(delimiter="\t")` for tab-separated files.
* `encoding` - default is `utf-8`

{!examples-md/contrib_tables_read_csv.md!}


## Rename, take / rearrange, drop columns

1. `rename(columns)` allows to rename columns, it accepts arguments of
   different types:
	 * `tuple` and `list` define new column names (_length of passed columns
	   should match the number of columns of the table_)
	 * `dict` defines a mapping from old column names to new ones
1. `take(*column_names)` leaves only specified columns (_order matters_),
   omitting the rest
	 * `take` can accept `...`, which references all non-mentioned columns, so
	   it's easy to rearrange them: `table.take("c", "d", ...)`
1. `drop(*column_names)` obviously drops columns, keeping the rest as-is.

{!examples-md/contrib_tables_rename_take_rearrange_drop.md!}


## Add, update columns

There's only one method to add and update columns, it's `update` and takes any
number of keyword arguments, where keys are names of new or existing columns,
while values are conversions to be applied row-wise.

Use `c.col("column name")` to reference the values of various columns.

{!examples-md/contrib_tables_add_update.md!}


## Filter rows

To filter rows, pass a conversion to the `filter` method, which will be used as
a condition.

Use `c.col("column name")` to reference the values of various columns.

{!examples-md/contrib_tables_filter.md!}


## Join tables

To join two tables, use `join` method, which accepts the following arguments:

* `table` - another table to join with
* `on` can be either:
    * a join conversion like `c.LEFT.col("a") == c.RIGHT.col("A")`
	* or an iterable of column names to join on
* `how` is to be one of: `"inner"`, `"left"`, `"right"`, `"full"`
* `suffixes` is a tuple of two strings (left and right) to be concatenated with
  column names of conflicting columns (_`on` columns passed as an iterable of
  strings don't count_). Default is `("_LEFT", "_RIGHT")`.

{!examples-md/contrib_tables_join.md!}


## Chain tables

`chain` method concatenates tables vertically. It has the following parameters:

* `table` to chain
* `fill_value` is used to fill gaps; default is `None`

{!examples-md/contrib_tables_chain.md!}


## Zip tables

`zip` method concatenates tables horizontally. Its parameters are:

* `table` to zip
* `fill_value` is used to fill gaps; default is `None`

/// admonition
    type: warning
* Before using this method, please make sure you are not looking for
  `Table.join`.
* Be cautious with using `.into_iter_rows(dict)` here, because by default
  `zip` uses `"keep"` `duplicate_columns` strategy, so you'll lose
  duplicate columns in case of collision because `dict` will take care of
  it
///

{!examples-md/contrib_tables_zip.md!}


## Explode table

`explode` method transforms a table with columns containing lists into a
table with values of these lists, by repeating values of other columns.

Args:

* `column_name: str` - first column with iterables to explode
* `*other_column_names: str` - additional columns to explode together

When multiple columns are provided, they are exploded together using
`zip_longest` semantics (like PostgreSQL's multiple `unnest` in same SELECT).
Shorter arrays are padded with `None`.

{!examples-md/contrib_tables_explode.md!}


## Wide to long

`wide_to_long` method turns a table from wide to long view, turning a single
row into multiple rows, which have fewer columns:

Args:

* `col_for_names: str` - name of the column with names of processed columns
* `col_for_values: str` - name of the column with values of processed columns
* `prepare_name: Optional[Callable[[str], str]]` - callable or conversion to prepare a name
* `prepare_value: Optional[Callable[[str], str]]` - callable or conversion to prepare a value
* `keep_cols: Sequence[str]` - column names to keep as is

{!examples-md/contrib_tables_wide_to_long.md!}


## Pivot

`pivot` method aggregates data and creates a pivot table.

Args:

* `rows: Sequence[str]` - columns to group by
* `columns: Sequence[str]` - columns to take names of new columns from
* `values: Mapping[str, str]` - mapping of name to reducer of column value/values
* `prepare_column_names: Callable[[Sequence[str]], str]` - callable to create column names from column names and reducer name

{!examples-md/contrib_tables_pivot.md!}


## Using tables inside conversions

It's impossible to make `Table` work directly inside other conversions, because
it would create more than one code generating layer.

But you most definitely can leverage piping to callables:

{!examples-md/contrib_tables_pipe.md!}

/// admonition
    type: note

Keep in mind, that unlike conversions, `Table` doesn't have `gen_converter`
method, so the code cannot be generated once during a warm-up and used
multiple times. Tables generate their code at each run.
///
