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

