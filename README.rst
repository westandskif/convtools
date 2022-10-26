=========
convtools
=========

**convtools** is a python library to declaratively define data transforms:

* ``convtools.conversion`` - pipelines for processing collections, doing
  complex aggregations and joins.
* ``convtools.contrib.tables`` - stream processing of table-like data (e.g.
  CSV)

.. image:: https://img.shields.io/pypi/pyversions/convtools.svg
    :target: https://pypi.org/project/convtools/

.. image:: https://img.shields.io/github/license/westandskif/convtools.svg
   :target: https://github.com/westandskif/convtools/blob/master/LICENSE.txt

.. image:: https://codecov.io/gh/westandskif/convtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/westandskif/convtools

.. image:: https://github.com/westandskif/convtools/workflows/tests/badge.svg
   :target: https://github.com/westandskif/convtools/workflows/tests/badge.svg
   :alt: Tests Status

.. image:: https://readthedocs.org/projects/convtools/badge/?version=latest
   :target: https://convtools.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://img.shields.io/github/tag/westandskif/convtools.svg
   :target: https://GitHub.com/westandskif/convtools/tags/

.. image:: https://badge.fury.io/py/convtools.svg
   :target: https://badge.fury.io/py/convtools

.. image:: https://img.shields.io/twitter/url?label=convtools&style=social&url=https%3A%2F%2Ftwitter.com%2Fconvtools
   :target: https://twitter.com/convtools
   :alt: Twitter URL

Docs
====

* `convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
* `Cheatsheet <https://convtools.readthedocs.io/en/latest/cheatsheet.html>`_
* `QuickStart <https://convtools.readthedocs.io/en/latest/quick_start.html>`_
* `Table - Stream processing <https://convtools.readthedocs.io/en/latest/tables.html>`_

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

.. code-block:: python

    from convtools import conversion as c


    def test_doc__index_intro():

        # ======== #
        # GROUP BY #
        # ======== #
        input_data = [
            {"a": 5, "b": "foo"},
            {"a": 10, "b": "foo"},
            {"a": 10, "b": "bar"},
            {"a": 10, "b": "bar"},
            {"a": 20, "b": "bar"},
        ]

        conv = (
            c.group_by(c.item("b"))
            .aggregate(
                {
                    "b": c.item("b"),
                    "a_first": c.ReduceFuncs.First(c.item("a")),
                    "a_max": c.ReduceFuncs.Max(c.item("a")),
                }
            )
            .gen_converter(debug=True)
        )

        assert conv(input_data) == [
            {"b": "foo", "a_first": 5, "a_max": 10},
            {"b": "bar", "a_first": 10, "a_max": 20},
        ]

        # ========= #
        # AGGREGATE #
        # ========= #
        conv = c.aggregate(
            {
                # list of "a" values where "b" equals to "bar"
                "a": c.ReduceFuncs.Array(c.item("a"), where=c.item("b") == "bar"),
                # "b" value of a row where "a" has Max value
                "b": c.ReduceFuncs.MaxRow(
                    c.item("a"),
                ).item("b", default=None),
            }
        ).gen_converter(debug=True)

        assert conv(input_data) == {"a": [10, 10, 20], "b": "bar"}

        # ==== #
        # JOIN #
        # ==== #
        collection_1 = [
            {"id": 1, "name": "Nick"},
            {"id": 2, "name": "Joash"},
            {"id": 3, "name": "Bob"},
        ]
        collection_2 = [
            {"ID": "3", "age": 17, "country": "GB"},
            {"ID": "2", "age": 21, "country": "US"},
            {"ID": "1", "age": 18, "country": "CA"},
        ]
        input_data = (collection_1, collection_2)

        conv = (
            c.join(
                c.item(0),
                c.item(1),
                c.and_(
                    c.LEFT.item("id") == c.RIGHT.item("ID").as_type(int),
                    c.RIGHT.item("age") >= 18,
                ),
                how="left",
            )
            .pipe(
                c.list_comp(
                    {
                        "id": c.item(0, "id"),
                        "name": c.item(0, "name"),
                        "age": c.item(1, "age", default=None),
                        "country": c.item(1, "country", default=None),
                    }
                )
            )
            .gen_converter(debug=True)
        )

        assert conv(input_data) == [
            {"id": 1, "name": "Nick", "age": 18, "country": "CA"},
            {"id": 2, "name": "Joash", "age": 21, "country": "US"},
            {"id": 3, "name": "Bob", "age": None, "country": None},
        ]

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

Docs
====

* `convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
* `Cheatsheet <https://convtools.readthedocs.io/en/latest/cheatsheet.html>`_
* `QuickStart <https://convtools.readthedocs.io/en/latest/quick_start.html>`_
* `Table - Stream processing <https://convtools.readthedocs.io/en/latest/tables.html>`_

