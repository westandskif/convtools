0.12.0 (2021-05-10)
-------------------

Bugfix
++++++

- ``.filter`` was unified across the library to work with previous step results
  only, no longer injecting conditions inside comprehensions & reducers.
  Now to pass conditions to comprehensions & reducers, use the following:

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

0.11.0 (2021-05-06)
-------------------

Bugfix
++++++

- fixed ``GroupBy.filter`` method to return generator by default, instead of
  list

