# Aggregations

**Please, make sure you've covered [Basics](./basics.md) first.**

The syntax to define aggregations is as follows:

 * `c.group_by(key1, key2, ...).aggregate(result)` returns list of results
 * `c.aggregate(result)` returns the result

where `result` is any conversion (_`dict`, `c.call_func`, whatever_) made up
of:

 * keys - `key1, keys, ...`
 * reducers - e.g. `c.ReduceFuncs.Sum(c.item("abc"))`


## c.group_by

{!examples-md/welcome__group_by.md!}

## c.aggregate

{!examples-md/welcome__aggregations.md!}


## c.ReduceFuncs

Here is the list of available reducers like `c.ReduceFuncs.Sum` with info on:

    * Sum - sums values, skips None, considering false values as 0; default=0
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
    * StdDev - sample standard deviation, skips None
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
    * DictArrayDistinct - dict values are lists of unique group (values preserves order)
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

Every reducer keyword arguments:

 * `where` - a condition to filter input values of a reducer
 * `default` - a value in case a reducer hasn't encountered any values

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
| Count             | v       | v      |         | 0       | 1-args     | v                |
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
| DictCount         |         | v      | v       | None    | 2-args     |                  |
| DictCountDistinct |         |        | v       | None    | v          |                  |
| DictFirst         |         |        | v       | None    |            |                  |
| DictLast          |         |        | v       | None    |            |                  |
| DictMax           |         |        | v       | None    | v          |                  |
| DictMin           |         |        | v       | None    | v          |                  |
| DictSum           |         |        | v       | None    | v          |                  |
| DictSumOrNone     |         |        | v       | None    |            |                  |
| DictFirstN        |         |        | v       | None    |            |                  |
| DictLastN         |         |        | v       | None    |            |                  |



