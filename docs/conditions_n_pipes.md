# Conditions and Pipes

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

## Conditions

There are 2 conversions which allow to define conditions:

1. `c.if_(condition, if_true, if_false)` for a single condition
1. `c.if_multiple(*condition_to_value_pairs, else_)` obviously for multiple conditions

{!examples-md/api__if.md!}


## Check and raise

There's a convenient helper, which checks whether a condition is met and
returns input as is or raises `c.ExpectException` otherwise:

1. `c.expect(condition, error_msg=None)`
2. also as a method: `c.attr("amount").expect(c.this < 10, "too big")`

{!examples-md/api__expect.md!}

## Pipes

Pipe is the most important conversion which allows to pass results of one
conversion to another. The syntax is simple: `first.pipe(second)`.

{!examples-md/api__pipe.md!}

You can also pipe to callables, have a look at its signature:
`pipe(next_conversion, *args, label_input=None, label_output=None, **kwargs)`.
It accepts `*args` and `**kwargs`, which are passed to a callable after pipe
input:

{!examples-md/api__pipe_callable.md!}

#### and_then

`and_then(conversion, condition=bool)` method applies provided conversion if
condition is true (by default condition is standard python's truth check).
`condition` accepts both conversions and callables.

{!examples-md/api__and_then.md!}

#### Labels

!!! warning
	Despite the fact that `convtools` encourages a functional approach and
	working with immutable data, sometimes it's inevitable to use global
	variables. Anyway avoid using labels if possible.

There are two ways to label data for further use:

1. `pipe` method accepts `label_input` (_applies to pipe's input data_) and
   `label_output` (_applies to the end result_) keyword arguments, each of them
   is either:
    * `str` - label name
	* `dict` - label names to conversion map. Labels are put on results of
	  conversions.
1. `add_label` - shortcut to `pipe(This, label_input=label_name)`

To reference previously labeled data use `c.label("label_name")`.

{!examples-md/api__pipe_labels.md!}

## Dispatch

!!! warning ""
    Experimental feature added on Feb 7, 2024. It will be stabilized in ~ half
    a year.

There are performance critical cases where it's desired to replace `c.if_` and
`c.if_multiple` with dict lookups. However it limits what can be used as keys
as these need to be hashable.

Interface: `c.this.dispatch(key, key_to_conv, default)`

1. `key` defines a conversion, which gets a key
1. `key_to_conv` is a dict which maps keys to conversions
1. `default` is an optional default conversion, when the dict doesn't contain
   the key

{!examples-md/api__dispatch.md!}
