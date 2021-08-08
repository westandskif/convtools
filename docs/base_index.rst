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

.. include:: ../tests/test_doc__index_intro.py
   :code: python

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
