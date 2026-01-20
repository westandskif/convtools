## 1.17.0 (2026-01-21)

- sped up `in_` and `not_in` in cases where static single-item sequence is passed
- added new c.ReduceFuncs: FirstN, LastN, DictFirstN, DictLastN

## 1.16.0 (2026-01-20)

**Features**

- added `fill_value` parameter to `Table.explode` for customizing padding when exploding multiple columns

**Bugfix**

- fixed `c.if_multiple` to correctly calculate `number_of_input_uses` and `total_weight` for short-circuit evaluation

## 1.15.0 (2026-01-18)

**Features**

- added `c.spread` conversion for spreading/unpacking collections into parent structures
- added `c.zip_longest` conversion matching Python's `itertools.zip_longest`
- added statistical reducers: `c.ReduceFuncs.Variance`, `c.ReduceFuncs.StdDev`, `c.ReduceFuncs.Covariance`, `c.ReduceFuncs.Correlation`
- added multi-column support to `Table.explode` with `zip_longest` semantics

**Bugfix**

- fixed `c.ReduceFuncs.Percentile` and `c.ReduceFuncs.Median` to work with `Decimal` values
- fixed `c.breakpoint` sending generated code to stdout when debug is not explicitly requested
- fixed `.asc()` and `.desc()` mutating `c.this` instead of creating a new conversion
- fixed `c.join` full join for cases with same reference objects

## 1.14.8 (2025-10-23)

- updated tests, Github Actions and pyproject.toml for Python 3.14

## 1.14.7 (2025-09-21)

- fixed `Table.pivot` for cases with prior table mutations

## 1.14.6 (2025-08-10)

- **fixed the following c.ReduceFuncs so they skip `None` values** just like `Min`, `Max`:
    * `Average`
    * `Percentile`
    * `TopK`
    * `CountDistinct`
    * `DictCountDistinct`
- documented whether reducers skip `None` in [Aggregations / Reducers API](./aggregations.md#reducers-api)


## 1.14.5 (2025-07-31)

- **fixed memory leaks `c.item` and `c.attr` with `default`**, which were sped up
in v1.12+ py3.10+
- stopped suppressing exceptions other than `(TypeError, KeyError, IndexError)`
for `c.item` with `default`
- stopped suppressing exceptions other than `AttributeError` `c.attr` with
`default`

## 1.14.4 (2025-03-19)

- fixed CSE (common subexpression elimination) for aggregations (used to raise
UndefinedError)

## 1.14.3 (2024-09-04)

- improved CSE (common subexpression elimination) dict c.ReduceFuncs

## 1.14.2 (2024-09-04)

- improved CSE (common subexpression elimination) for `c.group_by` mode

## 1.14.1 (2024-09-01)

- python 3.13t (free threading) support

## 1.14.0 (2024-09-01)

- added `c.unordered_chunk_by`
- added short paths for `Sum` and `DictLast` in single-reducer cases of
`c.aggregate`

## 1.13.2 (2024-08-29)

- sped up code generation for aggregations

## 1.13.1 (2024-08-28)

- sped up aggregations by CSE (common subexpression elimination)

## 1.12.2 (2024-08-22)

- fixed `c.this.datetime_parse` with default when uncovered data remains

## 1.12.1 (2024-07-14)

- sped up `c.item(..., default=...)` for python 3.10+ by a c-extension

## 1.11.0 (2024-07-01)

- added experimental `c.this.window(...).over(...)` and `c.WindowFuncs`
- added experimental support of `key` as conversion or tuple of conversions to
`c.sort` and `c.this.sort`
    * `c.this.asc(none_last=None, none_first=None)`
    * `c.this.desc(none_last=None, none_first=None)`
    * `c.sorting_key(*keys)` standalone helper to generate callables for
      `sorted`'s `key` parameter
- improved `Table.from_rows` not to raise StopIteration on empty sequences when
no header inference is required


## 1.10.1 (2024-06-11)

- fixed `Table.join` for dict-based rows after `rename` usage (_no breaking
changes as it used to break completely_)

## 1.10.0 (2024-06-07)

- added experimental `of_` parameter to `c.Mut.set_item`, `c.Mut.set_attr`,
`c.Mut.del_item`, `c.Mut.del_attr` to mutate non-root objects

## 1.9.0 (2024-06-05)

- added experimental `Table.pivot` method

## 1.8.0 (2024-03-06)

- added experimental `Table.wide_to_long` method

## 1.7.0 (2024-02-21)

- added experimental `c.try_(conv).except_(exc_def, value, re_raise_if=None)`
  conversion to handle exceptions

## 1.6.0 (2024-02-07)

- added experimental `c.this.dispatch(key, key_to_conv, default)` to switch
  between conversions based on dict lookups


## 1.5.1 (2023-10-08)

- added python 3.12 benchmark results
- added python 3.12 heuristics

## 1.5.0 (2023-07-30)

**Features**

- added `c.format_dt()` and `(...).format_dt()`: speed optimized implementation
  of `datetime.strftime`

**Misc**

- added "Benefits" section to the docs, added performance benchmarks to docs


## 1.4.0 (2023-06-28)

**Features**

- added optional `if_exists=True` parameter to `c.Mut.del_item` and
  `c.Mut.del_attr`

    * `c.Mut.del_item("d", if_exists=True)` drops `"d"` key if it exists

## 1.3.0 (2023-04-11)

**Features**

- added `__pow__` operator and corresponding `c.this.pow(...)` method
- added `c.expect(condition, error_msg=None)` and `c.this.expect(...)` method
  which check input for condition and raises `c.ExpectException` if condition
  fails

## 1.2.0 (2023-04-10)

**Deprecations**

- The following reducers never really worked with `initial` keyword argument
  because the underlying data structure was never exposed and this led to
  undefined behavior. Until `v2.0` such reducers with `internals_are_public ==
  False` will ignore `initial`, in `v2.0` if `initial` is passed, they will
  raise `ValueError`:

```
   * ArrayDistinct
   * CountDistinct
   * First
   * Last
   * MaxRow
   * MinRow
   * ArraySorted
   * Dict
   * DictArray
   * DictArrayDistinct
   * DictCount
   * DictCountDistinct
   * DictFirst
   * DictLast
   * DictMax
   * DictMin
   * DictSum
   * DictSumOrNone
```

**Bugfix**

- now `c.ReduceFuncs.Count()` counts rows, while `c.ReduceFuncs.Count(c.this)`
  counts not `None` values; both of these used to calculate rows (like SQL's
  `count(*)`)
- now `c.ReduceFuncs.DictCount(c.this)` counts rows, while
  `c.ReduceFuncs.DictCount(c.item("key"), c.item("value"))` counts not `None`
  values; both of these used to calculate rows (*like SQL's `count(*)`*)


## 1.1.2 (2023-03-27)

**Bugfix**

- fixed `c.naive` internals to work with `pypy`

## 1.1.1 (2023-03-27)

**Misc**

- weakened python version requirements: changed `">=3.6,<3.12"` to `">=3.6"`

## 1.1.0 (2023-03-24)

**Features**

- added `default` to `c.date_parse` and `c.datetime_parse` to return when no
  formats fit


## 1.0.0 (2023-03-23)

**Misc:**

- stabilized API

**BREAKING CHANGES:**

- renamed all non-public modules so the only supported way to import is
  directly from "convtools", e.g.:

    * `from convtools import conversion as c`
    * `from convtools import DateGrid, DateTimeGrid`

- contrib ones are left as is:

    * `from convtools.contrib.tables import Table`
	* `from convtools.contrib.fs import split_buffer`

## 0.42.4 (2023-03-22)

**Misc**

- locked CI dependencies
- switched packaging to hatch
- dropped setup.py and setup.cfg in favor of pyproject.toml


## 0.42.3 (2023-03-15)

**Bugfix**

- fixed `c.group_by` for cases with input_arg/label inside and
  iter/as_type/sort/tap methods called on it

## 0.42.2 (2023-03-14)

**Bugfix**

- fixed `c.group_by` for cases where group by keys are generated functions
  (e.g. deep attr lookup with default). No worries about silent errors, it used
  to fail hard.

## 0.42.1 (2023-02-20)

**Bugfix**

- fixed `Table.join` for cases where the right part has internal row type
  different from the left one

## 0.42.0 (2023-01-29)

**Features**

- introduced `c.iter_unique(element_conv=None, by_=None)` and
  `(...).iter_unique` methods which define a conversion, which iterates over
  the input and yields values unique based on the provided condition

## 0.41.0 (2023-01-16)

**Features**

- introduced `c.date_parse` / `c.datetime_parse` shortcut and extension of
  `datetime.strptime`
- introduced `c.date_trunc` / `c.datetime_trunc` to truncate dates to years,
  months, days-of-week, etc. (including multiples of them like quarters -
  `3mo`). Support offsets.
- introduced `DateGrid` / `DateTimeGrid` helpers to build gap-less series of
  dates/datetimes. Support offsets.


## 0.40.2 (2022-12-19)


**Misc**

- updated pipe inlining weights
- added initial set of benchmarks to catch regressions

## 0.40.1 (2022-12-19)

**Bugfix**

- fixed group by code generation: unnecessary comprehension condition


## 0.40.0 (2022-12-18)

**Misc**

- simplified inner group by code generation
- updated ``c.group_by``, ``(...).pipe`` and comprehensions to delegate method
  calls to their internals where possible
- updated internals of code generation, fixed random seed for reproducible code
  generation
- internally replaced ``FilterConversion`` with ``c.iter``
- added internal ``(...).to_iter()`` method (may become public later, once
  documented)


## 0.39.0 (2022-12-06)

**Misc**

- reworked ``c.join`` so it has its custom simpler implementation
  (on python 3.9 it has become approximately 1.62x, 1.95x, 2.15x times faster
  for inner, left and full joins correspondingly)

## 0.38.0 (2022-10-26)

**Features**

- introduced cumulative conversions: ``c.iter(c.cumulative(c.this, c.this + c.PREV))``
- introduced ``c.if_multiple((c.this < 0, c.this * 10), (c.this == 0, None), else_=5)``

## 0.37.0 (2022-09-29)

**BREAKING CHANGES:**

- changed signature: ``(...).add_label(label_name: t.Union[str, dict],
  conversion)`` to ``(...).add_label(label_name: t.Union[str, dict])``. The
  reason is that it had confusing behavior of applying the conversion after
  labeling.


## 0.36.0 (2022-09-20)

**contrib.tables:**

- added ``Table.explode`` method to explode a table to a long format by
  exploding a column with iterables

## 0.35.0 (2022-09-18)

**DROPPED Experimental - contrib.models**

One day this may become a separate lib (if pydantic v2 turns to be not what it
claims to be), but not today while all python `typing` internals are unstable.

## 0.34.0 (2022-07-26)

**contrib.tables:**

- updated ``Table`` to support ellipsis to signify other non-mentioned columns
  so it's possible to easily re-arrange columns like this:
  ``table.take("c", ...)`` / ``table.take(..., "a", "b")``

## 0.33.2 (2022-07-22)

**Bugfix**

- fixed ``c.iter_windows`` for empty collection cases

## 0.33.1 (2022-07-14)

**Experimental - contrib.models**

- fixed ``ProxyObject`` to properly forward __getattr__ calls to a wrapped
  object (required in cases where cyclic dependencies exist)

## 0.33.0 (2022-07-14)

**Experimental - contrib.models**

- [BREAKING] contrib.models: renamed ``cached_model_method`` to
  ``cached_model_classmethod``
- contrib.models ``cached_model_classmethod`` now allows to call it from
  sibling class methods (it no longer requires version parameter, its signature
  now is ``cls, data``)

## 0.32.0 (2022-07-12)

**Features**

- introduced ``c.iter_windows(width=7, step=1)`` / ``(...).iter_windows(...)``
  conversions, which iterate through an iterable and yield windows as tuples


## 0.31.0 (2022-07-06)

**Experimental - contrib.models**

- added Enum validator, e.g. ``validators.Enum(UserDefinedEnum)`` to check
  whether an object is a valid value of a provided Enum subclass

## 0.30.0 (2022-07-06)

**Experimental - contrib.models**

- added length validator, e.g. ``validators.Length(min_length=1, max_length=2)``

## 0.29.0 (2022-07-05)

- updated ``DictArray``, ``DictSum``, ``DictSumOrNone`` so they don't rebuild
  dicts from defaultdicts (only setting default_factory to None, so
  defaultdicts start raising KeyErrors like regular dicts)
- changed ``c.naive`` conversion logic so it supports pre-warming its value by
  putting it as a function parameter with a default value (conversions are not
  obliged to use naive pre-warming; if they don't request it, they will deal
  with global lookups to ``__naive_values__`` dict)

**Experimental - contrib.models**

- updated casters to support expression-mode, where they can be used as a part
  of list/set/dict/tuple comprehension (instead of building these collections
  in a loop in simple cases)
- sped up models
- inlined ``validators.Required``

## 0.28.0 (2022-07-03)

**Experimental - contrib.models**

- added ``typing.Set`` support
- added ``X | Y`` type support (PEP 604 - Python 3.10+)
- added ``list[int]``-like type definition support (Python 3.9+)

## 0.27.0 (2022-07-01)

**Experimental - contrib.models**

- added ``a: bool = cast()`` support
- added ``typing.Literal`` support

## 0.26.0 (2022-06-30)

**Experimental - contrib.models**

- reworked errors, returned by ``build`` and ``build_or_raise`` to allow for
  automated errors processing (now it's clear where path ends and error info
  starts)
- now ``cast`` not only supports casters, but complex types too:
  ``cast(t.List[t.Tuple[int]])``
- now it's possible to force all-field casting on a model level via ``Meta.cast
  = True`` class field
- ``build`` and ``build_or_raise`` can also force children casting via
  ``cast=True`` parameter (doesn't affect inner models as they have their own
  controls)
- now casting supports type-to-caster(s) overrides like:
  ``cast(overrides={date: casters.DateFromStr("%m/%d/%Y")})``,
  ``Meta.cast_overrides`` and ``build(..., cast_overrides={date: [...]})``
- added ``validators.Decimal(max_digits, decimal_places)``
- extended str caster to decode bytes and supported custom encodings like
  ``casters.Str("utf-16")``
- added quantization support to ``casters.DecimalLossy(quantize_exp, rounding)``
- added ``typing.Tuple`` support (both validation and casting)

**Misc:**

- updated `c.or_` and `c.and_` to better flatten nested constructions


## 0.25.2 (2022-06-24)

**Bugfix**

- fixed ``.gen_converter(class_method=True)``, broken in v0.25.0 where callable
  wrapper was eliminated. Now it returns a converter, wrapped with
  ``classmethod``

## 0.25.1 (2022-06-24)

**Bugfix**

- fixed label bug in case of nested pipes, introduced in 0.24.1: was leading to
  label key errors since labels were skipping initialization


## 0.25.0 (2022-06-22)

**Experimental features:**

- introduced data validation models: ``convtools.contrib.models.DictModel``
  (accesses keys and indexes) and ``convtools.contrib.models.ObjectModel``
  (accesses attributes and indexes)

**Misc**

- reworked converter generation to store generated code inside the main context
- eliminated converter wrapper, which was a callable, taking care of dumping
  generated source code to tmpdir in cases of exceptions. Now converters take
  care of this themselves.
- now long list/dict/tuple/set literal definition code includes newlines, so
  it's easier to debug in case of exception


## 0.24.1 (2022-05-29)

**Misc**

- forced pipes to inline if labels of "what" conversion cannot affect "where"
  label usage


## 0.24.0 (2022-05-29)

**Features**

- introduced ``convtools.contrib.fs`` helpers: ``split_buffer`` and
  ``split_buffer_n_decode`` to close the gap in Python's ``open``
  functionality, related to "newlines" (it doesn't support custom ones in text
  mode and doesn't support any in binary one).

**Misc**

- reworked and improved the way function args are collected during code
  generation, now it better understands which variables need to be passed
- reworked aggregates so they don't generate code twice (one for aggregation
  phase, another for result collection phase)
- improved pipes to better understand when they can inline the code and when
  it's beneficial to pass a complex input to a function and then use it
  multiple times without recalculations
- now pipes use estimated conversion weights (which correlate with computation
  costs), inferred for every Python version supported
- optimized dependency tracking to omit trivial ones, while still collecting
  content types as a bitmask
- reduced number of function calls, when using magic methods
- improved ``GetItem`` conversion so it can use hardcoded versions of functions
  in trivial cases and cache converters in almost-trivial ones; stopped
  catching ``AttributeError`` when run with default
- improved ``GetAttr`` conversion to inline attr lookups instead of ``getattr``
  calls where possible; stopped catching ``(TypeError, KeyError, IndexError)``


## 0.23.3 (2022-03-11)

**Bugfix**

- fixed long existing bug in aggregations in cases where multiple reducers get
  initialized at different moments, e.g. the first reducer collects min values
  of column "a", while the second reducer collects max values of column "b",
  "min a" may get initialized earlier than "max b" and then this would raise
  ``Exception``

## 0.23.2 (2022-03-10)

**Bugfix**

- fixed ``c.attr("a", default=None).attr("b", default=None)`` (preferred
  ``c.attr("a", "b", default=None)`` was working though)
- fixed too-many-parenthesis error for long chains of ``and_``, ``or_`` and
  ``==``

## 0.23.1 (2022-02-23)

**Misc**

- allowed passing callables to ``and_then`` so they are called with input as an
  argument
- made ``and_then`` handle the default case as ``a and conv(a)`` not ``if``


## 0.23.0 (2022-02-22)

**Features**

- added ``c.and_then`` and ``(...).and_then`` shortcut to pipe if condition is
  true, otherwise leave untouched. Supports overriding default ``bool``
  condition.


## 0.22.0 (2022-01-02)

[#16](https://github.com/westandskif/convtools/pull/16)

**Features**

- added ``c.ReduceFuncs.ArraySorted`` reducer
- reworked ``GetItem`` and ``GetAttr`` to cache ``get_or_default`` methods
  based on number of indexes and args
- added support for single column tables (headers are always str still)

**Misc**

- updated internals of arg def handling, made naive and labels optional
- removed ``NamedConversion`` and ``ConversionWrapper`` in favor of new
  ``LazyEscapedString``, ``Namespace`` and ``NamespaceCtx``. This lays better
  groundwork for future use of conversions which generate code around another
  named ones.

## 0.21.0 (2021-12-19)

**Features**

- backward-compatible change: now ``c.this`` is preferred over ``c.this()``
- ``c.and_`` and ``c.or_`` support any number of arguments (used to be 2
  mandatory ones). And also supports ``default: bool = None`` argument to
  control what should happen if no arguments are passed:

    * if None, raises ``ValueError``
    * if false value, returns ``False``
    * if true value, returns ``True``


## 0.20.2 (2021-12-02)


[#14](https://github.com/westandskif/convtools/issues/14)

**Misc**

- improved performance of ``Table.chain``, ``Table.into_iter_rows`` and
  ``Table.into_csv`` methods
- improved performance of ``c.apply_func``

## 0.20.1 (2021-11-29)


[#11](https://github.com/westandskif/convtools/pull/11)

**Features**

- added ``c.chunk_by(c.item("x"), size=100)`` for slicing iterables into chunks
  by element values and/or size of chunk
- added ``c.chunk_by_condition(c.CHUNK.item(-1) - c.this() < 100)`` for slicing
  iterables into chunks based on condition, which is a function of a current
  chunk and a current element
- added ``(...).len()`` shortcut for ``c.call_func(len, c.this())``

**Misc**

- no longer create empty ``labels_`` dict on each converter call where no
  labels are going to be used
- no longer create new ``This`` instances, now reusing an existing one


## 0.19.0 (2021-10-28)

**Features**

[#8](https://github.com/westandskif/convtools/issues/8)

- added ``c.ReduceFuncs.Percentile``
- ``c.reduce`` now accepts conversions as ``initial`` argument, this will be
  resolved on the first row met. If ``initial`` conversion depends on input
  data, it won't be used as ``default`` if default is not provided.
- sped up ``c.ReduceFuncs.Sum`` and ``c.ReduceFuncs.Average`` for cases where
  elements are obviously not None

**BREAKING CHANGES:**

Normally you use ``c.ReduceFuncs.Sum(c.this())`` to reduce something, but it's
possible to use custom reduce functions like this:

* ``c.reduce(lambda x, y: x + y, c.this(), initial=0)``
* ``c.reduce(c.inline_expr("{} + {}"), c.this(), initial=0)``

``c.reduce`` used to support ``prepare_first`` parameter which was adding
confusion. Now it's dropped.

## 0.18.0 (2021-10-24)


**Features**

[#6](https://github.com/westandskif/convtools/issues/6)

- added ``c.take_while`` and ``(...).take_while`` re-implementation of
  ``itertools.takewhile``
- added ``c.drop_while`` and ``(...).drop_while`` re-implementation of
  ``itertools.dropwhile``


## 0.17.0 (2021-10-14)


**Features**

- added ``Table.zip`` method to stitch tables (joining on row indexes)
- added ``Table.chain`` method to put tables together one after another


## 0.16.0 (2021-10-12)


**Features**

- introduced ``Table`` conversions [#3](https://github.com/westandskif/convtools/pull/3)
- added ``c.apply_func``, ``c.apply`` and ``(...).apply_method`` conversions

**Bugfix**

- fixed inner join with inner loop with soft conditions: any condition except
  for ``==`` and ``c.and_``
- fixed piping to callable with further calling pipe methods like ``as_type``,
  ``filter`` and ``sort``

**Misc**

- reworked main converter callable wrapper so that it no longer dumps sources
  onto disk for beautiful stacktraces when the converter returns a generator
  (it used to make them down almost 2 times slower). If such debugging is
  needed, just enable debug. As for simple exceptions, these still dump code to
  disc on Exceptions because this should be cheap.

## 0.15.4 (2021-09-23)

**Bugfix**

- fixed [#2](https://github.com/westandskif/convtools/issues/2): issue with
  input args passed to pipe labels

## 0.15.3 (2021-09-19)

**Misc**

- hard fork


## 0.15.2 (2021-09-17)

**Bugfix**

- fixed passing strings containing ``%`` and ``{`` to ``c.aggregate`` -
- [convtools-ita #34](https://github.com/itechart/convtools/issues/34)


## 0.15.1 (2021-08-08)

**Bugfix**

- replaced ``linecache`` populating code with real dumping generated code to
  files in either ``PY_CONVTOOLS_DEBUG_DIR`` (*if env variable is defined*) or
  to python's ``tempfile.gettempdir``. This adds pydevd support (VS Code and PyCharm debugger).


## 0.15.0 (2021-08-02)

**Features**

- introduced ``c.breakpoint`` and ``(...).breakpoint()`` to simplify debugging long pipelines

**Misc**

- [internals] created a separate conversion for ``c.this()``
- [internals] now ``c.naive`` is a direct init of ``NaiveConversion``
- improved quick start, cheatsheet and api docs

## 0.14.1 (2021-07-12)

**Bugfix**

- fixed piping something complex to ``c.join``

**Misc**

- [internals] reworked aggregate & group_by templating
- [internals] reworked optional items processing


## 0.14.0 (2021-06-27)

**Features**

- introduced ``c.zip``, which supports both args to yield tuples and kwargs to yield dicts
- introduced ``c.repeat`` -- the one from ``itertools``
- introduced ``c.flatten`` -- shortcut for ``itertools.chain.from_iterable``


## 0.13.4 (2021-06-20)

**Bugfix**

- fixed incorrect aggregate (not group_by) results in case of ``where``
  conditions in reducers [convtools-ita #32 ](https://github.com/itechart/convtools/issues/32)

## 0.13.3 (2021-06-14)

[convtools-ita #30 ](https://github.com/itechart/convtools/issues/30)

**Bugfix**

- fixed nested aggregations

**Misc**

- [internals] reworked aggregate & group_by templating


## 0.13.2 (2021-05-27)

**Bugfix**

- fixed join + input_arg case


## 0.13.1 (2021-05-23)

**Bugfix**

[convtools-ita #29 ](https://github.com/itechart/convtools/issues/29)

- fixed right join (conditions were not swapped correctly)


## 0.13.0 (2021-05-16)

**Features**

[convtools-ita #28 ](https://github.com/itechart/convtools/issues/28)

- now ``c.iter`` supports ``where`` parameters just like ``c.generator_comp``:

  * ``c.iter(c.this() + 1, where=c.this() > 0)``

- now it's possible to use ``.pipe`` wherever you want as long as it lets you
  do so, even piping in and out of reducers (``c.ReduceFuncs``)

  * e.g. it will raise an Exception if you try to add labels to a reducer input

- now it's possible to use ``aggregate`` inside ``aggregate`` as long as you
  don't nest reducers


## 0.12.1 (2021-05-13)

**Bugfix**

- fixed sporadic issues caused by code substring replacements (now it uses word
  replacements)


## 0.12.0 (2021-05-10)

**Bugfix - BREAKING CHANGES**

- ``.filter`` was unified across the library to work with previous step results
  only, no longer injecting conditions inside comprehensions & reducers.
  So to pass conditions to comprehensions & reducers, use the following:

```python
# REPLACE THIS
c.ReduceFuncs.Array(c.item("a")).filter(c.item("b") == "bar")
# WITH THAT
c.ReduceFuncs.Array(c.item("a"), where=c.item("b") == "bar")
# if the condition is to be applied before the aggregation
# or leave as is if you want to filter the resulting array
```

- ``c.generator_comp(...).filter(condition)`` no longer pushes condition inside
  the comprehension, the filtering works on resulting generator
  The same applies to:

    * ``c.list_comp``
    * ``c.tuple_comp``
    * ``c.set_comp``
    * ``c.dict_comp``

```python
# REPLACE THIS
c.generator_comp(c.item("a")).filter(c.item("b") == "bar")
# WITH THAT
c.generator_comp(c.item("a"), where=c.item("b") == "bar")
# if the condition is to be put to the IF clause of the comprehension to
# work with the input elements or leave it as is if you want to filter the
# resulting generator
```



## 0.11.2 (2021-05-08)


**Features**

- introduced ``c.sort``  & ``(...).sort`` conversions, which are helpers for
  ``sorted``; this is done for the sake of unification with methods of
  comprehension conversions

**Misc**

- implemented ``GroupBy.filter``, which returns generator of results without
  creating an intermediate list


## 0.11.1 (2021-05-07)

**Bugfix**

- fixed complex conversion cases where there are multiple aggregations
  [convtools-ita #27 ](https://github.com/itechart/convtools/issues/27)


## 0.11.0 (2021-05-06)

**Features**

[convtools-ita #26 ](https://github.com/itechart/convtools/issues/26)

- reimplemented pipes as a separate conversion + smart inlining
- now pipes are the only conversions which take care of adding labels
- introduced ``c.iter``: shortcut for ``self.pipe(c.generator_comp(element_conv))``
- introduced ``c.iter_mut``: generates the code which iterates and mutates the
  elements in-place. The result is a generator.

**Bugfix**

- fixed ``GroupBy.filter`` method to return generator by default, instead of
  list


## 0.10.0 (2021-04-28)

**Features**

[convtools-ita #25 by Anexen ](https://github.com/itechart/convtools/issues/25)

- introduced ``c.ReduceFuncs.Average`` - arithmetic mean or weighted mean
- introduced ``c.ReduceFuncs.Median``
- introduced ``c.ReduceFuncs.Mode`` - most frequent value; last one if there are
  many of the same frequency
- introduced ``c.ReduceFuncs.TopK`` - list of most frequent values


## 0.9.4 (2021-04-27)

**Bugfix**

- fixed ``c.item(..., default=c.input_arg("abc"))``-like cases, where input
  args passed to item/attr with defaults


## 0.9.3 (2021-04-11)

**Bugfix**

- fixed ``c.group_by`` case without reducers like:
  ``c.group_by(c.item(0)).aggregate(c.item(0))``


## 0.9.2 (2021-03-28)

**Misc**

- removed unnecessary ``debug=True`` enabled by default for ``join`` conversions


## 0.9.1 (2021-03-28)

**Bugfix**

[convtools-ita #24 ](https://github.com/itechart/convtools/issues/24)

- fixed populating ``linecache`` with source code (previously new lines were not preserved) -- debugging issue


## 0.9.0 (2021-03-24)

**Features**

[convtools-ita #23 ](https://github.com/itechart/convtools/issues/23)


- improved reducers to be usable on their own

```python
c.aggregate(
	c.ReduceFuncs.DictSum(
		c.item("name"),
		c.item("value")
	)
)
```

  previously it was possible to use them only within ``c.reduce`` clause:

```python
c.aggregate(
	c.reduce(
		c.ReduceFuncs.DictSum,
		(c.item("name"), c.item("value")),
	)
)
```

- allowed piping to reducers, still allowing to pipe the result further

```python
c.aggregate(
	c.item("value").pipe(
		c.ReduceFuncs.Sum(c.this()).pipe(c.this() + 1)
	)
).gen_converter(debug=True)
```

- fixed nested piping in aggregations
- reworked docs to use testable code


## 0.8.0 (2021-01-03)

**Misc**

- improved pylint rating
- added a few type hints
- added a few docstings


## 0.7.2 (2020-11-12)

**Misc**

- [convtools-ita #22 ](https://github.com/itechart/convtools/issues/22)


## 0.7.1 (2020-07-12)

**Bugfixes**

- Fixed name generation uniqueness issue
  [convtools-ita #21 ](https://github.com/itechart/convtools/issues/21)


## 0.7.0 (2020-06-14)

**Features**

- Introduced ``c.Mut.set_item`` and other mutations to be used in ``(...).tap(...)``` method
  [convtools-ita #20 ](https://github.com/itechart/convtools/issues/20)


## 0.6.1 (2020-05-18)

**Bugfixes**

- fixed ``gen_name`` usages (made ``item_to_hash`` mandatory)
  [convtools-ita #19 ](https://github.com/itechart/convtools/issues/19)


## 0.6.0 (2020-05-17)

**Features**

- * introduced ``c.optional`` collection items, which get omitted based on value or a condition
  * improved converter generation so that inner conversions are not getting their own callable wrapper
  * updated generated code variable name generation [convtools-ita #18 ](https://github.com/itechart/convtools/issues/18)


## 0.5.3 (2020-03-30)

**Bugfixes**

- fixed aggregate issue: reduce(...).item(..., default=...) case [convtools-ita #15 ](https://github.com/itechart/convtools/issues/15)


## 0.5.2 (2020-03-29)

**Bugfixes**

- fixed Aggregate multiple reduce optimization
- added main page
- added workflow example

[convtools-ita #14](https://github.com/itechart/convtools/issues/14)


## 0.5.1 (2020-03-26)

Updated index page docs.


## 0.5.0 (2020-03-23)

**Features**

- - increased the speed of ``c.aggregate`` and ``c.group_by`` by collapsing multiple ``if`` statements into one
  - updated labeling functionality

  [convtools-ita #11](https://github.com/itechart/convtools/issues/11)


## 0.4.0 (2020-03-19)

**Features**

- Improved the way ``linecache`` is used: now the number of files to be put
  into the ``linecache`` is limited to 100. The eviction is done by implementing
  recently used strategy.
  [convtools-ita #9](https://github.com/itechart/convtools/issues/9)
- - introduced ``c.join``
  - improved & fixed pipes (code with side-effects piped to a constant)

  [convtools-ita #10](https://github.com/itechart/convtools/issues/10)


## 0.3.3 (2020-03-06)

**Features**

- 1. fixed main example docs
  2. improved ``c.aggregate`` speed

  [convtools-ita #8](https://github.com/itechart/convtools/issues/8)


## 0.3.2 (2020-03-05)

**Improved Documentation**

- * updated docs (fixed numbers) and updated pypi docs


## 0.3.1 (2020-03-05)

**Features**

- * introduced c.OptionsCtx
  * improved tests - memory leaks
  * improved docs - added the index page example; added an example to QuickStart

  [convtools-ita #7](https://github.com/itechart/convtools/issues/7)


## 0.3.0 (2020-03-01)

**Features**

- Introduced `labeling`:

    * ``c.item("companies").add_label("first_company", c.item(0))`` labels the first
      company in the list as `first_company` and allows to use it as
      ``c.label("first_company")`` further in next and even nested conversions

    * ``(...).pipe`` now receives 2 new arguments:

      * `label_input`, to put some labels on the pipe input data
      * `label_output` to put labels on the output data.

      Both can be either ``str`` (label name to put on) or ``dict`` (keys are label names
      and values are conversions to apply to the data before labeling)

  [convtools-ita #6](https://github.com/itechart/convtools/issues/6)


**Bugfixes**

- Added ``__name__`` attribute to ctx. Now internal code from the generated converter is sending to Sentry (not only file name).
  Also the generated converter became a callable object, not a function.

  [convtools-ita #5](https://github.com/itechart/convtools/issues/5)


## 0.2.3 (2020-02-27)

**Bugfixes**

- Fixed ``c.group_by((c.item("name"),)).aggregate((c.item("name"), c.reduce(...)))``.
  Previously it was compiling successfully, now it raises ``ConversionException`` on ``gen_converter``
  because there is no explicit mention of ``c.item("name")`` field in group by keys (only tuple).

  [convtools-ita #4](https://github.com/itechart/convtools/issues/4)


## 0.2.2 (2020-02-25)

**Bugfixes**

- fixed ``c.aggregate`` to return a single value for empty input

  [convtools-ita #3](https://github.com/itechart/convtools/issues/3)


## 0.2.1 (2020-02-24)

**Bugfixes**

- ``c.aggregate`` now returns a single value (previously the result was a list of one item)

  [convtools-ita #2](https://github.com/itechart/convtools/issues/2)


## 0.2.0 (2020-02-23)

**Features**

- added ``c.if_`` conversion and introduced QuickStart docs

  [convtools-ita #1](https://github.com/itechart/convtools/issues/1)
