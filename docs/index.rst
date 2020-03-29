=========
convtools
=========

.. _ref_index_intro:

**convtools** is a python library to declaratively define fast conversions
from python objects to python objects, including processing collections and
doing complex aggregations and joins.

Once defined, the conversion can be compiled into an ad hoc code OR be reused for
building more complex conversions.


What's the workflow?
====================

 1. ``from convtools import conversion as c``
 2. define conversions
 3. (optional) store them somewhere for further reuse
 4. call ``gen_converter`` method to compile the conversion into a function,
    written with an ad hoc code
 5. (optional) it's totally fine to generate converters at runtime, for simple
    conversions it takes less than 0.1-0.2 milliseconds to get compiled.

.. code-block:: python

   input_data = [
       {'a': 5,  'b': 'foo'},
       {'a': 10, 'b': 'bar'},
       {'a': 10, 'b': 'bar'}
   ]

   conv = c.aggregate({
       "a": c.reduce(c.ReduceFuncs.Array, c.item("a")),
       "a_sum": c.reduce(c.ReduceFuncs.Sum, c.item("a")),
       "b": c.reduce(c.ReduceFuncs.ArrayDistinct, c.item("b")),
   }).gen_converter()

   conv(input_data) == {
       'a': [5, 10, 10],
       'a_sum': 25,
       'b': ['foo', 'bar']
   }

Why would you need this?
========================

 * you need to serialize some objects
 * you need to define data transformations based on some input,
   which becomes available at runtime
 * you want to reuse field-wise transformations across the project without
   worrying about huge overhead of calling tens of functions per row/object,
   especially when there are thousands of them to be processed
 * you believe that Python is awesome enough to have powerful aggregations and
   joins
 * you like the idea of having something else write an unpleasant ad hoc
   code for you


Is it any different from tools like Pandas?
===========================================

 * `convtools` doesn't need to wrap data in any container to provide useful API,
   it just writes normal python code under the hood
 * `convtools` is a lightweight library with no dependencies (however optional
   ``black`` is highly recommended for pretty-printing generated code
   when debugging)
 * `convtools` is about defining and reusing conversions -- declarative approach,
   while wrapping data in high-performance containers is more of being imperative


Description
===========

The speed of **convtools** comes from the approach of generating code & compiling
conversion functions, which don't have any generic code like superfluous
loops, ifs, etc.

.. note::

  So you can follow the DRY principle by storing and reusing the code on the
  python expression level, but at the same time be able to run the
  ``gen_converter`` and get the compiled code which doesn't care about being DRY
  and is generated to be highly specialized for the specific need.

Thanks to pipes & labels it's possible to define multiple pipelines of data
processing, including branching and merging of them.


Conversions are not limited to simple data transformations, there are
``GroupBy`` & ``Aggregate`` conversions with many useful reducers:

 * from common `Sum`, `Max`
 * and less widely supported `First`/`Last`, `Array`/`ArrayDistinct`
 * to `DictSum`-like ones (for nested aggregation) and `MaxRow`/`MinRow`
   (for finding an object with max/min value and further processing)

Also there are higher-level conversions - JOINS
(inner, left, right, outer, cross), which processes 2 iterables and returns
a generator of joined pairs.

Every conversion:
 * contains the information of how to transform an input
 * can be **piped** into another conversion (same as wrapping)
 * can be labeled to be reused further in the conversions chain
 * has a method ``gen_converter`` returning a function compiled at runtime
 * despite being compiled at runtime, is debuggable with `pdb` due to `linecache` populating.


Installation:
=============

.. code-block:: bash

   pip install convtools


Example #1: deserialization & data preps
========================================

.. code-block:: python

   # get by "department" key and then call method "strip"
   department = c.item("department").call_method("strip")
   first_name = c.item("first_name").call_method("capitalize")
   last_name = c.item("last_name").call_method("capitalize")

   # call "format" method of a string and pass first & last names as parameters
   full_name = c("{} {}").call_method("format", first_name, last_name)
   date_of_birth = c.item("dob")

   # partially initialized "strptime"
   parse_date = c.call_func(
       datetime.strptime,
       c.this(),
       "%Y-%m-%d"
   ).call_method("date")

   c.item("objects").pipe(
       c.generator_comp({
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
               c.item("salary").call_method("replace", ",", "")
           ),
           # pass a hardcoded dict and to get value by "department" key
           "department_id": c.naive({
               "D1": 10,
               "D2": 11,
               "D3": 12,
           }).item(department),
           "date": c.item("date").pipe(parse_date),
       })
   ).pipe(
       c.dict_comp(
           c.item("id"), # key
           # write a python code expression, format with passed parameters
           c.inline_expr("{employee_cls}(**{kwargs})").pass_args(
               employee_cls=Employee,
               kwargs=c.this(),
           ),            # value
       )
   ).gen_converter(debug=True)

Gets compiled into:

.. code-block:: python

   def converter705_580(data_):
       global add_label_, get_by_label_
       pipe705_68 = data_["objects"]
       pipe705_973 = (
           {
               "id": i703_861["id"],
               "first_name": i703_861["first_name"].capitalize(),
               "last_name": i703_861["last_name"].capitalize(),
               "full_name": "{} {}".format(
                   i703_861["first_name"].capitalize(),
                   i703_861["last_name"].capitalize(),
               ),
               "date_of_birth": (
                   strptime494_480(i703_861["dob"], "%Y-%m-%d").date()
                   if i703_861["dob"]
                   else None
               ),
               "salary": Decimal731_432(i703_861["salary"].replace(",", "")),
               "department_id": v677_416[i703_861["department"].strip()],
               "date": strptime494_480(i703_861["date"], "%Y-%m-%d").date(),
           }
           for i703_861 in pipe705_68
       )
       return {
           i705_330["id"]: (Employee700_725(**i705_330))
           for i705_330 in pipe705_973
       }

Example #2: word count
======================

.. code-block:: python

   import re
   from itertools import chain

   # the suggested way of importing convtolls
   from convtools import conversion as c

   # Let's say we need to count words across all files
   input_data = [
       "war-and-peace-1.txt",
       "war-and-peace-2.txt",
       "war-and-peace-3.txt",
       "war-and-peace-4.txt",
   ]
   def read_file(filename):
       with open(filename) as f:
           for line in f:
               yield line

   # iterate an input and read file lines
   extract_strings = c.generator_comp(
       c.call_func(read_file, c.this())
   )

   # 1. make ``re`` pattern available to the code to be generated
   # 2. call ``finditer`` method of the pattern and pass the string
   #    as an argument
   # 3. pass the result to the next conversion
   # 4. iterate results, call ``.group()`` method of each re.Match
   #    and call ``.lower()`` on each result
   split_words = (
       c.naive(re.compile(r'\w+')).call_method("finditer", c.this())
       .pipe(
           c.generator_comp(
               c.this().call_method("group", 0).call_method("lower")
           )
       )
   )

   # ``extract_strings`` is the generator of strings
   # so we iterate it and pass each item to ``split_words`` conversion
   vectorized_split_words = c.generator_comp(
       c.this().pipe(
           split_words
       )
   )

   # flattening the result of ``vectorized_split_words``, which is
   # a generator of generators of strings
   flatten = c.call_func(
       chain.from_iterable,
       c.this(),
   )

   # aggregate the input, the result is a single dict
   # words are keys, values are count of words
   dict_word_to_count = c.aggregate(
       c.reduce(
           c.ReduceFuncs.DictCount,
           (c.this(), c.this()),
           default=dict
       )
   )

   # take top N words by:
   #  - call ``.items()`` method of the dict (the result of the aggregate)
   #  - pass the result to ``sorted``
   #  - take the slice, using input argument named ``top_n``
   #  - cast to a dict
   take_top_n = (
       c.this().call_method("items")
       .pipe(sorted, key=lambda t: t[1], reverse=True)
       .pipe(c.this()[:c.input_arg("top_n")])
       .as_type(dict)
   )

   # the resulting pipeline is pretty self-descriptive, except the ``c.if_``
   # part, which checks the condition (first argument),
   # and returns the 2nd if True OR the 3rd (input data by default) otherwise
   pipeline = (
       extract_strings
       .pipe(flatten)
       .pipe(vectorized_split_words)
       .pipe(flatten)
       .pipe(dict_word_to_count)
       .pipe(
           c.if_(
               c.input_arg("top_n").is_not(None),
               c.this().pipe(take_top_n),
           )
       )
   # Define the resulting converter function signature.
   # In fact this isn't necessary if you don't need to specify default values
   ).gen_converter(debug=True, signature="data_, top_n=None")

   # check the speed yourself :)
   # e.g. take a look in txt format and tune the ``extract_strings``
   # conversion as needed
   pipeline(input_data, top_n=3)


**Generated code:**

.. code-block:: python

   def aggregate(data_):
       global add_label_, get_by_label_
       _none = v123_497
       agg_data_v0_ = _none
       expected_checksum_ = 1
       checksum_ = 0
       it_ = iter(data_)
       for row_ in it_:

           if agg_data_v0_ is _none:
               agg_data_v0_ = {row_: 1}

               if agg_data_v0_ is not _none:
                   checksum_ |= 1
                   if checksum_ == expected_checksum_:
                       break

           else:
               if row_ not in agg_data_v0_:
                   agg_data_v0_[row_] = 1
               else:
                   agg_data_v0_[row_] += 1

       for row_ in it_:

           if row_ not in agg_data_v0_:
               agg_data_v0_[row_] = 1
           else:
               agg_data_v0_[row_] += 1

       result_ = dict() if agg_data_v0_ is _none else agg_data_v0_

       return result_


   def converter459_881(data_, top_n=None):
       pipe459_557 = (read_file376_398(i458_940) for i458_940 in data_)
       pipe459_694 = from_iterable401_690(pipe459_557)
       pipe459_916 = (
           (i397_760.group(0).lower() for i397_760 in v379_129.finditer(i456_473))
           for i456_473 in pipe459_694
       )
       pipe459_431 = from_iterable401_690(pipe459_916)
       pipe459_970 = aggregate469_287(pipe459_431)
       return (
           dict(
               (
                   sorted(pipe459_970.items(), key=lambda418_804, reverse=True)[
                       (slice(None, top_n, None))
                   ]
               )
           )
           if (top_n is not None)
           else pipe459_970
       )

Next steps:
===========

 1. :ref:`QuickStart<convtools_quickstart>`
 2. :ref:`Cheatsheet<convtools_cheatsheet>`
 3. :ref:`API doc<convtools_api_doc>`


Contents
========

.. toctree::
   :maxdepth: 2

   QuickStart <quick_start>
   Cheatsheet <cheatsheet>
   API doc <api_doc>

.. toctree::
   :maxdepth: 1

   License <license>
   Authors <authors>
   Changelog <changelog>
   Module Reference <api/modules>

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _toctree: http://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html
.. _reStructuredText: http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html
.. _references: http://www.sphinx-doc.org/en/stable/markup/inline.html
.. _Python domain syntax: http://sphinx-doc.org/domains.html#the-python-domain
.. _Sphinx: http://www.sphinx-doc.org/
.. _Python: http://docs.python.org/
.. _Numpy: http://docs.scipy.org/doc/numpy
.. _SciPy: http://docs.scipy.org/doc/scipy/reference/
.. _matplotlib: https://matplotlib.org/contents.html#
.. _Pandas: http://pandas.pydata.org/pandas-docs/stable
.. _Scikit-Learn: http://scikit-learn.org/stable
.. _autodoc: http://www.sphinx-doc.org/en/stable/ext/autodoc.html
.. _Google style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings
.. _NumPy style: https://numpydoc.readthedocs.io/en/latest/format.html
.. _classical style: http://www.sphinx-doc.org/en/stable/domains.html#info-field-lists
