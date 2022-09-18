Why would you need this?
========================

* you prefer declarative approach
* you love functional programming
* you believe that Python is high-level enough not to make you write
  aggregations and joins by hand
* you need to serialize/validate objects
* you need to dynamically define transforms (including at runtime)
* you like the idea of having something write ad hoc code for you :)


Installation:
=============

.. code-block:: bash

   pip install convtools


Conversions - data transforms, aggregations, joins
==================================================

.. code-block:: python

   # pip install convtools

   from convtools import conversion as c

   input_data = [{"StoreID": " 123", "Quantity": "123"}]

   # define a conversion (sometimes you may want to do this dynamically)
   #  takes iterable and returns iterable of dicts, stopping before the first
   #  one with quantity >= 1000, splitting into chunks of size = 1000
   conversion = (
       c.iter(
           {
               "id": c.item("StoreID").call_method("strip"),
               "quantity": c.item("Quantity").as_type(int),
           }
       )
       .take_while(c.item("quantity") < 1000)
       .pipe(
           c.chunk_by(c.item("id"), size=1000)
       )
       .as_type(list)
       .gen_converter(debug=True)
   )

   # compile the conversion into an ad hoc function and run it
   converter = conversion.gen_converter()
   converter(input_data)

   # OR in case of a one-shot use
   conversion.execute(input_data)

.. include:: ../tests/test_doc__index_intro.py
   :code: python


What reducers are supported by aggregations?
++++++++++++++++++++++++++++++++++++++++++++

Built-in ones, exposed like ``c.ReduceFuncs.Sum``:
 * Sum
 * SumOrNone
 * Max
 * MaxRow
 * Min
 * MinRow
 * Count
 * CountDistinct
 * First
 * Last
 * Average
 * Median
 * Percentile - ``c.ReduceFuncs.Percentile(95.0, c.item("x"))``
 * Mode
 * TopK - ``c.ReduceFuncs.TopK(3, c.item("x"))``
 * Array
 * ArrayDistinct
 * ArraySorted - ``c.ReduceFuncs.ArraySorted(c.item("x"), key=lambda v: v, reverse=True)``
 * Dict - ``c.ReduceFuncs.Dict(c.item("key"), c.item("x"))``
 * DictArray
 * DictSum
 * DictSumOrNone
 * DictMax
 * DictMin
 * DictCount
 * DictCountDistinct
 * DictFirst
 * DictLast

and any reduce function of two arguments you pass in ``c.reduce``.


Contrib / Table - stream processing of table-like data
======================================================

``Table`` helper allows to massage CSVs and table-like data:
 * join / zip / chain tables
 * take / drop / rename columns
 * filter rows
 * update / update_all values

.. code-block:: python

   from convtools.contrib.tables import Table
   from convtools import conversion as c

   # reads Iterable of rows
   (
       Table.from_rows([(0, -1), (1, 2)], header=["a", "b"]).join(
           Table
           # reads tab-separated CSV file
           .from_csv(
               "tests/csvs/ac.csv",
               header=True,
               dialect=Table.csv_dialect(delimiter="\t"),
           )
           # transform column values
           .update(
               a=c.col("a").as_type(float),
               c=c.col("c").as_type(int),
           )
           # filter rows by condition
           .filter(c.col("c") >= 0),
           # joins on column "a" values
           on=["a"],
           how="inner",
       )
       # rearrange columns
       .take(..., "a")
       # this is a generator to consume (tuple, list are supported too)
       .into_iter_rows(dict)
   )


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
* convtools supports nested aggregations


Is this thing debuggable?
=========================

Despite being compiled at runtime, it is (by both ``pdb`` and ``pydevd``).
