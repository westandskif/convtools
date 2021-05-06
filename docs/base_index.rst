What's the workflow?
====================

 1. ``from convtools import conversion as c``
 2. define conversions
 3. (optional) store them somewhere for further reuse
 4. call ``gen_converter`` method to compile the conversion into a function,
    written with an ad hoc code
 5. (optional) it's totally fine to generate converters at runtime, for simple
    conversions it takes less than 0.1-0.2 milliseconds to get compiled.

Please, see simple examples of `group by`, `aggregate` and `join` conversions
below.

.. include:: ../tests/test_doc__index_intro.py
   :code: python

Also there are more after the **Installation** section.

Why would you need this?
========================

 * you believe that Python is awesome enough to have powerful aggregations and
   joins
 * you like the idea of having something else write an unpleasant ad hoc
   code for you
 * you need to serialize/deserialize objects
 * you need to define dynamic data transforms based on some input, which
   becomes available at runtime
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
 * can be labeled to be reused further in the conversions chain
 * has a method ``gen_converter`` returning a function compiled at runtime
 * despite being compiled at runtime, is debuggable with `pdb` due to `linecache` populating.


Installation:
=============

.. code-block:: bash

   pip install convtools

All-in-one example #1: deserialization & data preps
===================================================

.. include:: ../tests/test_doc__index_deserialization.py
   :code: python


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

.. include:: ../tests/test_doc__index_word_count.py
   :code: python


**Generated code:**

.. code-block:: python

   def aggregate_u5(data_):
       global labels_
       _none = v_lj
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
                   agg_data_v0_[row_] = agg_data_v0_[row_] + 1

       for row_ in it_:

           if row_ not in agg_data_v0_:
               agg_data_v0_[row_] = 1
           else:
               agg_data_v0_[row_] = agg_data_v0_[row_] + 1

       result_ = dict() if agg_data_v0_ is _none else agg_data_v0_

       return result_


   def pipe_2h(input_om, top_n):
       global labels_
       return (
           dict(
               sorted(input_om.items(), key=lambda_ik, reverse=True)[
                   (slice(None, top_n, None))
               ]
           )
           if (top_n is not None)
           else input_om
       )


   def converter_wz(data_, top_n=None):
       global labels_
       return pipe_2h(
           aggregate_u5(
               from_iterable_c4(
                   (
                       (i_ry.group(0).lower() for i_ry in v_ql.finditer(i_fi))
                       for i_fi in from_iterable_c4(
                           (lambda_6b(i_jq) for i_jq in data_)
                       )
                   )
               )
           ),
           top_n,
       )
