# Window functions

/// admonition | Prerequisites
    type: info

Start with [Basics](./basics.md) for conversion fundamentals,
[Collections](./collections.md) for iterable helpers, and
[Aggregations](./aggregations.md) for reducers used over window frames.
///

/// admonition | See also
    type: tip

For reducer behavior, see [`c.ReduceFuncs`](./aggregations.md#creducefuncs)
and [Reducers API](./aggregations.md#reducers-api). For SQL terminology, see
[PostgreSQL's window functions](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS).
///

`c.this.window(...).over(...)` applies SQL-style window calculations to a
Python iterable. It sorts rows into partitions, finds a frame for each row, and
returns one result for every input row.

The first argument to `window(...)` is a conversion evaluated for each output
row. It may contain `c.WindowFuncs` references to the current row, partition,
peer group, and frame metadata. It may also contain `c.ReduceFuncs` reducers,
which are evaluated over the current window frame.

When no ordering key is specified, all rows have the same ordering key and fall
in one peer group. Row and peer-group indexes are zero-based; add `1` when you
want SQL-style one-based numbering.

## Common SQL equivalents

### Row numbering and ranking

`RowIndex() + 1` is equivalent to `row_number()`,
`PeerGroupFirstRowIndex() + 1` is equivalent to `rank()`, and
`PeerGroupIndex() + 1` is equivalent to `dense_rank()`.

{!examples-md/api__window_funcs_ranking.md!}

### Aggregate over a window

Reducers inside `window(...)` behave like aggregate window functions. This
example is equivalent to `sum(amount) over (order by day rows between 1
preceding and current row)`.

{!examples-md/api__window_funcs_rolling_sum.md!}

### Lag and lead

`RowPreceding(offset)` is equivalent to `lag(...)`, and
`RowFollowing(offset)` is equivalent to `lead(...)`.

{!examples-md/api__window_funcs_lag_lead.md!}

## `c.WindowFuncs`

| Function | Arguments | Returns | SQL equivalent |
| --- | --- | --- | --- |
| `Row()` | none | The current row from the current partition. | Current row reference |
| `RowIndex()` | none | Zero-based row index within the current partition. | `row_number() - 1` |
| `RowPreceding(offset, default=None)` | `offset`: rows before current row; `default`: value when missing | The row at `offset` rows before the current row, or `default`. | `lag(row, offset, default)` |
| `RowFollowing(offset, default=None)` | `offset`: rows after current row; `default`: value when missing | The row at `offset` rows after the current row, or `default`. | `lead(row, offset, default)` |
| `PeerGroupFirstRow()` | none | The first row in the current peer group. | First row among ties |
| `PeerGroupLastRow()` | none | The last row in the current peer group. | Last row among ties |
| `PeerGroupFirstRowIndex()` | none | Zero-based index of the first row in the current peer group. | `rank() - 1` |
| `PeerGroupLastRowIndex()` | none | Zero-based index of the last row in the current peer group. | End index of rank peer group |
| `PeerGroupIndex()` | none | Zero-based peer-group index within the current partition. | `dense_rank() - 1` |
| `FrameFirstRow(default=None)` | `default`: value for an empty frame | First row in the current frame, or `default`. | `first_value(row)` |
| `FrameLastRow(default=None)` | `default`: value for an empty frame | Last row in the current frame, or `default`. | `last_value(row)` |
| `FrameNthRow(n, default=None)` | `n`: zero-based row offset in the frame; `default`: value when missing | The `n`th row in the current frame, or `default`. | `nth_value(row, n + 1)` |

Use `.item(...)`, `.attr(...)`, or any other conversion on row-returning
functions to extract fields:

```python
c.WindowFuncs.RowPreceding(1).item("amount", default=0)
```

## `.over(...)` parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `partition_by` | not set | Conversion used to split input rows into independent partitions. Use a tuple of conversions for multi-key partitions. |
| `order_by` | not set | Conversion, or tuple of conversions, used to order rows inside each partition. Equal ordering keys form a peer group. Supports sorting helpers such as `.desc()` and `none_last=True`. |
| `frame_mode` | `"RANGE"` | Frame interpretation: `"RANGE"` uses ordering-key values, `"ROWS"` uses row offsets, and `"GROUPS"` uses peer-group offsets. |
| `frame_start` | `"UNBOUNDED PRECEDING"` | Start boundary. Accepts `"UNBOUNDED PRECEDING"`, `"CURRENT ROW"`, or `(offset, "PRECEDING" / "FOLLOWING")`. |
| `frame_end` | `"CURRENT ROW"` | End boundary. Accepts `"UNBOUNDED FOLLOWING"`, `"CURRENT ROW"`, or `(offset, "PRECEDING" / "FOLLOWING")`. |
| `frame_exclusion` | `"NO OTHERS"` | Exclusion rule: `"NO OTHERS"`, `"CURRENT ROW"`, `"GROUP"`, or `"TIES"`. |

Frame modes follow PostgreSQL terminology:

| Mode | Frame offset meaning |
| --- | --- |
| `"RANGE"` | Offsets are added to or subtracted from the current row's ordering key. Offset frames require `order_by`. |
| `"ROWS"` | Offsets are non-negative row counts before or after the current row. |
| `"GROUPS"` | Offsets are peer-group counts before or after the current peer group. |

For available reducers, see [`c.ReduceFuncs`](./aggregations.md#creducefuncs).

## Frame mode examples

/// tab | RANGE mode
{!examples-md/api__window_funcs_range.md!}
///
/// tab | ROWS mode
{!examples-md/api__window_funcs_rows.md!}
///
/// tab | GROUPS mode
{!examples-md/api__window_funcs_groups.md!}
///
