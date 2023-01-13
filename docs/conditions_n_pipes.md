# Conditions and Pipes

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

## Conditions

There are 2 conversions which allow to define conditions:

1. `c.if_(condition, if_true, if_false)` for a single condition
1. `c.if_multiple(*condition_to_value_pairs, else_)` obviously for multiple conditions

{!.examples/api__if.md!}


## Pipes

Pipe is the most important conversion which allows to pass results of one
conversion to another. The syntax is simple: `first.pipe(second)`.

{!.examples/api__pipe.md!}

You can also pipe to callables, have a look at its signature:
`pipe(next_conversion, *args, label_input=None, label_output=None, **kwargs)`.
It accepts `*args` and `**kwargs`, which are passed to a callable after pipe
input:

{!.examples/api__pipe_callable.md!}

#### and_then

`and_then(conversion, condition=bool)` method applies provided conversion if
condition is true (by default condition is standard python's truth check).
`condition` accepts both conversions and callables.

{!.examples/api__and_then.md!}

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

{!.examples/api__pipe_labels.md!}
