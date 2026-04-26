# Aggregations

**Please, make sure you've covered [Basics](./basics.md) first.**

The syntax to define aggregations is as follows:

 * `c.group_by(key1, key2, ...).aggregate(result)` returns list of results
 * `c.aggregate(result)` returns the result

where `result` is any conversion (_`dict`, `c.call_func`, whatever_) made up
of:

 * keys - `key1, keys, ...`
 * reducers - e.g. `c.ReduceFuncs.Sum(c.item("abc"))`

Reducer arguments are evaluated against each input row, so `c.this` and
shortcuts like `c.item(...)` refer to the row currently being reduced. See
[Placeholders & Special References](./basics.md#placeholders-special-references)
for the broader context-reference rules.


## c.group_by

{!examples-md/welcome__group_by.md!}

## c.aggregate

{!examples-md/welcome__aggregations.md!}


## c.ReduceFuncs

Here is the list of available reducers like `c.ReduceFuncs.Sum`:

    * Sum - sums values, treating `None` and other falsy values such as
      `False` as `0`; default=0
    * SumOrNone - strict sum OR None if at least one None is encountered;
      default=None
    * Max - max value, skips None
    * MaxRow - row with max value, skips None
    * Min - min value, skips None
    * MinRow - row with min value, skips None
    * Count
	    - when 0-args: count of rows
		- when 1-args: count of not None values
    * CountDistinct - len of resulting set of values
    * First - first encountered value
    * Last - last encountered value
    * Average(value, weight=1) - simple/weighted average, skips None
    * Median
    * Percentile(percentile, value, interpolation="linear") - percentile value,
      skips None;
		interpolation is one of:
		  - "linear"
		  - "lower"
		  - "higher"
		  - "midpoint"
		  - "nearest"
      e.g.: c.ReduceFuncs.Percentile(95.0, c.item("x"))
    * Mode - most frequent value, skips None
    * TopK - top K most frequent values, skips None
      e.g. top 3 most frequent ones: c.ReduceFuncs.TopK(3, c.item("x"))
    * FirstN - collect first N values as a list
      e.g.: c.ReduceFuncs.FirstN(3, c.item("x"))
    * LastN - collect last N values as a list
      e.g.: c.ReduceFuncs.LastN(3, c.item("x"))
    * Variance - sample variance, skips None; returns None for n<2
    * StdDev - sample standard deviation, skips None; returns None for n<2
    * PopulationVariance - population variance, skips None
    * PopulationStdDev - population standard deviation, skips None
    * Covariance(x, y) - sample covariance between two variables, skips None
    * Correlation(x, y) - Pearson correlation coefficient, skips None
    * Array
    * ArrayDistinct
    * ArraySorted
	    c.ReduceFuncs.ArraySorted(c.item("x"), key=lambda v: v, reverse=True)

	DICT REDUCERS ARE IN FACT AGGREGATIONS THEMSELVES, BECAUSE VALUES GET REDUCED:
    * Dict
	    c.ReduceFuncs.Dict(c.item("key"), c.item("x"))
    * DictArray - dict values are lists of encountered values
    * DictArrayDistinct - dict values are lists of unique group values,
      preserving order
    * DictSum - dict values are reduced by Sum
    * DictSumOrNone
    * DictMax
    * DictMin
    * DictCount
	    - when 1-args: dict values are counts of reduced rows
	    - when 2-args: dict values are counts of not None values
    * DictCountDistinct
    * DictFirst
    * DictLast
    * DictFirstN - dict values are lists of first N encountered values
      e.g.: c.ReduceFuncs.DictFirstN(3, c.item("key"), c.item("x"))
    * DictLastN - dict values are lists of last N encountered values
      e.g.: c.ReduceFuncs.DictLastN(3, c.item("key"), c.item("x"))

	AND LASTLY YOU CAN DEFINE YOUR OWN REDUCER BY PASSING ANY REDUCE FUNCTION
	OF TWO ARGUMENTS TO ``c.reduce`` (it may be slower because of extra
	function call):
	  - c.reduce(lambda a, b: a + b, c.item("amount"), initial=0)



#### Reducers API

Every reducer accepts the following keyword arguments:

 * `where` - a condition evaluated for each input row before the reducer sees
   the row's value.
 * `default` - a value returned when the reducer hasn't reduced any values.
 * `initial` - an initial accumulator value for reducers that support it. For
   reducers that do not support it, passing `initial` is deprecated and v2 will
   raise `ValueError`; prefer `default=` unless the table marks `initial` as
   supported.

The table below gives the following info on builtin reducers:

 * how many positional arguments they can accept
 * what are their default values (_returned when no rows are reduced_)
 * whether they skip `None` during reducing
 * whether they support `initial` keyword argument.

| Reducer           | 0-args  | 1-args | 2-args  | default | skips None | supports initial |
| ----------------- | ------- | ------ | ------- | ------- | ---------- | ---------------- |
| Array             |         | v      |         | None    |            | v                |
| ArrayDistinct     |         | v      |         | None    |            |                  |
| ArraySorted       |         | v      |         | None    |            |                  |
| Average           |         | v      |         | None    | v          |                  |
| Count             | v       | v      |         | 0       | note 1     | v                |
| CountDistinct     |         | v      |         | 0       | v          |                  |
| First             |         | v      |         | None    |            |                  |
| Last              |         | v      |         | None    |            |                  |
| Max               |         | v      |         | None    | v          | v                |
| MaxRow            |         | v      |         | None    | v          |                  |
| Median            |         | v      |         | None    | v          |                  |
| Min               |         | v      |         | None    | v          | v                |
| MinRow            |         | v      |         | None    | v          |                  |
| Mode              |         | v      |         | None    | v          |                  |
| Percentile        |         | v      |         | None    | v          |                  |
| Sum               |         | v      |         | 0       | v          | v                |
| SumOrNone         |         | v      |         | None    |            | v                |
| TopK              |         | v      |         | None    | v          |                  |
| FirstN            |         | v      |         | None    |            | v                |
| LastN             |         | v      |         | None    |            |                  |
| Variance          |         | v      |         | None    | v          |                  |
| StdDev            |         | v      |         | None    | v          |                  |
| PopulationVariance|         | v      |         | None    | v          |                  |
| PopulationStdDev  |         | v      |         | None    | v          |                  |
| Covariance        |         |        | v       | None    | v          |                  |
| Correlation       |         |        | v       | None    | v          |                  |
| Dict              |         |        | v       | None    |            |                  |
| DictArray         |         |        | v       | None    |            |                  |
| DictArrayDistinct |         |        | v       | None    |            |                  |
| DictCount         |         | v      | v       | None    | note 2     |                  |
| DictCountDistinct |         |        | v       | None    | v          |                  |
| DictFirst         |         |        | v       | None    |            |                  |
| DictLast          |         |        | v       | None    |            |                  |
| DictMax           |         |        | v       | None    | v          |                  |
| DictMin           |         |        | v       | None    | v          |                  |
| DictSum           |         |        | v       | None    | v          |                  |
| DictSumOrNone     |         |        | v       | None    |            |                  |
| DictFirstN        |         |        | v       | None    |            |                  |
| DictLastN         |         |        | v       | None    |            |                  |

Notes:

 * note 1: `Count()` counts rows; `Count(value)` counts non-`None` values.
 * note 2: `DictCount(key)` counts rows per key; `DictCount(key, value)`
   counts non-`None` values per key.

Statistical reducers follow the usual sample/population edge cases after
`where` and `None` filtering: `Variance` and `StdDev` return `None` for empty
input or fewer than two reduced values; `PopulationVariance` and
`PopulationStdDev` return `None` for empty input and `0` for one reduced value.
