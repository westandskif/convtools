=========
convtools
=========

**convtools** is a python library to declaratively define conversions for
processing collections, doing complex aggregations and joins.

Once a conversion is defined, it can be compiled into an ad hoc code OR be
reused for building more complex conversions.

.. image:: https://img.shields.io/pypi/pyversions/convtools.svg
    :target: https://pypi.org/project/convtools/

.. image:: https://img.shields.io/github/license/itechart/convtools.svg
   :target: https://github.com/itechart/convtools/blob/master/LICENSE.txt

.. image:: https://codecov.io/gh/itechart/convtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/itechart/convtools

.. image:: https://github.com/itechart/convtools/workflows/tests/badge.svg
   :target: https://github.com/itechart/convtools/workflows/tests/badge.svg
   :alt: Tests Status

.. image:: https://readthedocs.org/projects/convtools/badge/?version=latest
   :target: https://convtools.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://img.shields.io/github/tag/itechart/convtools.svg
   :target: https://GitHub.com/itechart/convtools/tags/

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

What's the workflow?
====================

#. ``from convtools import conversion as c``
#. define conversions
#. (optional) store them somewhere for further reuse
#. call ``gen_converter`` method to compile the conversion into a function,
   written with an ad hoc code
#. (optional) it's totally fine to generate converters at runtime, for simple
   conversions it takes less than 0.1-0.2 milliseconds to get compiled.

Please, see simple examples of `group by`, `aggregate` and `join` conversions
below.

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

Also there are more after the **Installation** section.

Why would you need this?
========================
  * you love functional programming
  * you believe that Python is awesome enough to have powerful aggregations and
    joins
  * you need to serialize/deserialize objects
  * you need to define dynamic data transforms based on some input, which
    becomes available at runtime
  * you like the idea of having something else write an unpleasant ad hoc
    code for you
  * you want to reuse field-wise transformations across the project without
    worrying about huge overhead of calling tens of functions per row/object,
    especially when there are thousands of them to be processed


Is it any different from tools like Pandas?
===========================================

 * `convtools` doesn't need to wrap data in any container to provide useful API,
   it just writes ad hoc python code under the hood
 * `convtools` is a lightweight library with no dependencies (however optional
   ``black`` is highly recommended for pretty-printing generated code when
   debugging)
 * `convtools` is about defining and reusing conversions -- declarative
   approach, while wrapping data in high-performance containers is more of
   being imperative


Description
===========

The speed of **convtools** comes from the approach of generating code &
compiling conversion functions, which don't have any generic code like
superfluous loops, ifs, unnecessary function calls, etc.

So you can keep following the DRY principle by storing and reusing the code on
the python expression level, but at the same time be able to run the
``gen_converter`` and get the compiled code which doesn't care about being DRY
and is generated to be highly specialized for the specific need.

____

There are ``group_by`` & ``aggregate`` conversions with many useful reducers:

 * from common `Sum`, `Max`
 * and less widely supported `First`/`Last`, `Array`/`ArrayDistinct`
 * to `DictSum`-like ones (for nested aggregation) and `MaxRow`/`MinRow`
   (for finding an object with max/min value and further processing)

There is a ``join`` conversion (inner, left, right, outer, cross are
supported), which processes 2 iterables and returns a generator of joined
pairs.

Thanks to pipes & labels it's possible to define multiple pipelines of data
processing, including branching and merging of them.

Tapping allows to add mutation steps not to rebuild objects from the scratch at
every step.

____

Every conversion:
 * contains the information of how to transform an input
 * can be **piped** into another conversion (same as wrapping)
 * has a method ``gen_converter`` returning a function compiled at runtime
 * despite being compiled at runtime, it remains debuggable with both `pdb` and `pydevd`


Installation:
=============

.. code-block:: bash

   pip install convtools

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

        # get by "department" key and then call method "strip"
        department = c.item("department").call_method("strip")
        first_name = c.item("first_name").call_method("capitalize")
        last_name = c.item("last_name").call_method("capitalize")

        # call "format" method of a string and pass first & last names as
        # parameters
        full_name = c("{} {}").call_method("format", first_name, last_name)
        date_of_birth = c.item("dob")

        # partially initialized "strptime"
        parse_date = c.call_func(
            datetime.strptime, c.this(), "%Y-%m-%d"
        ).call_method("date")

        conv = (
            c.item("objects")
            .pipe(
                c.generator_comp(
                    {
                        "id": c.item("id"),
                        "first_name": first_name,
                        "last_name": last_name,
                        "full_name": full_name,
                        "date_of_birth": c.if_(
                            date_of_birth,
                            date_of_birth.pipe(parse_date),
                            None,
                        ),
                        "salary": c.call_func(
                            Decimal,
                            c.item("salary").call_method("replace", ",", ""),
                        ),
                        # pass a hardcoded dict and to get value by "department"
                        # key
                        "department_id": c.naive(
                            {
                                "D1": 10,
                                "D2": 11,
                                "D3": 12,
                            }
                        ).item(department),
                        "date": c.item("date").pipe(parse_date),
                    }
                )
            )
            .pipe(
                c.dict_comp(
                    c.item("id"),  # key
                    # write a python code expression, format with passed parameters
                    c.inline_expr("{employee_cls}(**{kwargs})").pass_args(
                        employee_cls=Employee,
                        kwargs=c.this(),
                    ),  # value
                )
            )
            .gen_converter(debug=True)
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

Under the hood the compiled code is as follows:

.. code-block:: python

   def converter_2n(data_):
       global labels_
       return {
           i_0t["id"]: (Employee_vk(**i_0t))
           for i_0t in (
               {
                   "id": i_n7["id"],
                   "first_name": i_n7["first_name"].capitalize(),
                   "last_name": i_n7["last_name"].capitalize(),
                   "full_name": "{} {}".format(
                       i_n7["first_name"].capitalize(),
                       i_n7["last_name"].capitalize(),
                   ),
                   "date_of_birth": (
                       (
                           strptime_db(i_n7["dob"], "%Y-%m-%d").date()
                           if i_n7["dob"]
                           else None
                       )
                   ),
                   "salary": Decimal_tr(i_n7["salary"].replace(",", "")),
                   "department_id": v_g6[i_n7["department"].strip()],
                   "date": strptime_db(i_n7["date"], "%Y-%m-%d").date(),
               }
               for i_n7 in data_["objects"]
           )
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

**Generated code:**

.. code-block:: python

   def aggregate__ao(data_):
       global labels_
       _none = v_vl
       agg_data__ao_v0 = _none
       expected_checksum_ = 1
       checksum_ = 0
       it_ = iter(data_)

       for row__ao in it_:
           if agg_data__ao_v0 is _none:
               agg_data__ao_v0 = {row__ao: 1}
               break

       for row__ao in it_:
           if row__ao not in agg_data__ao_v0:
               agg_data__ao_v0[row__ao] = 1
           else:
               agg_data__ao_v0[row__ao] = agg_data__ao_v0[row__ao] + 1

       return dict() if agg_data__ao_v0 is _none else agg_data__ao_v0


   def pipe__ho(input__ho, top_n):
       global labels_
       return (
           dict(
               sorted(input__ho.items(), key=lambda_0r, reverse=True)[
                   (slice(None, top_n, None))
               ]
           )
           if (top_n is not None)
           else input__ho
       )


   def converter_dg(data_, top_n=None):
       global labels_
       return pipe__ho(
           aggregate__ao(
               from_iterable_tq(
                   (
                       (i_3u.group(0).lower() for i_3u in v_vq.finditer(i_zs))
                       for i_zs in from_iterable_tq(
                           (lambda_cq(i_y4) for i_y4 in data_)
                       )
                   )
               )
           ),
           top_n,
       )

Docs
====

 * `convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
 * `Cheatsheet <https://convtools.readthedocs.io/en/latest/cheatsheet.html>`_
 * `QuickStart <https://convtools.readthedocs.io/en/latest/quick_start.html>`_

