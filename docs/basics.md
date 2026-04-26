# Basics

The idea behind this library is to allow you to dynamically build data
transforms, which can be compiled to ad-hoc Python functions.

This means that we need to introduce `convtools` primitives for the most basic
Python operations first, before we can get to a more complex things like
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

1. you define data transforms using its building blocks (_conversions_)
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

Note that `c.item(x)` is shorthand for `c.this.item(x)` - it operates on the
input data by default, just like `c.this` does.

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

Should you need to suppress `KeyError`, `IndexError` and `TypeError` to achieve
`dict.get(key, default)`-like behavior but for arbitrary data:

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

Should you need to suppress `AttributeError`, pass `default` argument.

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
parameters to them.

Let's update our "increment" function to have a keyword-only `increment`
parameter:

```python
def f(data, *, increment):
    return data + increment
```


To build a conversion like this use `c.input_arg("increment")` to reference the
keyword argument to be passed:

{!examples-md/getting_started__input_arg.md!}

#### When to use c.naive vs c.input_arg

- **`c.naive`**: Use when the value is known at converter creation time and
  won't change between calls (lookup tables, configuration constants, helper
  functions).
- **`c.input_arg`**: Use when the value varies per call (runtime parameters,
  user-provided configuration, dynamic thresholds).


## Placeholders & Special References

Some conversions change what "current input" means. For example, inside
`c.iter(...)`, `c.this` refers to the current element, while in a join condition
`c.LEFT` and `c.RIGHT` refer to the current pair of rows being matched.

| Reference | Where to use it | What it points to |
| --------- | --------------- | ----------------- |
| `c.this` | Anywhere | The current conversion input. Inside iterable helpers and comprehensions, this is the current item. |
| `c.naive(value)` | Anywhere | A value or function known when the converter is built and exposed to generated code. |
| `c.input_arg("name")` | Anywhere | A runtime argument of the generated converter. By default these become keyword-only arguments unless `signature=` is customized. |
| `c.label("name")` | After labeling data with `add_label`, `label_input`, or `label_output` | The previously saved value for that label. |
| `c.LEFT` / `c.RIGHT` | `c.join(...)` conditions and table joins | The current left and right rows being compared. |
| `c.CHUNK` | `c.chunk_by_condition(...)` | The current accumulated chunk while deciding whether the next item belongs to it. |
| `c.PREV` | `c.cumulative(...)` reduce expressions | The previous cumulative value. |

Reducers and window expressions also use context-specific inputs. Reducer
arguments such as `c.ReduceFuncs.Sum(c.item("amount"))` are evaluated against
each input row. Window conversions follow the same pattern for row expressions,
while window functions themselves are provided by `c.WindowFuncs`.


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

**Recommendation:** For most cases, prefer `c.call_func` or
`c.naive(func)(...)`. Both avoid repeated attribute lookups and produce
cleaner generated code.

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

Sometimes it's required to adjust the automatically generated converter
signature. `gen_converter` accepts several parameters for this:

1. `method=True` - prepends `self`, producing a signature like
   `def converter(self, data_)`
1. `class_method=True` - prepends `cls`, producing a signature like
   `def converter(cls, data_)`, and returns a `classmethod`
1. `signature="..."` - uses the provided function signature verbatim
1. `debug=True` - prints and dumps generated code for this converter
1. `converter_name="..."` - changes the generated function name prefix

The generated converter uses `data_` as the input variable. Include `data_` in
custom `signature=` values when the conversion reads the input. Also include
any names referenced with `c.input_arg("name")`; otherwise converter generation
raises an error before compiling the function.

{!examples-md/getting_started__signature.md!}


## Debug

When you need to debug a conversion, enable debug mode to inspect the generated
Python code. There are 2 ways:

1. pass `debug=True` to `gen_converter` or `execute` for one converter build
1. set `options.debug = True` inside `c.OptionsCtx()` for a scoped block of
   converter builds

`c.OptionsCtx` is thread-local and restores the previous options when the
`with` block exits. It currently supports one option:

| Option | Default | Meaning |
| ------ | ------- | ------- |
| `debug` | `False` | Print generated code during compilation, format it with `black` when installed, and dump generated source files for debugger tracebacks. |

Passing `debug=True` to `gen_converter` temporarily enables the same debug
option for that converter and any nested converter functions it generates.
Passing `debug=True` to `execute` is a shortcut for generating a debug
converter and immediately calling it.

Generated source files are written to the directory from
`PY_CONVTOOLS_DEBUG_DIR`, or to `py_convtools_debug` inside Python's temporary
directory when the environment variable is not set. Sources are also dumped if
generated code raises an exception, so tracebacks can point to readable files.

{!examples-md/getting_started__debug.md!}

Here is a small example of the kind of code `debug=True` prints:

```python
def _converter(data_):
    try:
        return [
            {
                "id": _i["id"],
                "total": (_i["qty"] * _i["price"]),
            }
            for _i in data_["orders"]
        ]
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise
```

For interactive debugging, use the `breakpoint` conversion:

```python
c({"a": c.breakpoint()}).gen_converter(debug=True)
# same
c({"a": c.item(0).breakpoint()}).gen_converter(debug=True)
```

`c.breakpoint()` wraps the intermediate value, stops at that point, and returns
the value unchanged when execution continues. On Python 3.7+ it calls the
built-in `breakpoint()`, on older Python versions it falls back to
`pdb.set_trace()`, and when `pydevd` is already loaded it uses `pydevd.settrace()`
for IDE debuggers.


## Inline expressions

/// admonition
    type: warning
`convtools` cannot guard you here and doesn't infer any insights from the
attributes of unknown pieces of code. Avoid using if possible.

**Risks:**

- **Code injection**: Never pass untrusted user input to inline expressions -
  they are executed as Python code.
- **Bypasses optimizer**: Inline code cannot be analyzed or optimized by
  convtools.
- **Harder to debug**: Errors in inline expressions produce less helpful
  tracebacks.
///

There are two ways to pass custom code expression as a string:

1. `c.escaped_string`
1. `c.inline_expr`


{!examples-md/api__inline_n_escaped.md!}


**Now that we know the basics and how the thing works, we are ready to go over
more complex conversions in a more cheatsheet-like narrative.**
