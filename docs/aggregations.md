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

<!-- reducer-inventory:start -->
The public reducer inventory is generated from `c.ReduceFuncs`:

##### Value reducers

| Reducer | Description |
| ------- | ----------- |
| `Array` | Collects values as a list. |
| `ArrayDistinct` | Collects distinct values as a list, preserving order. |
| `ArraySorted` | Collects values as a sorted list. |
| `Average` | Calculates the arithmetic mean or weighted mean, skipping `None`. |
| `Correlation` | Calculates Pearson correlation between two variables, skipping `None`. |
| `Count` | `Count()` counts rows; `Count(value)` counts non-`None` values. |
| `CountDistinct` | Counts distinct non-`None` values. |
| `Covariance` | Calculates sample covariance between two variables, skipping `None`. |
| `First` | Returns the first encountered value. |
| `FirstN` | Collects the first N encountered values as a list. |
| `Last` | Returns the last encountered value. |
| `LastN` | Collects the last N encountered values as a list. |
| `Max` | Returns the max value, skipping `None`. |
| `MaxRow` | Returns the row with the max value, skipping `None` comparison values. |
| `Median` | Calculates the median value, skipping `None`. |
| `Min` | Returns the min value, skipping `None`. |
| `MinRow` | Returns the row with the min value, skipping `None` comparison values. |
| `Mode` | Returns the most common non-`None` value, using the last value on ties. |
| `Percentile` | Calculates a percentile from floats in `[0, 100]`, skipping `None`. |
| `PopulationStdDev` | Calculates population standard deviation, skipping `None`. |
| `PopulationVariance` | Calculates population variance, skipping `None`. |
| `StdDev` | Calculates sample standard deviation, skipping `None`. |
| `Sum` | Sums values, skipping `None` and falsy values; default is `0`. |
| `SumOrNone` | Sums values; any `None` makes the result `None`. |
| `TopK` | Returns the most frequent non-`None` values, sorted by descending frequency. |
| `Variance` | Calculates sample variance, skipping `None`. |

##### Dict reducers

| Reducer | Description |
| ------- | ----------- |
| `Dict` | Builds a dict whose values are the last value per key. |
| `DictArray` | Builds a dict whose values are lists of values per key. |
| `DictArrayDistinct` | Builds a dict whose values are distinct lists per key, preserving order. |
| `DictCount` | `DictCount(key)` counts rows per key; `DictCount(key, value)` counts non-`None` values per key. |
| `DictCountDistinct` | Builds a dict whose values are counts of distinct non-`None` values per key. |
| `DictFirst` | Builds a dict whose values are first encountered values per key. |
| `DictFirstN` | Builds a dict whose values are first N encountered values per key. |
| `DictLast` | Builds a dict whose values are last encountered values per key. |
| `DictLastN` | Builds a dict whose values are last N encountered values per key. |
| `DictMax` | Builds a dict whose values are max values per key, skipping `None`. |
| `DictMin` | Builds a dict whose values are min values per key, skipping `None`. |
| `DictSum` | Builds a dict whose values are sums per key, skipping `None`. |
| `DictSumOrNone` | Builds a dict whose values are sums per key; any `None` makes that key's result `None`. |

Dict reducers aggregate into dictionaries whose values are reduced per key. See [Reducers API](#reducers-api) below for argument counts, defaults, `None` handling, `initial=` support, and edge-case notes.

You can also define custom reducers with `c.reduce` by passing any two-argument reduce function, for example `c.reduce(lambda a, b: a + b, c.item("amount"), initial=0)`.
<!-- reducer-inventory:end -->

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
