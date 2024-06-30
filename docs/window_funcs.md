# Window functions

**Please, make sure you've covered [Reference / Basics](./basics.md) first.**

/// admonition | Experimental feature
    type: warning
It was added on Jul 1, 2024 and may be stabilized ~ in a year.
///

This is SQL's `count(*) over (...)` counterpart, its interface should closely follow
[PostgreSQL's window functions](https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS).

It slides over a sequence with a window frame, applying reducers to each frame
and returns their results.

#### Examples

/// tab | RANGE mode
{!examples-md/api__window_funcs_range.md!}
///
/// tab | ROWS mode
{!examples-md/api__window_funcs_rows.md!}
///
/// tab | GROUPS mode
{!examples-md/api__window_funcs_groups.md!}
///

Available `c.WindowFuncs`:

    * FrameFirstRow(default=None)
    * FrameLastRow(default=None)
    * FrameNthRow(n, default=None)
    * PeerGroupFirstRow()
    * PeerGroupFirstRowIndex()
    * PeerGroupIndex()
    * PeerGroupLastRow()
    * PeerGroupLastRowIndex()
    * Row()
    * RowFollowing(offset, default=None)
    * RowIndex()
    * RowPreceding(offset, default=None)

For available `c.ReduceFuncs`, please check [here](./aggregations.md#creducefuncs).

#### Parameters

    --8<-- "src/convtools/_window.py:over_args_docs"

/// admonition
    type: hint
When no ordering key is specified, all rows have the same ordering key and
fall in the single peer group.
///
