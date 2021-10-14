.. _convtools_tables:

===================================
convtools Table - stream processing
===================================

1. Installation
_______________

``pip install convtools``

For the sake of conciseness, let's assume the following imports are in place:

.. code-block:: python

 from convtools.contrib.tables import Table
 from convtools import conversion as c

This is an object which exposes public API.

Please make sure you've read - :ref:`base info here<ref_index_intro>`.

2. Basics
_________

* **table conversion** - an instance of
  :py:obj:`convtools.contrib.tables.Table`, which works with iterables, so
  it cannot be reused once consumed
* **duplicate column names** - there's a special treatment to these:

  * when initializing from iterable of rows, by default it raises
    :py:obj:`ValueError` when a duplicate column name is detected
    (``duplicate_columns`` option is set to ``"raise"`` by default)
  * when initializing from CSV, by default it mangles duplicate column names
    like: "a", "a_1", "a_2", etc. (``duplicate_columns`` option is set to
    ``"mangle"`` by default)

  ``duplicate_columns`` option accepts the following values: "raise", "keep",
  "drop", "mangle", please see
  :py:obj:`convtools.contrib.tables.Table.from_rows` docs for more
  information

3. Reading CSV
______________

Let's:
  * read ``input.csv`` file, which contains two columns ``a`` and ``b`` and a
    header in the first row
  * add a new column ``c``, which is a sum of ``a`` and ``b``
  * store the result in `output.csv` file

.. code-block:: python

      (
          Table
          .from_csv(
              "tests/csvs/ac.csv",
              header=True,
              dialect=Table.csv_dialect(delimiter="\t"),
          )
          .take("a", "c")
          .update(B=c.col("a") + c.col("c"))
          .rename({"a": "A"})
          .drop("c")
          .into_csv("tests/csvs/out.csv")
      )


Reading dicts like :py:obj:`csv.DictReader`, but faster because dicts are
initialized as literals:

.. code-block:: python

   Table.from_csv("tests/csvs/ac.csv", True).into_iter_rows(dict)


Custom dialect (e.g. different delimiter), custom header:

.. code-block:: python

   Table.from_csv(
       "tests/csvs/ac.csv",
       header={"A": 1, "B": 0},  # indices of list (row from csv.reader)
       skip_rows=1,  # skipping the heading row
       dialect=Table.csv_dialect(delimiter="\t"),
   ).into_iter_rows(dict)

.. warning::

   Providing own headers, be sure ``Table`` will raise ValueError if numbers
   of columns don't match.


**For more details see:**

#. :py:obj:`convtools.contrib.tables.Table.from_csv`
#. :py:obj:`convtools.contrib.tables.Table.into_iter_rows`
#. :py:obj:`convtools.contrib.tables.Table.into_csv`

____

**It's important to note what is going on under the hood.** We can wrap the
above like below to see ad hoc code :py:obj:`convtools.contrib.tables.Table`
generates under the hood (using convtools conversions):

.. tabs::

   .. tab:: ipython

      .. code-block:: python

         with c.OptionsCtx() as options:
             options.debug = True
             Table.from_csv("tests/csvs/ab.csv", header=True).update(
                 c=c.col("a") + c.col("b")
             ).into_csv("tests/csvs/out.csv")


   .. tab:: output

      .. code-block:: python

         def converter_r8(data_):
             global __naive_values__, __none__
             _naive = __naive_values__
             _none = __none__
             _labels = {}
             return (
                 (
                     i_ci[0],
                     i_ci[1],
                     (i_ci[0] + i_ci[1]),
                 )
                 for i_ci in data_
             )

____

**Points to comprehend:**

#. table conversions embed indices and don't have superfluous loops inside.
   This allows them to work just as fast as simple bare python code.
#. table conversions work with iterables, so they cannot be reused once
   consumed
#. table conversions do their best to be lazy except for cases where it's
   impossible (e.g. when :py:obj:`convtools.contrib.tables.Table.join` decides to
   use hash-join, it builds a full hashmap, consuming the right side iterable


4. Reading rows
_______________

Just pass an iterable of one of tuple/list/dict:

.. code-block:: python

   # if no header passed, columns get names like: "COLUMN_0", "COLUMN_1", etc.
   Table.from_rows([(1, 2, 3), (2, 3, 4)])

   Table.from_rows([[1, 2, 3], [2, 3, 4]], header=["a", "b", "c"])

   Table.from_rows([{"a": 1, "b": 2}, {"a": 2, "b": 3}])

**For more details see:**

#. :py:obj:`convtools.contrib.tables.Table.from_rows`
#. :py:obj:`convtools.contrib.tables.Table.into_iter_rows`
#. :py:obj:`convtools.contrib.tables.Table.into_csv`


5. Rename, take, drop columns
_____________________________

These methods operate with column names and can accept multiple values:

.. code-block:: python

   # just to show all at once
   list(
       Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
       .rename({"a": "A"})
       .drop("b")
       .take("A")
       .into_iter_rows(dict)
   )

**For more details see:**

#. :py:obj:`convtools.contrib.tables.Table.rename`
#. :py:obj:`convtools.contrib.tables.Table.drop`
#. :py:obj:`convtools.contrib.tables.Table.take`


6. Add, update columns
______________________

To process data:
  * you should be comfortable with ``convtools`` conversions
  * use ``c.col("a")`` syntax to reference ``"a"`` column values (all
    conversions are element-wise).

.. code-block:: python

   list(
       Table.from_rows([(1, -2), (2, -3)], ["a", "b"])
       .update(c=c.col("a") + c.col("b"))  # adding new column: "c"
       .update(c=c.call_func(abs, c.col("c")))  # updating new column: "c"
       .into_iter_rows(dict)
   )

**For more details see:**

#. :py:obj:`convtools.contrib.tables.Table.update`


7. Filter rows
______________

You can filter rows by passing a conversion - :py:obj:`convtools.contrib.tables.Table.filter`

.. code-block:: python

   list(
       Table.from_rows([(1, -2), (2, -3)], ["a", "b"])
       .filter(c.col("b") < -2)
       .into_iter_rows(dict)
   )




8. Join tables
______________

When you join two tables, conflicting columns (except for ones, specified as
list of columns, passed as ``on`` argument) get suffixed with "_LEFT" and
"_RIGHT" for columns of left and right tables correspondingly. Suffixes can be
overridden using ``suffixes`` option.

There are two ways to join tables:

#. passing list of column names as ``on`` argument, joining rows based on
   equality

   .. code-block:: python

       list(
           Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
           .join(
               Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
               how="inner",
               on=["a"],
           )
           .into_iter_rows(dict)
       )

#. passing a custom join condition as ``on`` argument, where
   ``c.LEFT.col("a")`` references an element in column ``"a"`` of the left
   table and ``c.RIGHT.col("a")`` references an element in column ``"a"`` of
   the right table

   .. code-block:: python

       list(
           Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
           .join(
               Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
               how="full",
               on=c.and_(
                   c.LEFT.col("a") == c.RIGHT.col("a"),
                   c.LEFT.col("b") < c.RIGHT.col("c")
               )
           )
           .into_iter_rows(dict)
       )


**For more details see:**

#. :py:obj:`convtools.contrib.tables.Table.join`

9. Chain tables
_______________

.. automethod:: convtools.contrib.tables.Table.chain
   :noindex:

10. Zip tables
______________

.. automethod:: convtools.contrib.tables.Table.zip
   :noindex:

11. Using inside other conversions
_________________________________

It's impossible to make ``Table`` work directly inside other conversions,
because it would introduce ambiguity on which code generating layer is to
transform the conversion into code: ``Table`` or the parent conversion.

But you most definitely can leverage piping to callables like this:

.. code-block:: python

   input_data = [["a", "b"], [1, 2], [3, 4]]
   conversion = c.this().pipe(
       lambda it: Table.from_rows(it, header=True).into_iter_rows(dict)
   ).as_type(list)
   conversion.execute(input_data)
