# Group By and Aggregate

**Please, make sure you've covered [Reference / Basics](./basics.md) first.**

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

    * Sum - auto-replaces False values with 0; default=0
    * SumOrNone - sum or None if at least one None is encountered; default=None
    * Max - max not None
    * MaxRow - row with max not None
    * Min - min not None
    * MinRow - row with min not None
    * Count
	    - when 0-args: count of rows
		- when 1-args: count of not None values
    * CountDistinct - len of resulting set of values
    * First - first encountered value
    * Last - last encountered value
    * Average(value, weight=1) - pass custom weight conversion for weighted average
    * Median
    * Percentile(percentile, value, interpolation="linear")
	    c.ReduceFuncs.Percentile(95.0, c.item("x"))
		interpolation is one of:
		  - "linear"
		  - "lower"
		  - "higher"
		  - "midpoint"
		  - "nearest"
    * Mode
    * TopK - c.ReduceFuncs.TopK(3, c.item("x"))
    * Array
    * ArrayDistinct
    * ArraySorted
	    c.ReduceFuncs.ArraySorted(c.item("x"), key=lambda v: v, reverse=True)

	DICT REDUCERS ARE IN FACT AGGREGATIONS THEMSELVES, BECAUSE VALUES GET REDUCED:
    * Dict
	    c.ReduceFuncs.Dict(c.item("key"), c.item("x"))
    * DictArray - dict values are lists of encountered values
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
 * and whether they support `initial` keyword argument.

| Reducer           | 0-args  | 1-args | 2-args  | default | supports initial |
| ----------------- | ------- | ------ | ------- | ------- | ---------------- |
| Array             |         | v      |         | None    | v                |
| ArrayDistinct     |         | v      |         | None    |                  |
| ArraySorted       |         | v      |         | None    |                  |
| Average           |         | v      |         | None    |                  |
| Count             | v       | v      |         | 0       | v                |
| CountDistinct     |         | v      |         | 0       |                  |
| First             |         | v      |         | None    |                  |
| Last              |         | v      |         | None    |                  |
| Max               |         | v      |         | None    | v                |
| MaxRow            |         | v      |         | None    |                  |
| Median            |         | v      |         | None    |                  |
| Min               |         | v      |         | None    | v                |
| MinRow            |         | v      |         | None    |                  |
| Mode              |         | v      |         | None    |                  |
| Percentile        |         | v      |         | None    |                  |
| Sum               |         | v      |         | 0       | v                |
| SumOrNone         |         | v      |         | None    | v                |
| TopK              |         | v      |         | None    |                  |
| Dict              |         |        | v       | None    |                  |
| DictArray         |         |        | v       | None    |                  |
| DictCount         |         | v      | v       | None    |                  |
| DictCountDistinct |         |        | v       | None    |                  |
| DictFirst         |         |        | v       | None    |                  |
| DictLast          |         |        | v       | None    |                  |
| DictMax           |         |        | v       | None    |                  |
| DictMin           |         |        | v       | None    |                  |
| DictSum           |         |        | v       | None    |                  |
| DictSumOrNone     |         |        | v       | None    |                  |



