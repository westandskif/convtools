Why would you need this?
========================

* you love functional programming
* you believe that Python is awesome enough to have powerful aggregations and
  joins
* you need to serialize/deserialize objects
* you need to dynamically define transforms (including at runtime)
* you need to reuse code without function call overhead where possible (inlining)
* you like the idea of having something write ad hoc code for you

____

Every conversion:

* contains the information of how to transform an input
* can be **piped** into another conversion (same as wrapping)
* has a method ``gen_converter`` returning a compiled ad hoc function


Installation:
=============

.. code-block:: bash

   pip install convtools


What's the workflow?
====================

**Contrib / Table helper:**

``Table`` helper allows to massage CSVs and table-like data, join tables,
filter rows, take / drop / rename / update columns.

.. code-block:: python

   from convtools.contrib.tables import Table
   from convtools import conversion as c

   # reads Iterable of rows
   Table.from_rows(
       [(0, -1), (1, 2)],
       header=["a", "b"]
   ).join(
       Table
       # reads tab-separated CSV file
       .from_csv("tests/csvs/ac.csv", header=True, dialect=Table.csv_dialect(delimiter="\t"))
       # casts all column values to int
       .update_all(int)
       # filter rows by condition (convtools conversion)
       .filter(c.col("c") >= 0),
       # joins on column "a" values
       on=["a"],
       how="inner",
   ).into_iter_rows(dict)  # this is a generator to consume (tuple, list are supported to)

**Base conversions:**

.. code-block:: python

   # pip install convtools

   from convtools import conversion as c

   input_data = [{"StoreID": " 123", "Quantity": "123"}]

   # define a conversion (sometimes you may want to do this dynamically)
   #   takes iterable and returns iterable of dicts
   conversion = c.iter({
       "id": c.item("StoreID").call_method("strip"),
       "quantity": c.item("Quantity").as_type(int),
   })

   # compile the conversion into an ad hoc function and run it
   converter = conversion.gen_converter()
   converter(input_data)

   # OR in case of a single use
   conversion.execute(input_data)


**group_by, aggregate and join conversions:**

.. include:: ../tests/test_doc__index_intro.py
   :code: python


What reducers are supported by aggregations?
============================================

Any reduce function of two arguments you pass in ``c.reduce`` OR the following
ones, exposed like ``c.ReduceFuncs.Sum``:

#. Sum
#. SumOrNone
#. Max
#. MaxRow
#. Min
#. MinRow
#. Count
#. CountDistinct
#. First
#. Last
#. Average
#. Median
#. Mode
#. TopK
#. Array
#. ArrayDistinct
#. Dict
#. DictArray
#. DictSum
#. DictSumOrNone
#. DictMax
#. DictMin
#. DictCount
#. DictCountDistinct
#. DictFirst
#. DictLast


Is it any different from tools like Pandas / Polars?
====================================================

* convtools doesn't wrap data in any container, it just writes and runs the
  code which perform the conversion you defined
* convtools is a lightweight library with no dependencies `(however optional`
  ``black`` `is highly recommended for pretty-printing generated code when
  debugging)`
* convtools is about defining and reusing conversions -- declarative
  approach, while wrapping data in high-performance containers is more of being
  imperative


Is this thing debuggable?
=========================

Despite being compiled at runtime, it remains debuggable with both `pdb` and
`pydevd`




All-in-one example #1: deserialization & data preps
===================================================

.. include:: ../tests/test_doc__index_deserialization.py
   :code: python


All-in-one example #2: word count
=================================

.. include:: ../tests/test_doc__index_word_count.py
   :code: python
