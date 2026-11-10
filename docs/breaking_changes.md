# Breaking changes

## Planned for 2.0

If `v2` happens one day, passing `initial` to the following reducers (whose
internal accumulators are private) will raise `ValueError` instead of emitting
`DeprecationWarning`:

* `ArrayDistinct`
* `ArraySorted`
* `Correlation`
* `CountDistinct`
* `Covariance`
* `Dict`
* `DictArray`
* `DictArrayDistinct`
* `DictCount`
* `DictCountDistinct`
* `DictFirst`
* `DictFirstN`
* `DictLast`
* `DictLastN`
* `DictMax`
* `DictMin`
* `DictSum`
* `DictSumOrNone`
* `First`
* `FirstN`
* `Last`
* `LastN`
* `MaxRow`
* `MinRow`
* `Median`
* `Mode`
* `Percentile`
* `PopulationStdDev`
* `PopulationVariance`
* `StdDev`
* `TopK`
* `Variance`


## 1.18.1 (2026-11-10)

- `c.this.desc(*, none_last=None, none_first=None)` now accepts keyword
  arguments only, matching `c.this.asc(*, none_last=None, none_first=None)`.


## 1.18.0 (2026-10-18)

- Labels written inside a reducer argument (`where`, a value expression,
  `initial`, or `default`) can now only be read within that same argument;
  reading them from another argument of the reducer, a sibling reducer, the
  aggregate / `group_by` output, or `group_by` keys raises
  `ConversionException` at compile time. Use `c.ReduceFuncs.Last` for a last
  value.
- A custom `BaseReducer` subclass with empty `prepare_first_lines` now raises
  `ConversionException` at compile time.


## 1.17.4 (2026-09-23)

- Removed the undocumented `BaseConversion.replace_word` helper.


## 1.17.3 (2026-09-13)

- `c.if_` no longer accepts the `no_input_caching` parameter.
- `split_buffer` and `split_buffer_n_decode` no longer close the passed buffer;
  the caller owns and closes it.
- `c.input_arg("self")` and `c.input_arg("cls")` now raise at `gen_converter`
  unless `method=True` / `class_method=True` (or a custom `signature=` includes
  the name).
- `FirstN(..., initial=...)` no longer seeds the collected list; like `LastN`,
  `initial=` is deprecated and only serves as the empty-input result.
- `DictComp.filter(..., cast=None)` returns a `dict` (same as omitting `cast`)
  instead of a generator of `(key, value)` pairs.
- `sort(key=...)`, `over(order_by=...)`, and `over(partition_by=...)` treat a
  `list` as a sequence of keys (same as `tuple`); plain callables inside key
  sequences raise `TypeError` (wrap as `c.call_func(f, c.this)`).


## 1.17.2 (2026-09-06)

- Join condition terms referencing `c.LEFT` or `c.RIGHT` can no longer read the
  outer join input (`c.this`); they raise `ConversionException` at
  `gen_converter()`. Pass outer values via `c.input_arg(...)` or `c.label(...)`,
  or attach the expression to `c.LEFT` / `c.RIGHT` with `.pipe(...)`.
- `c.expect(..., error_msg=...)` only uses `"condition is not met"` when
  `error_msg` is `None`; falsy values such as `""` or `0` are preserved.
- `c.input_arg` rejects reserved and invalid parameter names (`data_`, `_none`,
  Python keywords, non-identifiers).
- Reducer `default=` conversions that depend on row inputs now raise at compile
  time.


## 1.14.6 (2025-08-10)

- `Average`, `Percentile`, `TopK`, `CountDistinct`, and `DictCountDistinct` now
  skip `None` values, matching `Min` and `Max`.


## 1.14.5 (2025-07-31)

- `c.item(..., default=...)` suppresses only `(TypeError, KeyError, IndexError)`
  and `c.attr(..., default=...)` suppresses only `AttributeError`, rather than
  catching arbitrary `Exception` subclasses.


## 1.2.0 (2023-04-10)

- `c.ReduceFuncs.Mode` and `TopK` sort by frequency only instead of `(count,
  value)` pairs, so `Mode` breaks ties by first-encountered order (and works on
  mutually unorderable values).
- Passing `initial=` to reducers whose internal accumulators are private was
  deprecated (`DeprecationWarning`, raising `ValueError` in 2.0).


## 1.0.0 (2023-03-23)

- renamed all non-public modules so the only supported way to import is
  directly from "convtools", e.g.:

    * `from convtools import conversion as c`
    * `from convtools import DateGrid, DateTimeGrid`

- contrib ones are left as is:

    * `from convtools.contrib.tables import Table`
    * `from convtools.contrib.fs import split_buffer`


## 0.37.0 (2022-09-29)

Changed `add_label` signature from:
```python
(...).add_label(label_name: t.Union[str, dict], conversion)
```
to:
```python
(...).add_label(label_name: t.Union[str, dict])
```
The reason is that it had confusing behavior of applying the conversion after
labeling.


## 0.24.0 (2022-05-29)

**Clean-up**

When you use ``c.item(c.item("key"))``, it generates ``data_[data_["key"]]``
under the hood. However reducers (``c.ReduceFuncs`` objects) used to replace
the input data for subsequent conversions with the reducer result, which was an
inconsistency (so that "key" was taken off of the reducer result, not its
input).

Now, the following is impossible: ``c.aggregate(reducer.item(c.item("key")))``
because ``c.item("key")`` is neither a group by field, nor a reducer.


## 0.19.0 (2021-10-28)

**Clean-up**

Normally you use ``c.ReduceFuncs.Sum(c.this())`` to reduce something, but it's
possible to use custom reduce functions like this:

* ``c.reduce(lambda x, y: x + y, c.this(), initial=0)``
* ``c.reduce(c.inline_expr("{} + {}"), c.this(), initial=0)``

``c.reduce`` used to support ``prepare_first`` parameter which was adding
confusion. Now it's dropped.


## 0.12.0 (2021-05-10)

**Bugfix**

- ``.filter`` was unified across the library to work with previous step results
  only, no longer injecting conditions inside comprehensions & reducers.
  Now to pass conditions to comprehensions & reducers, use the following:

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

```python
# REPLACE THIS
c.generator_comp(c.item("a")).filter(c.item("b") == "bar")
# WITH THAT
c.generator_comp(c.item("a"), where=c.item("b") == "bar")
# if the condition is to be put to the IF clause of the comprehension to
# work with the input elements or leave it as is if you want to filter the
# resulting generator
```

  The same applies to:

   * ``c.list_comp``
   * ``c.tuple_comp``
   * ``c.set_comp``
   * ``c.dict_comp``


----

## 0.11.0 (2021-05-06)

**Bugfix**

- fixed ``GroupBy.filter`` method to return generator by default, instead of
  list
