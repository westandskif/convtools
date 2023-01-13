# Group By and Aggregate

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

The syntax to define aggregations is as follows:

 * `c.group_by(key1, key2, ...).aggregate(result)` returns list of results
 * `c.aggregate(result)` returns the result

where `result` is any conversion (_`dict`, `c.call_func`, whatever_) made up
of:

 * keys - `key1, keys, ...`
 * reducers - e.g. `c.ReduceFuncs.Sum(c.item("abc"))`


## c.ReduceFuncs

Here is the list of available reducers like `c.ReduceFuncs.Sum`:

    * Sum - auto-replaces False values with 0; default=0
    * SumOrNone - sum or None if at least one None is encountered; default=None
    * Max - max not None
    * MaxRow - row with max not None
    * Min - min not None
    * MinRow - row with min not None
    * Count - count of everything
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

	DICT REDUCERS ARE IN FACT AGGREGATIONS THEMSELVES, BECAUSE VALUES GET REDUCED.
    * Dict
	    c.ReduceFuncs.Dict(c.item("key"), c.item("x"))
    * DictArray - dict values are lists of encountered values
    * DictSum - values are sums
    * DictSumOrNone
    * DictMax
    * DictMin
    * DictCount
    * DictCountDistinct
    * DictFirst
    * DictLast

	AND LASTLY YOU CAN DEFINE YOUR OWN REDUCER BY PASSING ANY REDUCE FUNCTION
	OF TWO ARGUMENTS TO ``c.reduce``.

Every reducer keyword arguments:

 * `where` - a condition to filter input values of a reducer
 * `default` - a value in case a reducer hasn't encountered any values

## c.group_by

{!examples-md/welcome__group_by.md!}

## c.aggregate

{!examples-md/welcome__aggregations.md!}
