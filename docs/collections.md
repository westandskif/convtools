# Collections

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

## Collections and `c()` wrapper

The syntax to create a conversion, which builds a `dict`, `list`, `tuple` or a
`set` is as follows: `c({"a": 1})` - just wrap in a `c` call.

Let's build a dict from a tuple of two integers:

{!examples-md/api__collections.md!}

**So to summarize on `c()` wrapper, it:**

* leaves conversions untouched
* interprets collections as conversions which are to build such collections
* wraps everything else in `c.naive`.

#### Optional items

It's possible to mark a particular item as optional, so it disappears from an
`dict`/`list`/`tuple`/`set` in certain cases:

{!examples-md/api__collections_optional.md!}


## Operators and fundamental methods

{!examples-md/api__operators.md!}


## Type casting

To cast to a type use a naive conversion method `as_type`:

{!examples-md/api__as_type.md!}

!!! note
	It may seem useless as it can be replaced with piping the result to `list`
	function or just to calling `list` function directly, but in fact some
	conversions override this method to achieve predicate-pushdown-like
	optimizations.


## Iterators & Comprehensions

#### Process

To iterate an input, there are the following conversions:

* `c.iter` and `iter` method
* `c.list_comp`
* `c.dict_comp`
* `c.tuple_comp`
* `c.set_comp`.

Each of them accepts `where` argument to support conditions like:
`[x for x in items if x > 10]`.

A few examples:
{!examples-md/api__comp.md!}

!!! note
	It's important to note that a conversion passed into `iter`, `list_comp`
	and other iteration methods defines the conversions of each element of
	the input collection. This is one of the input-switching conversions.


#### filter

To filter an input use `c.filter` or `filter` conversion method:

{!examples-md/api__filter.md!}


#### sort

`sort` method is a shortcut to `c.call_func(sorted, c.this, ...)`

{!examples-md/api__sort.md!}


#### zip, repeat, flatten

Whenever you need to annotate something or just zip sequences, it's convenient
to have these shortcuts/helpers:

1. `c.zip`
1. `c.repeat`
1. `flatten` method

{!examples-md/api__zip_repeat_flatten.md!}

`c.zip` supports keyword arguments to build dicts:

{!examples-md/api__zip_to_dict.md!}


#### len, min, max

1. `c.this.len()`: shortcut to `c.this.pipe(len)` or `c.call_func(len, c.this)`
1. `c.max`: shortcut to `c.call_func(max, ...)`
1. `c.min`: shortcut to `c.call_func(min, ...)`


#### chunk_by, chunk_by_condition

It's a common task to chunk a sequence by: values, chunk size, condition or
combination of them. Here are two conversions to achieve this:

1. `c.chunk_by(*by, size=None)`
1. `c.chunk_by_condition(condition)` - it takes the condition as a conversion
   of an element (`c.this`) and the existing chunk (`c.CHUNK`)

{!examples-md/api__chunk.md!}

We'll cover aggregations later, but bear with me -- chunk conversions have
`aggregate` method:

{!examples-md/api__chunk_aggregate.md!}


#### take_while, drop_while

1. `take_while` reimplements `itertools.takewhile` - terminates once condition
   evaluates to false
1. `drop_while` reimplements `itertools.dropwhile` - yields elements starting
   from the first one where condition evaluates to true

{!examples-md/api__take_drop_while.md!}


#### iter_windows

`c.iter_windows` iterates through an iterable and yields tuples, which are
obtained by sliding a window of a given width and by moving the window by
specified step size as follows: `c.iter_windows(width=7, step=1)`

{!examples-md/api__iter_windows.md!}

#### cumulative

`cumulative(prepare_first, reduce_two, label_name=None)` method allows to
define cumulative conversions.

 * `prepare_first` defines conversion of the first element
 * `reduce_two` defines conversion of two elements

{!examples-md/api__cumulative.md!}

In cases where the value in accumulator needs to be cleared, usually it happens
in nested iterators, take 2 steps:

1. label your cumulative
1. use `c.cumulative_reset` to reset where necessary

{!examples-md/api__cumulative_2.md!}
