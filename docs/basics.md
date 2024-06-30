# Basics

The idea behind this library is to allow you to dynamically build data
transforms, which can be compiled to ad-hoc python functions.

This means that we need to introduce `convtools` primitives for the most basic
python operations first, before we can get to a more complex things like
aggregations and joins.

## c.this

To start with, here is a function which increments an input by one:
```python
def f(data):
    return data + 1
```

If we called `data` as `c.this`, then this data transform would look like:
`c.this + 1`. And this is a correct `convtools` conversion.

So the steps of getting a converter function are:

1. you define data transforms using it's building blocks (_conversions_)
1. you call ``gen_converter`` conversion method to generate ad-hoc code and
   compile a function, which implements the transform you just defined
1. you use the resulting function as many times as needed

{!examples-md/getting_started__this.md!}

Many examples will contain `debug=True` just so the generated code is visible
for those who are curious, not because it's required :)

If we need a converter function to run it only once, then we can shorten it to:

{!examples-md/getting_started__this_execute.md!}


## c.item

Of course the above is not enough to work with data. Let's define conversions
to perform key/index lookups.

#### No default

```python
def f(data):
    return data[1]
```

There are two ways to do it:

1. `c.this.item(1)` - to build on top of the previous example
1. `c.item(1)` - same, but shorter


{!examples-md/getting_started__item.md!}

#### With default

Should you need to suppress `KeyError` to achieve `dict.get(key, default)`
behavior:

{!examples-md/getting_started__item_default.md!}


#### Multiple indexes / keys

Sometimes you may need to perform multiple subsequent index/key lookups:

{!examples-md/getting_started__item_multi.md!}


## c.attr

Just like the `c.item` conversion takes care of index/key lookups, the
`c.attr` does attribute lookups. So to define the following conversion:

```python
def f(data):
    return data.value
```

just use `c.attr("value")`.

Here is all-in one example:

{!examples-md/getting_started__attr.md!}


## c.naive

In fact we implicitly used `c.naive` when we implemented the increment
conversion. It is used to make objects/functions/whatever available inside
conversions.

A good example is when we need to achieve something like the following:

```python
VALUE_TO_VERBOSE = {
    1: "ACTIVE",
	2: "INACTIVE",
}
def f(data):
    return VALUE_TO_VERBOSE[data]
```
here we made `VALUE_TO_VERBOSE` available to the function. To build an
equivalent conversion wrap an object to be exposed into `c.naive`:

{!examples-md/getting_started__naive.md!}

_And yes, you can pass conversions as arguments to other conversions (notice
`.item(c.this)` part)._


## c.input_arg

Given that we are generating functions, it is useful to be able to add
parameters to them. Let's update our "increment" function to have a
keyword-only `increment` parameter:

```python
def f(data, *, increment):
    return data + increment
```


To build a conversion like this use `c.input_arg("increment")` to reference the
keyword argument to be passed:

{!examples-md/getting_started__input_arg.md!}


## Calling functions

One of the most important primitive conversions is the one which calls
functions. Let's build a conversion which does the following:

```python
from datetime import datetime

def f(data):
    return datetime.strptime(data, "%m/%d/%Y")
```

We can either:

1. use `c.call_func` on `datetime.strptime`
1. use `call_method` on `datetime`
1. expose `datetime.strptime` via `c.naive` and then call it

{!examples-md/getting_started__call.md!}

/// admonition
    type: tip

If we think about which one is faster, have a look at the generated code.
That extra `.strptime` attribute lookup in the 2nd variant makes it slower,
while both other variants perform this lookup only once at conversion
building stage and wouldn't perform it if we stored the converter for
further reuse.
///

#### calling with `*args`, `**kwargs`

Of course this is slower because on every call `args` and `kwargs` get rebuilt,
but sometimes you cannot avoid such calls as `f(*args, **kwargs)`. The options
are:

1. `c.apply_func`
1. `apply_method`
1. `apply`

{!examples-md/getting_started__apply.md!}


## Operators

{!examples-md/api__operators.md!}

## Converter signature

Sometimes it's required to adjust automatically generated converter signature,
there are three parameters of `gen_converter` to achieve that:

1. `method` - results in signature like `def converter(self, data_)`
1. `class_method` - results in signature like `def converter(cls, data_)`
1. `signature` - uses the provided signature

just make sure you to include `data_` in case your conversion uses the input.

{!examples-md/getting_started__signature.md!}


## Debug

When you need to debug a conversion, the very first thing is to enable debug
mode. There are 2 ways:

1. pass `debug=True` to either `gen_converter` or `execute` methods
2. set debug options using `c.OptionsCtx` context manager

_In both cases it makes sense to install `black` code formatter (`pip install
black`), it will be used automatically once installed._

{!examples-md/getting_started__debug.md!}

Another way to debug is to use `breakpoint` method:

```python
c({"a": c.breakpoint()}).gen_converter(debug=True)
# same
c({"a": c.item(0).breakpoint()}).gen_converter(debug=True)
```


## Inline expressions

/// admonition
    type: warning
`convtools` cannot guard you here and doesn't infer any insights from the
attributes of unknown pieces of code. Avoid using if possible.
///

There are two ways to pass custom code expression as a string:

1. `c.escaped_string`
1. `c.inline_expr`


{!examples-md/api__inline_n_escaped.md!}


**Now that we know the basics and how the thing works, we are ready to go over
more complex conversions in a more cheatsheet-like narrative.**
