0.31.0 (2022-07-06)
___________________

Experimental - contrib.model:
+++++++++++++++++++++++++++++

- added Enum validator, e.g. ``validators.Enum(UserDefinedEnum)`` to check
  whether an object is a valid value of a provided Enum subclass

0.30.0 (2022-07-06)
___________________

Experimental - contrib.model:
+++++++++++++++++++++++++++++

- added length validator, e.g. ``validators.Length(min_length=1, max_length=2)``

0.29.0 (2022-07-05)
___________________

- updated ``DictArray``, ``DictSum``, ``DictSumOrNone`` so they don't rebuild
  dicts from defaultdicts (only setting default_factory to None, so
  defaultdicts start raising KeyErrors like regular dicts)
- changed ``c.naive`` conversion logic so it supports pre-warming its value by
  putting it as a function parameter with a default value (conversions are not
  obliged to use naive pre-warming; if they don't request it, they will deal
  with global lookups to ``__naive_values__`` dict)

Experimental - contrib.model:
+++++++++++++++++++++++++++++

- updated casters to support expression-mode, where they can be used as a part
  of list/set/dict/tuple comprehension (instead of building these collections
  in a loop in simple cases)
- sped up models
- inlined ``validators.Required``

0.28.0 (2022-07-03)
___________________

Experimental - contrib.model:
+++++++++++++++++++++++++++++

- added ``typing.Set`` support
- added ``X | Y`` type support (PEP 604 - Python 3.10+)
- added ``list[int]``-like type definition support (Python 3.9+)

0.27.0 (2022-07-01)
___________________

Experimental - contrib.model:
+++++++++++++++++++++++++++++

- added ``a: bool = cast()`` support
- added ``typing.Literal`` support

0.26.0 (2022-06-30)
___________________

Experimental - contrib.model:
+++++++++++++++++++++++++++++

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

Misc:
+++++

- updated `c.or_` and `c.and_` to better flatten nested constructions


0.25.2 (2022-06-24)
___________________

Bugfix
++++++

- fixed ``.gen_converter(class_method=True)``, broken in v0.25.0 where callable
  wrapper was eliminated. Now it returns a converter, wrapped with
  ``classmethod``

0.25.1 (2022-06-24)
___________________

Bugfix
++++++

- fixed label bug in case of nested pipes, introduced in 0.24.1: was leading to
  label key errors since labels were skipping initialization


0.25.0 (2022-06-22)
___________________

Experimental features:
++++++++++++++++++++++

- introduced data validation models: ``convtools.contrib.models.DictModel``
  (accesses keys and indexes) and ``convtools.contrib.models.ObjectModel``
  (accesses attributes and indexes)

Misc
++++

- reworked converter generation to store generated code inside the main context
- eliminated converter wrapper, which was a callable, taking care of dumping
  generated source code to tmpdir in cases of exceptions. Now converters take
  care of this themselves.
- now long list/dict/tuple/set literal definition code includes newlines, so
  it's easier to debug in case of exception


0.24.1 (2022-05-29)
___________________

Misc
++++

- forced pipes to inline if labels of "what" conversion cannot affect "where"
  label usage


0.24.0 (2022-05-29)
___________________

Features
++++++++

- introduced ``convtools.contrib.fs`` helpers: ``split_buffer`` and
  ``split_buffer_n_decode`` to close the gap in Python's ``open``
  functionality, related to "newlines" (it doesn't support custom ones in text
  mode and doesn't support any in binary one).

Misc
++++
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


0.23.3 (2022-03-11)
___________________

Bugfix
++++++

- fixed long existing bug in aggregations in cases where multiple reducers get
  initialized at different moments, e.g. the first reducer collects min values
  of column "a", while the second reducer collects max values of column "b",
  "min a" may get initialized earlier than "max b" and then this would raise
  ``Exception``

0.23.2 (2022-03-10)
___________________

Bugfix
++++++

- fixed ``c.attr("a", default=None).attr("b", default=None)`` (preferred
  ``c.attr("a", "b", default=None)`` was working though)
- fixed too-many-parenthesis error for long chains of ``and_``, ``or_`` and
  ``==``

0.23.1 (2022-02-23)
___________________

Misc
++++

- allowed passing callables to ``and_then`` so they are called with input as an
  argument
- made ``and_then`` handle the default case as ``a and conv(a)`` not ``if``



0.23.0 (2022-02-22)
___________________

Features
++++++++

- added ``c.and_then`` and ``(...).and_then`` shortcut to pipe if condition is
  true, otherwise leave untouched. Supports overriding default ``bool``
  condition.


0.22.0 (2022-01-02)
___________________

`#16 <https://github.com/westandskif/convtools/pull/16>`_

Features
++++++++

- added ``c.ReduceFuncs.ArraySorted`` reducer
- reworked ``GetItem`` and ``GetAttr`` to cache ``get_or_default`` methods
  based on number of indexes and args
- added support for single column tables (headers are always str still)

Misc
++++

- updated internals of arg def handling, made naive and labels optional
- removed ``NamedConversion`` and ``ConversionWrapper`` in favor of new
  ``LazyEscapedString``, ``Namespace`` and ``NamespaceCtx``. This lays better
  groundwork for future use of conversions which generate code around another
  named ones.

0.21.0 (2021-12-19)
___________________

Features
++++++++

#. backward-compatible change: now ``c.this`` is preferred over ``c.this()``
#. ``c.and_`` and ``c.or_`` support any number of arguments (used to be 2
   mandatory ones). And also supports ``default: bool = None`` argument to control
   what should happen if no arguments are passed:

   * if None, raises ``ValueError``
   * if false value, returns ``False``
   * if true value, returns ``True``


0.20.2 (2021-12-02)
___________________


`#14 <https://github.com/westandskif/convtools/issues/14>`_

Misc
++++

- improved performance of ``Table.chain``, ``Table.into_iter_rows`` and
  ``Table.into_csv`` methods
- improved performance of ``c.apply_func``

0.20.1 (2021-11-29)
___________________


`#11 <https://github.com/westandskif/convtools/pull/11>`_

Features
++++++++

- added ``c.chunk_by(c.item("x"), size=100)`` for slicing iterables into chunks
  by element values and/or size of chunk
- added ``c.chunk_by_condition(c.CHUNK.item(-1) - c.this() < 100)`` for slicing
  iterables into chunks based on condition, which is a function of a current
  chunk and a current element
- added ``(...).len()`` shortcut for ``c.call_func(len, c.this())``

Misc
++++

- no longer create empty ``labels_`` dict on each converter call where no
  labels are going to be used
- no longer create new ``This`` instances, now reusing an existing one


0.19.0 (2021-10-28)
___________________

Features
++++++++

`#8 <https://github.com/westandskif/convtools/issues/8>`_

- added ``c.ReduceFuncs.Percentile``
- ``c.reduce`` now accepts conversions as ``initial`` argument, this will be
  resolved on the first row met. If ``initial`` conversion depends on input
  data, it won't be used as ``default`` if default is not provided.
- sped up ``c.ReduceFuncs.Sum`` and ``c.ReduceFuncs.Average`` for cases where
  elements are obviously not None

BREAKING CHANGES:
+++++++++++++++++

Normally you use ``c.ReduceFuncs.Sum(c.this())`` to reduce something, but it's
possible to use custom reduce functions like this:

* ``c.reduce(lambda x, y: x + y, c.this(), initial=0)``
* ``c.reduce(c.inline_expr("{} + {}"), c.this(), initial=0)``

``c.reduce`` used to support ``prepare_first`` parameter which was adding
confusion. Now it's dropped.

0.18.0 (2021-10-24)
___________________


Features
++++++++

`#6 <https://github.com/westandskif/convtools/issues/6>`_

- added ``c.take_while`` and ``(...).take_while`` re-implementation of
  ``itertools.takewhile``
- added ``c.drop_while`` and ``(...).drop_while`` re-implementation of
  ``itertools.dropwhile``


0.17.0 (2021-10-14)
___________________


Features
++++++++

- added ``Table.zip`` method to stitch tables (joining on row indexes)
- added ``Table.chain`` method to put tables together one after another


0.16.0 (2021-10-12)
___________________


Features
++++++++

- introduced ``Table`` conversions `#3
  <https://github.com/westandskif/convtools/pull/3>`_
- added ``c.apply_func``, ``c.apply`` and ``(...).apply_method`` conversions

Bugfix
++++++

- fixed inner join with inner loop with soft conditions: any condition except
  for ``==`` and ``c.and_``
- fixed piping to callable with further calling pipe methods like ``as_type``,
  ``filter`` and ``sort``

Misc
++++

- reworked main converter callable wrapper so that it no longer dumps sources
  onto disk for beautiful stacktraces when the converter returns a generator
  (it used to make them down almost 2 times slower). If such debugging is
  needed, just enable debug. As for simple exceptions, these still dump code to
  disc on Exceptions because this should be cheap.

0.15.4 (2021-09-23)
___________________

Bugfix
++++++

- fixed `#2 <https://github.com/westandskif/convtools/issues/2>`_: issue with
  input args passed to pipe labels

0.15.3 (2021-09-19)
___________________

Misc
++++

- hard fork


0.15.2 (2021-09-17)
___________________

Bugfix
++++++

- fixed passing strings containing ``%`` and ``{`` to ``c.aggregate`` - `convtools-ita #34 <https://github.com/itechart/convtools/issues/34>`_


0.15.1 (2021-08-08)
___________________

Bugfix
++++++

- replaced ``linecache`` populating code with real dumping generated code to
  files in either ``PY_CONVTOOLS_DEBUG_DIR`` (*if env variable is defined*) or
  to python's ``tempfile.gettempdir``. This adds pydevd support (VS Code and PyCharm debugger).


0.15.0 (2021-08-02)
___________________

Features
++++++++

- introduced ``c.breakpoint`` and ``(...).breakpoint()`` to simplify debugging long pipelines

Misc
++++

- [internals] created a separate conversion for ``c.this()``
- [internals] now ``c.naive`` is a direct init of ``NaiveConversion``
- improved quick start, cheatsheet and api docs

0.14.1 (2021-07-12)
___________________

Bugfix
++++++

- fixed piping something complex to ``c.join``

Misc
++++

- [internals] reworked aggregate & group_by templating
- [internals] reworked optional items processing


0.14.0 (2021-06-27)
___________________

Features
++++++++

- introduced ``c.zip``, which supports both args to yield tuples and kwargs to yield dicts
- introduced ``c.repeat`` -- the one from ``itertools``
- introduced ``c.flatten`` -- shortcut for ``itertools.chain.from_iterable``


0.13.4 (2021-06-20)
-------------------

Bugfix
++++++

- fixed incorrect aggregate (not group_by) results in case of ``where``
  conditions in reducers `convtools-ita #32 <https://github.com/itechart/convtools/issues/32>`_

0.13.3 (2021-06-14)
-------------------

`convtools-ita #30 <https://github.com/itechart/convtools/issues/30>`_

Bugfix
++++++

- fixed nested aggregations

Misc
++++

- [internals] reworked aggregate & group_by templating

----

0.13.2 (2021-05-27)
-------------------

Bugfix
++++++

- fixed join + input_arg case

----

0.13.1 (2021-05-23)
-------------------

Bugfix
++++++

`convtools-ita #29 <https://github.com/itechart/convtools/issues/29>`_

- fixed right join (conditions were not swapped correctly)

----

0.13.0 (2021-05-16)
-------------------

Features
++++++++

`convtools-ita #28 <https://github.com/itechart/convtools/issues/28>`_

- now ``c.iter`` supports ``where`` parameters just like ``c.generator_comp``:

  * ``c.iter(c.this() + 1, where=c.this() > 0)``

- now it's possible to use ``.pipe`` wherever you want as long as it lets you
  do so, even piping in and out of reducers (``c.ReduceFuncs``)

  * e.g. it will raise an Exception if you try to add labels to a reducer input

- now it's possible to use ``aggregate`` inside ``aggregate`` as long as you
  don't nest reducers

----

0.12.1 (2021-05-13)
-------------------

Bugfix
++++++

- fixed sporadic issues caused by code substring replacements (now it uses word
  replacements)


----


0.12.0 (2021-05-10)
-------------------

Bugfix - BREAKING CHANGES
+++++++++++++++++++++++++

- ``.filter`` was unified across the library to work with previous step results
  only, no longer injecting conditions inside comprehensions & reducers.
  So to pass conditions to comprehensions & reducers, use the following:

  .. code-block:: python

     # REPLACE THIS
     c.ReduceFuncs.Array(c.item("a")).filter(c.item("b") == "bar")
     # WITH THAT
     c.ReduceFuncs.Array(c.item("a"), where=c.item("b") == "bar")
     # if the condition is to be applied before the aggregation
     # or leave as is if you want to filter the resulting array

- ``c.generator_comp(...).filter(condition)`` no longer pushes condition inside
  the comprehension, the filtering works on resulting generator

  .. code-block:: python

     # REPLACE THIS
     c.generator_comp(c.item("a")).filter(c.item("b") == "bar")
     # WITH THAT
     c.generator_comp(c.item("a"), where=c.item("b") == "bar")
     # if the condition is to be put to the IF clause of the comprehension to
     # work with the input elements or leave it as is if you want to filter the
     # resulting generator

  The same applies to:

   * ``c.list_comp``
   * ``c.tuple_comp``
   * ``c.set_comp``
   * ``c.dict_comp``


----

0.11.2 (2021-05-08)
-------------------


Features
++++++++

- introduced ``c.sort``  & ``(...).sort`` conversions, which are helpers for
  ``sorted``; this is done for the sake of unification with methods of
  comprehension conversions

Misc
++++

- implemented ``GroupBy.filter``, which returns generator of results without
  creating an intermediate list

----


0.11.1 (2021-05-07)
-------------------

Bugfix
++++++

- fixed complex conversion cases where there are multiple aggregations
  `convtools-ita #27 <https://github.com/itechart/convtools/issues/27>`_

----


0.11.0 (2021-05-06)
-------------------

Features
++++++++

`convtools-ita #26 <https://github.com/itechart/convtools/issues/26>`_

- reimplemented pipes as a separate conversion + smart inlining
- now pipes are the only conversions which take care of adding labels
- introduced ``c.iter``: shortcut for ``self.pipe(c.generator_comp(element_conv))``
- introduced ``c.iter_mut``: generates the code which iterates and mutates the
  elements in-place. The result is a generator.

Bugfix
++++++

- fixed ``GroupBy.filter`` method to return generator by default, instead of
  list

----


0.10.0 (2021-04-28)
-------------------

Features
++++++++

`convtools-ita #25 by Anexen <https://github.com/itechart/convtools/issues/25>`_

- introduced ``c.ReduceFuncs.Average`` - arithmetic mean or weighted mean
- introduced ``c.ReduceFuncs.Median``
- introduced ``c.ReduceFuncs.Mode`` - most frequent value; last one if there are
  many of the same frequency
- introduced ``c.ReduceFuncs.TopK`` - list of most frequent values

----



0.9.4 (2021-04-27)
------------------

Bugfix
++++++

- fixed ``c.item(..., default=c.input_arg("abc"))``-like cases, where input
  args passed to item/attr with defaults

----


0.9.3 (2021-04-11)
------------------

Bugfix
++++++

- fixed ``c.group_by`` case without reducers like:
  ``c.group_by(c.item(0)).aggregate(c.item(0))``

----


0.9.2 (2021-03-28)
------------------

Misc
++++

- removed unnecessary ``debug=True`` enabled by default for ``join`` conversions

----


0.9.1 (2021-03-28)
------------------

Bugfix
++++++

`convtools-ita #24 <https://github.com/itechart/convtools/issues/24>`_

- fixed populating ``linecache`` with source code (previously new lines were not preserved) -- debugging issue

----

0.9.0 (2021-03-24)
------------------

Features
++++++++

`convtools-ita #23 <https://github.com/itechart/convtools/issues/23>`_


- improved reducers to be usable on their own

  .. code-block:: python

    c.aggregate(
        c.ReduceFuncs.DictSum(
            c.item("name"),
            c.item("value")
        )
    )

  previously it was possible to use them only within ``c.reduce`` clause:

  .. code-block:: python

    c.aggregate(
        c.reduce(
            c.ReduceFuncs.DictSum,
            (c.item("name"), c.item("value")),
        )
    )

- allowed piping to reducers, still allowing to pipe the result further

  .. code-block:: python

    c.aggregate(
        c.item("value").pipe(
            c.ReduceFuncs.Sum(c.this()).pipe(c.this() + 1)
        )
    ).gen_converter(debug=True)

- fixed nested piping in aggregations
- reworked docs to use testable code


----


0.8.0 (2021-01-03)
------------------

Misc
++++

- improved pylint rating
- added a few type hints
- added a few docstings


----


0.7.2 (2020-11-12)
------------------

Misc
++++

- `convtools-ita #22 <https://github.com/itechart/convtools/issues/22>`_


----


0.7.1 (2020-07-12)
------------------

Bugfixes
++++++++

- Fixed name generation uniqueness issue
  `convtools-ita #21 <https://github.com/itechart/convtools/issues/21>`_


----


0.7.0 (2020-06-14)
------------------

Features
++++++++

- Introduced ``c.Mut.set_item`` and other mutations to be used in ``(...).tap(...)``` method
  `convtools-ita #20 <https://github.com/itechart/convtools/issues/20>`_


----


0.6.1 (2020-05-18)
------------------

Bugfixes
++++++++

- fixed ``gen_name`` usages (made ``item_to_hash`` mandatory)
  `convtools-ita #19 <https://github.com/itechart/convtools/issues/19>`_


----


0.6.0 (2020-05-17)
------------------

Features
++++++++

- * introduced ``c.optional`` collection items, which get omitted based on value or a condition
  * improved converter generation so that inner conversions are not getting their own callable wrapper
  * updated generated code variable name generation `convtools-ita #18 <https://github.com/itechart/convtools/issues/18>`_


----


0.5.3 (2020-03-30)
------------------

Bugfixes
++++++++

- fixed aggregate issue: reduce(...).item(..., default=...) case `convtools-ita #15 <https://github.com/itechart/convtools/issues/15>`_


----


0.5.2 (2020-03-29)
------------------

Bugfixes
++++++++

- fixed Aggregate multiple reduce optimization
- added main page
- added workflow example

`convtools-ita #14 <https://github.com/itechart/convtools/issues/14>`_


----


0.5.1 (2020-03-26)
------------------

Updated index page docs.


----


0.5.0 (2020-03-23)
------------------

Features
++++++++

- - increased the speed of ``c.aggregate`` and ``c.group_by`` by collapsing multiple ``if`` statements into one
  - updated labeling functionality

  `convtools-ita #11 <https://github.com/itechart/convtools/issues/11>`_


----


0.4.0 (2020-03-19)
------------------

Features
++++++++

- Improved the way ``linecache`` is used: now the number of files to be put
  into the ``linecache`` is limited to 100. The eviction is done by implementing
  recently used strategy.
  `convtools-ita #9 <https://github.com/itechart/convtools/issues/9>`_
- - introduced ``c.join``
  - improved & fixed pipes (code with side-effects piped to a constant)

  `convtools-ita #10 <https://github.com/itechart/convtools/issues/10>`_


----


0.3.3 (2020-03-06)
------------------

Features
++++++++

- 1. fixed main example docs
  2. improved ``c.aggregate`` speed

  `convtools-ita #8 <https://github.com/itechart/convtools/issues/8>`_


----


0.3.2 (2020-03-05)
------------------

Improved Documentation
++++++++++++++++++++++

- * updated docs (fixed numbers) and updated pypi docs


----


0.3.1 (2020-03-05)
------------------

Features
++++++++

- * introduced c.OptionsCtx
  * improved tests - memory leaks
  * improved docs - added the index page example; added an example to QuickStart

  `convtools-ita #7 <https://github.com/itechart/convtools/issues/7>`_


----


0.3.0 (2020-03-01)
------------------

Features
++++++++

- Introduced `labeling`:

    * ``c.item("companies").add_label("first_company", c.item(0))`` labels the first
      company in the list as `first_company` and allows to use it as
      ``c.label("first_company")`` further in next and even nested conversions

    * ``(...).pipe`` now receives 2 new arguments:

      * `label_input`, to put some labels on the pipe input data
      * `label_output` to put labels on the output data.

      Both can be either ``str`` (label name to put on) or ``dict`` (keys are label names
      and values are conversions to apply to the data before labeling)

  `convtools-ita #6 <https://github.com/itechart/convtools/issues/6>`_


Bugfixes
++++++++

- Added ``__name__`` attribute to ctx. Now internal code from the generated converter is sending to Sentry (not only file name).
  Also the generated converter became a callable object, not a function.

  `convtools-ita #5 <https://github.com/itechart/convtools/issues/5>`_


----


0.2.3 (2020-02-27)
------------------

Bugfixes
++++++++

- Fixed ``c.group_by((c.item("name"),)).aggregate((c.item("name"), c.reduce(...)))``.
  Previously it was compiling successfully, now it raises ``ConversionException`` on ``gen_converter``
  because there is no explicit mention of ``c.item("name")`` field in group by keys (only tuple).

  `convtools-ita #4 <https://github.com/itechart/convtools/issues/4>`_


----


0.2.2 (2020-02-25)
------------------

Bugfixes
++++++++

- fixed ``c.aggregate`` to return a single value for empty input

  `convtools-ita #3 <https://github.com/itechart/convtools/issues/3>`_


----


0.2.1 (2020-02-24)
------------------

Bugfixes
++++++++

- ``c.aggregate`` now returns a single value (previously the result was a list of one item)

  `convtools-ita #2 <https://github.com/itechart/convtools/issues/2>`_


----


0.2.0 (2020-02-23)
------------------

Features
++++++++

- added ``c.if_`` conversion and introduced QuickStart docs

  `convtools-ita #1 <https://github.com/itechart/convtools/issues/1>`_

