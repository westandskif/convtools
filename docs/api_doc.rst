.. _convtools_api_doc:

=================
convtools API Doc
=================

For the sake of conciseness, let's assume the following import statement is in place:

.. code-block:: python

 from convtools import conversion as c

This is an object which exposes public API.

.. _ref_c_base_conversion:

c.BaseConversion
================

 .. autoclass:: convtools.base.BaseConversion()
    :noindex:

 .. _ref_c_gen_converter:

 .. automethod:: convtools.base.BaseConversion.gen_converter
    :noindex:

 .. note::

  At first use ``.gen_converter(debug=True)`` everywhere to see the
  generated code


.. _ref_optionsctx:

c.OptionsCtx
============

 .. autoattribute:: convtools.conversion.OptionsCtx

 .. autoclass:: convtools.base.ConverterOptionsCtx()
    :noindex:

 .. autoclass:: convtools.base.ConverterOptions()
    :noindex:




.. _ref_c_this:

c.this
======

 .. automethod:: convtools.conversion.this


.. _ref_c_input_arg:

c.input_arg
===========

 .. autoattribute:: convtools.conversion.input_arg

 .. autoclass:: convtools.base.InputArg()
  :noindex:

 .. automethod:: convtools.base.InputArg.__init__


**Example of changing the signature:**

 .. code-block:: python

  c.this().and_(
      c.input_arg("x").as_type(int)
  ).or_(None).gen_converter(
      debug=True,
      signature="x, data_",
  )
  # is compiled to
  def converter37_306(x, data_):
      return (data_ and int(x)) or None

.. _ref_c_naive:

c.naive
=======

 .. automethod:: convtools.conversion.naive()

 .. autoclass:: convtools.base.NaiveConversion()
    :noindex:

 .. automethod:: convtools.base.NaiveConversion.__init__(value)


.. _ref_c_wrapper:

c() wrapper
===========

 .. automethod:: convtools.conversion.__call__

 .. automethod:: convtools.base.ensure_conversion
    :noindex:

 .. note::
    It is used under the hood on every argument passed to any conversion.


.. _ref_c_item:

c.item
======

 .. autoattribute:: convtools.conversion.item

 .. autoclass:: convtools.base.GetItem()
    :noindex:

 .. automethod:: convtools.base.GetItem.__init__


.. _ref_c_attr:

c.attr
======

``c.attr`` works the same as :py:obj:`convtools.base.GetItem`, but for
getting attributes.

.. autoattribute:: convtools.conversion.attr

.. autoclass:: convtools.base.GetAttr()
   :noindex:

.. automethod:: convtools.base.GetAttr.__init__


.. _ref_c_calls:

call_func, call and call_method
===============================

There are 3 different actions related to calling something:

**1. c.call -- Calling __call__ of an input**

 .. automethod:: convtools.base.BaseConversion.call
    :noindex:

**2. c.call_func -- Regular function calling, passing a function to call**

 .. autoattribute:: convtools.conversion.call_func

 .. autofunction:: convtools.base.CallFunc
    :noindex:

**3. (...).call_method -- Calling a method of an input**

 .. automethod:: convtools.base.BaseConversion.call_method
    :noindex:


.. _ref_c_inline_expr:

c.inline_expr
=============

``c.inline_expr`` is used to inline a raw python expression into
the code of resulting conversion, to avoid function call overhead.

.. autoattribute:: convtools.conversion.inline_expr

.. autoclass:: convtools.base.InlineExpr()
   :noindex:

.. automethod:: convtools.base.InlineExpr.__init__

.. automethod:: convtools.base.InlineExpr.pass_args
   :noindex:


.. _ref_c_operators:

Conversion methods/operators
============================

Wraps conversions with logical / math / comparison operators

.. code-block:: python

 # logical
 c.not_(conversion)
 c.or_(*conversions)
 c.and_(*conversions)

 c.this()[conv1:conv2:conv3]       # slices

 c.this().or_(*conversions)        # OR c.this() | ...
 c.this().and_(*conversions)       # OR c.this() & ...
 c.this().not_()                   # OR ~c.this()
 c.this().is_(conversion)
 c.this().is_not(conversion)
 c.this().in_(conversion)
 c.this().not_in(conversion)

 # comparisons
 c.this().eq(conversion)           # OR c.this() == ...
 c.this().not_eq(conversion)       # OR c.this() != ...
 c.this().gt(conversion)           # OR c.this() > ...
 c.this().gte(conversion)          # OR c.this() >= ...
 c.this().lt(conversion)           # OR c.this() < ...
 c.this().lte(conversion)          # OR c.this() <= ...

 # math
 c.this().neg()                    # OR -c.this()
 c.this().add(conversion)          # OR c.this() + ...
 c.this().mul(conversion)          # OR c.this() * ...
 c.this().sub(conversion)          # OR c.this() - ...
 c.this().div(conversion)          # OR c.this() / ...
 c.this().mod(conversion)          # OR c.this() % ...
 c.this().floor_div(conversion)    # OR c.this() // ...


.. _ref_c_collections:

Collections
===========
Converts an input into a collection, same is achievable by using
`c() wrapper`_, see below:

 * **c.list or c([])**

  .. autoattribute:: convtools.conversion.list

  .. autoclass:: convtools.base.List()
     :noindex:

  .. automethod:: convtools.base.List.__init__

 * **c.tuple or c(())**

  .. autoattribute:: convtools.conversion.tuple

  .. autoclass:: convtools.base.Tuple()
     :noindex:

  .. automethod:: convtools.base.Tuple.__init__

 * **c.set or c(set())**

  .. autoattribute:: convtools.conversion.set

  .. autoclass:: convtools.base.Set()
     :noindex:

  .. automethod:: convtools.base.Set.__init__

 * **c.dict or c({})**

  .. autoattribute:: convtools.conversion.dict

  .. autoclass:: convtools.base.Dict()
     :noindex:

  .. automethod:: convtools.base.Dict.__init__


.. _ref_c_optionals:

Optional items:
+++++++++++++++

  .. autoattribute:: convtools.conversion.optional

  .. autoclass:: convtools.base.OptionalCollectionItem()
     :noindex:

  .. automethod:: convtools.base.OptionalCollectionItem.__init__


.. _ref_comprehensions:

Comprehensions
==============

.. autoclass:: convtools.base.BaseComprehensionConversion()
   :noindex:

   .. automethod:: convtools.base.BaseComprehensionConversion.__init__
      :noindex:

   .. automethod:: convtools.base.BaseComprehensionConversion.filter
      :noindex:

   .. automethod:: convtools.base.BaseComprehensionConversion.sort
      :noindex:


.. autoattribute:: convtools.conversion.list_comp

 .. autoclass:: convtools.base.ListComp()
   :noindex:

.. autoattribute:: convtools.conversion.tuple_comp

 .. autoclass:: convtools.base.TupleComp()
  :noindex:

.. autoattribute:: convtools.conversion.set_comp

 .. autoclass:: convtools.base.SetComp()
  :noindex:

.. autoattribute:: convtools.conversion.dict_comp

 .. autoclass:: convtools.base.DictComp()
  :noindex:
 .. automethod:: convtools.base.DictComp.__init__


.. _ref_c_filter:

c.filter
========

.. automethod:: convtools.conversion.filter
   :noindex:
.. automethod:: convtools.base.BaseConversion.filter
   :noindex:


.. _ref_labels:

c.label
=======

.. autoattribute:: convtools.conversion.label
   :noindex:

.. autoclass:: convtools.base.LabelConversion()
   :noindex:

   .. automethod:: convtools.base.LabelConversion.__init__
      :noindex:

____

.. autoclass:: convtools.base.CachingConversion()
   :noindex:

   .. automethod:: convtools.base.CachingConversion.__init__
      :noindex:
   .. automethod:: convtools.base.CachingConversion.add_label
      :noindex:


.. _ref_pipes:

Pipes
=====

.. automethod:: convtools.base.BaseConversion.pipe
   :noindex:


.. _ref_c_conditions:

Conditions
==========

 * **IF expressions**

     .. autoattribute:: convtools.conversion.if_

     .. autoclass:: convtools.base.If()
        :noindex:

     .. automethod:: convtools.base.If.__init__

 * **AND/OR expressions**
     .. autoattribute:: convtools.conversion.and_
     .. autoattribute:: convtools.conversion.or_

     .. autoclass:: convtools.base.And()
        :noindex:

     .. autoclass:: convtools.base.Or()
        :noindex:

     .. automethod:: convtools.base.And.__init__
     .. automethod:: convtools.base.Or.__init__


.. _ref_c_aggregations:

c.group_by, c.aggregate & c.reduce
==================================


c.group_by
__________

.. _ref_c_group_by:

.. autoattribute:: convtools.conversion.group_by

  .. autoclass:: convtools.aggregations.GroupBy()
     :noindex:

  .. automethod:: convtools.aggregations.GroupBy.__init__
     :noindex:

  .. automethod:: convtools.aggregations.GroupBy.aggregate
     :noindex:

  .. automethod:: convtools.aggregations.GroupBy.filter
     :noindex:

  .. automethod:: convtools.aggregations.GroupBy.sort
     :noindex:


.. _ref_c_aggregate:

c.aggregate
___________

.. autoattribute:: convtools.conversion.aggregate

   .. autofunction:: convtools.aggregations.Aggregate


.. _ref_c_reduce:

c.reduce
________

.. autoattribute:: convtools.conversion.reduce

  .. autoclass:: convtools.aggregations.Reduce()
     :noindex:

  .. automethod:: convtools.aggregations.Reduce.__init__
     :noindex:

  .. automethod:: convtools.aggregations.Reduce.filter
     :noindex:

Examples:

.. code-block:: python

   converter = c.group_by(c.item("category")).aggregate({
       "category": c.item("category").call_method("upper"),
       "earnings": c.reduce(
           c.ReduceFuncs.Sum,
           c.item("earnings").as_type(Decimal),
       ),
       "best_day": c.reduce(
           c.ReduceFuncs.MaxRow,
           c.item("earnings").as_type(float),
       ).item("date").pipe(datetime.strptime, "%Y-%m-%d"),
   }).gen_converter(debug=True)
   # list of dicts
   converter(data)

   converter = c.aggregate({
       "category": c.reduce(
           c.ReduceFuncs.ArrayDistinct,
           c.item("category").call_method("upper"),
       ),
       "earnings": c.reduce(
           c.ReduceFuncs.Sum,
           c.item("earnings").as_type(Decimal),
       ),
       "best_day": c.reduce(
           c.ReduceFuncs.MaxRow,
           c.item("earnings").as_type(float),
       ).item("date").pipe(datetime.strptime, "%Y-%m-%d"),
   }).gen_converter(debug=True)
   # a single dict
   converter(data)


.. _ref_c_reduce_funcs:

c.ReduceFuncs
_____________

.. autoclass:: convtools.aggregations.ReduceFuncs
   :noindex:

   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Sum
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.SumOrNone
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Max
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.MaxRow
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Min
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.MinRow
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Count
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.CountDistinct
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.First
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Last
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Array
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.ArrayDistinct
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.Dict
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictArray
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictArrayDistinct
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictSum
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictSumOrNone
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictMax
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictMin
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictCount
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictCountDistinct
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictFirst
        :noindex:
   * .. autoattribute:: convtools.aggregations.ReduceFuncs.DictLast
        :noindex:


.. _ref_c_joins:

c.join
======

.. autofunction:: convtools.conversion.join


.. _ref_mutations:

Mutations
=========

.. automethod:: convtools.base.BaseConversion.tap
   :noindex:

.. autoclass:: convtools.conversion.conversion.Mut
   :noindex:

.. autoclass:: convtools.mutations.Mutations
   :noindex:
   :members:
