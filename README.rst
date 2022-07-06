=========
convtools
=========

**convtools** is a python library to declaratively define data transforms:

* ``convtools.contrib.models`` - data validation based on ``typing`` -
  **experimental**
* ``convtools.contrib.tables`` - stream processing of table-like data (e.g.
  CSV)
* ``convtools.conversion`` - pipelines for processing collections, doing
  complex aggregations and joins.

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
* `Model - Data validation  <https://convtools.readthedocs.io/en/latest/models.html>`_

Why would you need this?
========================

* you prefer declarative approach
* you love functional programming
* you believe that Python is high-level enough not make you write aggregations
  and joins by hand
* you need to serialize/validate objects
* you need to dynamically define transforms (including at runtime)
* you like the idea of having something write ad hoc code for you


Installation:
=============

.. code-block:: bash

   pip install convtools


What's the workflow?
====================

**Contrib / Model** - data validation (**experimental**)

.. code-block:: python

   import typing as t
   from enum import Enum

   from convtools.contrib.models import DictModel, build, cast, json_dumps

   T = t.TypeVar("T")

   class Countries(Enum):
       MX = "MX"
       BR = "BR"


   class AddressModel(DictModel):
       country: Countries = cast()  # explicit casting to output type
       state: str                   # validation only
       city: t.Optional[str]
       street: t.Optional[str] = None

       # # in case of a custom path like: address["apt"]["number"]
       # apt: int = field("apt", "number").cast()


   class UserModel(DictModel):
       name: str
       age: int = cast()
       addresses: t.List[AddressModel]


   class ResponseModel(DictModel, t.Generic[T]):
       data: T


   input_data = {
       "data": [
           {
               "name": "John",
               "age": "21",
               "addresses": [{"country": "BR", "state": "SP", "city": "São Paulo"}],
           }
       ]
   }
   obj, errors = build(ResponseModel[t.List[UserModel]], input_data)

   In [4]: obj
   Out[4]: ResponseModel(data=[
               UserModel(name='John', age=21, addresses=[
                   AddressModel(country=<Countries.BR: 'BR'>, state='SP', city='São Paulo', street=None)])])

   In [5]: obj.data[0].addresses[0].country
   Out[5]: <Countries.BR: 'BR'>

   In [6]: obj.to_dict()
   Out[6]:
   {'data': [{'name': 'John',
      'age': 21,
      'addresses': [{'country': <Countries.BR: 'BR'>,
        'state': 'SP',
        'city': 'São Paulo',
        'street': None}]}]}

   In [7]: json_dumps(obj)
   Out[7]: '{"data": [{"name": "John", "age": 21, "addresses": [{"country": "BR", "state": "SP", "city": "S\\u00e3o Paulo", "street": null}]}]}'

.. code-block:: python

   # LET'S BREAK THE DATA AND VALIDATE AGAIN:
   input_data["data"][0]["age"] = 21.1
   obj, errors = build(ResponseModel[t.List[UserModel]], input_data)

   In [5]: errors
   Out[5]: {'data': {0: {'age': {'__ERRORS': {'int_caster': 'losing fractional part: 21.1; if desired, use casters.IntLossy'}}}}}


**Contrib / Table** - stream processing of table-like data

``Table`` helper allows to massage CSVs and table-like data:
 * join / zip / chain tables
 * take / drop / rename columns
 * filter rows
 * update / update_all values

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
   ).into_iter_rows(dict)  # this is a generator to consume (tuple, list are supported too)


**Conversions** - data transforms, complex aggregations, joins:

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
#. Percentile - ``c.ReduceFuncs.Percentile(95.0, c.item("x"))``
#. Mode
#. TopK - ``c.ReduceFuncs.TopK(3, c.item("x"))``
#. Array
#. ArrayDistinct
#. ArraySorted - ``c.ReduceFuncs.ArraySorted(c.item("x"), key=lambda v: v, reverse=True)``
#. Dict - ``c.ReduceFuncs.Dict(c.item("key"), c.item("x"))``
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
* convtools supports nested aggregations


Is this thing debuggable?
=========================

Despite being compiled at runtime, it is, by both ``pdb`` and ``pydevd``

Docs
====

* `convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
* `Cheatsheet <https://convtools.readthedocs.io/en/latest/cheatsheet.html>`_
* `QuickStart <https://convtools.readthedocs.io/en/latest/quick_start.html>`_
* `Table - Stream processing <https://convtools.readthedocs.io/en/latest/tables.html>`_
* `Model - Data validation  <https://convtools.readthedocs.io/en/latest/models.html>`_

