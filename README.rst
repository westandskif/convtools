=========
convtools
=========

**convtools** is a python library to declaratively define pipelines for
processing collections, doing complex aggregations and joins. It also provides
a helper for stream processing of table-like data (e.g. CSV).

Conversions foster extensive code reuse. Once defined, these generate ad hoc
code with as much inlining as possible and return compiled ad hoc functions
`(with superfluous loops and conditions removed)`.

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

.. image:: https://pepy.tech/badge/convtools
   :target: https://pepy.tech/project/convtools
   :alt: Downloads

.. image:: https://badges.gitter.im/python-convtools/community.svg
   :target: https://gitter.im/python-convtools/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge
   :alt: Chat on Gitter

Docs
====

* `convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
* `Cheatsheet <https://convtools.readthedocs.io/en/latest/cheatsheet.html>`_
* `QuickStart <https://convtools.readthedocs.io/en/latest/quick_start.html>`_
* `Table - Stream processing <https://convtools.readthedocs.io/en/latest/tables.html>`_

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

.. code-block:: python

    from datetime import date, datetime
    from decimal import Decimal

    from convtools import conversion as c


    def test_doc__index_deserialization():
        class Employee:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        input_data = {
            "objects": [
                {
                    "id": 1,
                    "first_name": "john",
                    "last_name": "black",
                    "dob": None,
                    "salary": "1,000.00",
                    "department": "D1 ",
                    "date": "2000-01-01",
                },
                {
                    "id": 2,
                    "first_name": "bob",
                    "last_name": "wick",
                    "dob": "1900-01-01",
                    "salary": "1,001.00",
                    "department": "D3 ",
                    "date": "2000-01-01",
                },
            ]
        }

        # prepare a few conversions to reuse
        c_strip = c.this().call_method("strip")
        c_capitalize = c.this().call_method("capitalize")
        c_decimal = c.this().call_method("replace", ",", "").as_type(Decimal)
        c_date = c.call_func(datetime.strptime, c.this(), "%Y-%m-%d").call_method(
            "date"
        )
        # reusing c_date
        c_optional_date = c.if_(c.this(), c_date, None)

        first_name = c.item("first_name").pipe(c_capitalize)
        last_name = c.item("last_name").pipe(c_capitalize)
        # call "format" method of a string and pass first & last names as
        # parameters
        full_name = c("{} {}").call_method("format", first_name, last_name)

        conv = (
            c.item("objects")
            .pipe(
                c.generator_comp(
                    {
                        "id": c.item("id"),
                        "first_name": first_name,
                        "last_name": last_name,
                        "full_name": full_name,
                        "date_of_birth": c.item("dob").pipe(c_optional_date),
                        "salary": c.item("salary").pipe(c_decimal),
                        # pass a hardcoded dict and to get value by "department"
                        # key
                        "department_id": c.naive(
                            {
                                "D1": 10,
                                "D2": 11,
                                "D3": 12,
                            }
                        ).item(c.item("department").pipe(c_strip)),
                        "date": c.item("date").pipe(c_date),
                    }
                )
            )
            .pipe(
                c.dict_comp(
                    c.item("id"),  # key
                    c.apply_func(  # value
                        Employee,
                        args=(),
                        kwargs=c.this(),
                    ),
                )
            )
            .gen_converter(debug=True)  # to see print generated code
        )

        result = conv(input_data)
        assert result[1].kwargs == {
            "date": date(2000, 1, 1),
            "date_of_birth": None,
            "department_id": 10,
            "first_name": "John",
            "full_name": "John Black",
            "id": 1,
            "last_name": "Black",
            "salary": Decimal("1000.00"),
        }
        assert result[2].kwargs == {
            "date": date(2000, 1, 1),
            "date_of_birth": date(1900, 1, 1),
            "department_id": 12,
            "first_name": "Bob",
            "full_name": "Bob Wick",
            "id": 2,
            "last_name": "Wick",
            "salary": Decimal("1001.00"),
        }

All-in-one example #2: word count
=================================

.. code-block:: python

    import re
    from itertools import chain

    from convtools import conversion as c


    def test_doc__index_word_count():

        # Let's say we need to count words across all files
        input_data = [
            "war-and-peace-1.txt",
            "war-and-peace-2.txt",
            "war-and-peace-3.txt",
            "war-and-peace-4.txt",
        ]

        # # iterate an input and read file lines
        #
        # def read_file(filename):
        #     with open(filename) as f:
        #         for line in f:
        #             yield line
        # extract_strings = c.generator_comp(c.call_func(read_file, c.this()))

        # to simplify testing
        extract_strings = c.generator_comp(
            c.call_func(lambda filename: [filename], c.this())
        )

        # 1. make ``re`` pattern available to the code to be generated
        # 2. call ``finditer`` method of the pattern and pass the string
        #    as an argument
        # 3. pass the result to the next conversion
        # 4. iterate results, call ``.group()`` method of each re.Match
        #    and call ``.lower()`` on each result
        split_words = (
            c.naive(re.compile(r"\w+"))
            .call_method("finditer", c.this())
            .pipe(
                c.generator_comp(
                    c.this().call_method("group", 0).call_method("lower")
                )
            )
        )

        # ``extract_strings`` is the generator of strings
        # so we iterate it and pass each item to ``split_words`` conversion
        vectorized_split_words = c.generator_comp(c.this().pipe(split_words))

        # flattening the result of ``vectorized_split_words``, which is
        # a generator of generators of strings
        flatten = c.call_func(
            chain.from_iterable,
            c.this(),
        )

        # aggregate the input, the result is a single dict
        # words are keys, values are count of words
        dict_word_to_count = c.aggregate(
            c.ReduceFuncs.DictCount(c.this(), c.this(), default=dict)
        )

        # take top N words by:
        #  - call ``.items()`` method of the dict (the result of the aggregate)
        #  - pass the result to ``sorted``
        #  - take the slice, using input argument named ``top_n``
        #  - cast to a dict
        take_top_n = (
            c.this()
            .call_method("items")
            .sort(key=lambda t: t[1], reverse=True)
            .pipe(c.this()[: c.input_arg("top_n")])
            .as_type(dict)
        )

        # the resulting pipeline is pretty self-descriptive, except the ``c.if_``
        # part, which checks the condition (first argument),
        # and returns the 2nd if True OR the 3rd (input data by default) otherwise
        pipeline = (
            extract_strings.pipe(flatten)
            .pipe(vectorized_split_words)
            .pipe(flatten)
            .pipe(dict_word_to_count)
            .pipe(
                c.if_(
                    c.input_arg("top_n").is_not(None),
                    c.this().pipe(take_top_n),
                )
            )
            # Define the resulting converter function signature.  In fact this
            # isn't necessary if you don't need to specify default values
        ).gen_converter(debug=True, signature="data_, top_n=None")

        assert pipeline(input_data, top_n=3) == {"war": 4, "and": 4, "peace": 4}

Docs
====

* `convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
* `Cheatsheet <https://convtools.readthedocs.io/en/latest/cheatsheet.html>`_
* `QuickStart <https://convtools.readthedocs.io/en/latest/quick_start.html>`_
* `Table - Stream processing <https://convtools.readthedocs.io/en/latest/tables.html>`_

