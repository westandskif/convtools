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

 .. code-block:: python

  c.this().gen_converter(debug=True)
  # is compiled to
  def converter36_998(data_):
      return data_

.. _ref_c_input_arg:

c.input_arg
===========

 .. autoattribute:: convtools.conversion.input_arg

 .. autoclass:: convtools.base.InputArg()
  :noindex:

 .. automethod:: convtools.base.InputArg.__init__

 .. code-block:: python

  f = (c.this() + c.input_arg("x")).gen_converter(debug=True)
  # is compiled to
  def converter37_306(data_, *, x):
      return data_ + x
  # usage:
  assert f(10, x=700) == 710

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

**Example:**

.. code-block:: python

 # assume we have a map: 3rd party error code to verbose
 converter = c.naive({
     "99": "Invalid token - the user has changed password",
     "500": "try again later"
 }).item(c.item("error_code")).gen_converter()

 # is compiled to
 def converter209_358(data_):
    # v206_380 is the mapping exposed by c.naive
    return v206_380[data_["error_code"]]

 converter({"error_code": "500"}) == "try again later"


.. _ref_c_wrapper:

c() wrapper
===========

 .. automethod:: convtools.conversion.__call__

 .. automethod:: convtools.base.ensure_conversion
    :noindex:

 .. note::
    It is used under the hood on every argument passed to any conversion.

**Example #1:**

.. code-block:: python

 converter = c({
  c.item("id"): c.item("name"),
 }).gen_converter()

 # is compiled to
 def converter42_484(data_):
     return {data_["id"]: data_["name"]}

 converter({"id": "uid", "name": "John"}) == {"uid": "John"}

**Example #2:**

.. code-block:: python

 converter = c(
     lambda x: f"{type(x).__name__}_{x}"
 ).call(c.item("value")).gen_converter()

 # is compiled to
 def converter42_484(data_):
     return vlambda80_37(data_["value"])

 converter(123) == "int_123"

**Example #2 + inline_expr (no unnecessary func call):**

.. code-block:: python

 converter = (
     c.inline_expr('''"%s_%s" % (type({x}).__name__, {x})''')
     .pass_args(x=c.item("value"))
     .gen_converter(debug=True)
 )({"value": 123}) == "int_123"

 # is compiled to
 def converter100_386(data_):
     return "%s_%s" % (type(data_["value"]).__name__, data_["value"])

 converter(123) == "int_123"

**Example #2 without inline_expr (no unnecessary func call):**

.. code-block:: python

 converter = (
     c("{}_{}").call_method(
         "format",
         c.call_func(type, c.item("value")).attr("__name__"),
         c.item("value"),
     )
     .gen_converter(debug=True)
 )({"value": 123}) == "int_123"

 # is compiled to
 def converter100_386(data_):
     return "{}_{}".format(
         getattr(type(data_["value"]), "__name__"), data_["value"]
     )
 converter(123) == "int_123"


.. _ref_c_item:

c.item
======

 .. autoattribute:: convtools.conversion.item

 .. autoclass:: convtools.base.GetItem()
    :noindex:

 .. automethod:: convtools.base.GetItem.__init__

**Example:**

.. code-block:: python

 c.item("key1", 1, c.item("key2"), default=-1).gen_converter()

generates:

.. code-block:: python

 def get_or_default208_222(obj, default):
     try:
         return obj['key1'][1][obj['key2']]
     except (TypeError, KeyError, IndexError, AttributeError):
         return default

 def converter208_771(data):
    return get_or_default208_222(data, -1)


**Also since conversions have methods, the following expressions
are equivalent:**

.. code-block:: python

 c.item("key1", "key2", 1).gen_converter()
 c.item("key1").item("key2").item(1).gen_converter()

and generate same code, like:

.. code-block:: python

 def converter210_775(data):
     return data["key1"]["key2"][1]


.. _ref_c_attr:

c.attr
======

``c.attr`` works the same as :py:obj:`convtools.base.GetItem`, but for
getting attributes.

.. autoattribute:: convtools.conversion.attr

.. autoclass:: convtools.base.GetAttr()
   :noindex:

.. automethod:: convtools.base.GetAttr.__init__

.. code-block:: python

 c.attr("user", c.input_arg("field_name")).gen_converter()

generates:

.. code-block:: python

 def converter157_386(data_, *, field_name):
    return getattr(data_.user, field_name)


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


**Examples:**

.. code-block:: python

 c.item("key1").call_method("replace", "abc", "").gen_converter()
 # generates
 def converter210_134(data):
     return data["key1"].replace("abc", "")

.. code-block:: python

 # also the following is available
 c.call_func(str.replace, c.item("key1"), "abc", "").gen_converter()
 c.item("key1").attr("replace").call("abc", "").gen_converter()


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

.. code-block:: python

 c.inline_expr("{0} + 1").pass_args(c.item("key1")).gen_converter()
 # same
 c.inline_expr("{number} + 1").pass_args(number=c.item("key1")).gen_converter()

 # gets compiled into
 def converter206_372(data):
    try:
        return data["key1"] + 1


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

.. code-block:: python

 # passing a list; the same works with tuples, sets,
 converter = c([
     "val_baked_into_conversion",
     c.item(2),
     c.item(1),
     # nesting works too, since every argument is being passed
     # through the `c() wrapper`, so no additional wrapping is needed
     (c.item(0), c.item(1)),
     c.input_arg("kwarg1")
 ]).gen_converter() # <=> c.list(...)

 converter([0, 1, 2], kwarg1=777) == ["val_baked_into_conversion", 2, 1, 777]

 # the code above generates the following:
 def converter215_171(data, *, kwarg1):
     return [
         "val_baked_into_conversion",
         data[2],
         data[1],
         (data[0], data[1]),
         kwarg1,
     ]

 # dicts either
 converter = c({
     c.item(0): c.item(1),
     c.item(1): c.item(0),
     '3': c.item(0),
 }).gen_converter()
 converter(['1', '2']) == {'1': '2', '2': '1', '3': '1'}

 # the code above generates the following:
 def converter216_250(data):
     return {data[0]: data[1], data[1]: data[0], "3": data[0]}


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

**Examples:**

.. code-block:: python

 c.list_comp(c.item("name")).gen_converter()
 # equivalent to
 [i208_702["name"] for i208_702 in data]

 c.dict_comp(c.item("id"), c.item("name")).gen_converter()
 # equivalent to
 {i210_336["id"]: i210_336["name"] for i210_336 in data}

**Support of filtering & sorting:**

.. code-block:: python

 c.list_comp(
     (c.item("id"), c.item("name"))
 ).filter(
     c.item("age").gte(18)
 ).sort(
     key=lambda t: t[0],
     reverse=True,
 ).gen_converter()
 # equivalent to
 return sorted(
     [
         (i210_700["id"], i210_700["name"])
         for i210_700 in data
         if (i210_700["age"] >= 18)
     ],
     key=vlambda216_644,
     reverse=True,
 )


.. _ref_c_filter:

c.filter
========

.. automethod:: convtools.conversion.filter
   :noindex:
.. automethod:: convtools.base.BaseConversion.filter
   :noindex:

Iterate an input filtering out items where the conversion resolves to False

.. code-block:: python

 c.filter(c.item("age").gte(18), cast=None).gen_converter()
 # equivalent to the following generator
 (i211_213 for i211_213 in data if (i211_213["age"] >= 18))

 # cast also supports: list, set, tuple or any callable to wrap generator
 c.filter(
     c.item("age").gte(c.input_arg("age")),
     cast=list
 ).gen_converter()
 # equivalent to
 def converter182_386(data_, *, age):
     return [i182_509 for i182_509 in data_ if (i182_509["age"] >= age)]


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

____

Examples:

.. code-block:: python

   conv = c.call_func(
       itertools.chain,
       c.list_comp(c.item(0)).add_label("first_objs"),
       c.label("first_objs"),
   ).gen_converter(debug=True)

   list(conv([(0,), (1,)])) == [0, 1, 0, 1]


.. _ref_pipes:

Pipes
=====

.. automethod:: convtools.base.BaseConversion.pipe
   :noindex:

____

It's easier to read the code written with pipes in contrast to heavily
nested approach:

.. code-block:: python

 conv = c.tuple(
     c.item("data", "users"),
     c.item("timestamp").add_label("timestamp1"),
 ).pipe(
     c.item(0).pipe(
         c.generator_comp({"id": c.item("id"), "name": c.item("name")})
     ),
     label_input=dict(
         timestamp2=c.item(1),
     )
 ).pipe(
     c.list_comp(
         c.inline_expr(
             "{ModelCls}(updated={updated}, timestamp={timestamp}, **{data})",
         ).pass_args(
             ModelCls=c.input_arg("model_cls"),
             timestamp=c.label("timestamp1"),
             # timestamp=c.label("timestamp2"), # also available
             updated=c.input_arg("updated"),
             data=c.this(),
         )
     ),
     # label_output="resulting_list", # labeling the result
 ).gen_converter(debug=True)

 # generates:

 def converter282_272(data_, *, model_cls, updated):
     pipe282_978 = (
         globals().__setitem__(
             "cached_val_272", (data_["data"]["users"], data_["timestamp"])
         )
         or globals().__setitem__("timestamp", cached_val_272[1])
         or cached_val_272
     )
     timestamp = globals()["timestamp"]
     pipe282_748 = pipe282_978[0]
     pipe282_952 = (
         {"id": i281_832["id"], "name": i281_832["name"]}
         for i281_832 in pipe282_748
     )
     return [
         (model_cls(updated=updated, timestamp=timestamp, **i282_325))
         for i282_325 in pipe282_952
     ]


Also it's often useful to pass the result to a callable (*of course you can
wrap any callable to make it a conversion and pass any parameters in any way
you wish*), but there is some syntactic sugar:

.. code-block:: python

   c.item("date_str").pipe(datetime.strptime, "%Y-%m-%d")

   # results in:

   def converter397_422(data_):
       return vstrptime396_498(data_["date_str"], "%Y-%m-%d")
   # so in cases where you pipe to python callable,
   # the input will be passed as the first param and other params onward



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


Examples:

.. code-block:: python

   f = c.list_comp(
       c.if_(
           c.this().is_(None),
           -1,
           c.this()
       )
   ).gen_converter(debug=True)

   f([0, 1, None, 2]) == [0, 1, -1, 2]

   # generates:

   def converter66_417(data_):
       return [(-1 if (i66_248 is None) else i66_248) for i66_248 in data_]


**Imagine we pass something more complex than just a simple value:**

.. code-block:: python

   f = c.list_comp(
       c.call_func(
           lambda x: x, c.this()
       ).pipe(
           c.if_(if_true=c.this() + 2)
       )
   ).gen_converter(debug=True)

   f([1, 0, 2]) == [3, 0, 4]

   # generates:
   # as you can see, it uses a function to cache the input data
   def converter75_417(data_):
       return [
           (
               (vvalue_cache76_824() + 2)
               if vvalue_cache76_824(vlambda69_109(i75_248))
               else vvalue_cache76_824()
           )
           for i75_248 in data_
       ]

It works as follows: if it finds any function calls, index/attribute lookups,
it just caches the input, because the IF cannot be sure whether it's cheap or
applicable to run the input code twice.



.. _ref_c_aggregations:

c.group_by, c.aggregate & c.reduce
==================================


.. _ref_c_group_by:

c.group_by
__________

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


Let's get to an almost self-describing example:

.. code-block:: python

 c.group_by(
     # any number of keys to group by
     c.item("company"), c.item("department"),
 ).aggregate({
     # a list, a tuple or a set would work as well; here we'll get the
     # list of dicts
     "company": c.item("company"),
     "department": c.item("department"),

     # just to demonstrate that even dict keys and groupby keys are dynamic
     c.call_func(
         lambda c: c.upper(),
         c.item("company")
     ): c.item("department").call_method("replace", "PREFIX", ""),


     # some normal SQL-like functionality
     "sales_total": c.reduce(
         c.ReduceFuncs.Sum,
         c.item("sales"),
     ),
     "sales_2019": c.reduce(
         c.ReduceFuncs.Sum,
         c.item("sales"),
     ).filter(
         c.item("date").gte("2019-01-01")
     ),
     "sales_total_too": c.reduce(
         lambda a, b: a + b,
         c.item("sales"),
         initial=0, # initial value for reducer
         default=None, # if not a single value is met (e.g. because of filter)
     ),

     # some additional functionality
     "company_address": c.reduce(
         c.ReduceFuncs.First,
         c.item("company_address"),
     ),

     "oldest_employee": c.reduce(
         c.ReduceFuncs.MaxRow,
         c.item("age"),
     ).item("employee"), # looking for a row with maximum employee age and then taking "employee" field (actually we could take the row untouched)

     # here we perform another aggregation, inside grouping by company & department
     # the output of this reduce is a dict: from employee to sum of sales (within the group)
     "employee_to_sales": c.reduce(
         c.ReduceFuncs.DictSum,
         (c.item("employee"), c.item("sales"))
     ),

     # piping works here too
     "postprocessed_dict_reduce": c.reduce(
         c.ReduceFuncs.DictSum,
         (c.item("currency"), c.item("sales")),
         default=dict,
     ).call_method("items").pipe(
         c.generator_comp(
             c.inline_expr(
                 "{convert_currency}({currency}, {convert_to_currency}, {sales})"
             ).pass_args(
                 convert_currency=convert_currency_func,
                 currency=c.item(0),
                 convert_to_currency=c.input_arg("convert_to_currency"),
                 sales=c.item(1),
             )
         )
     ),
 }).gen_converter()


Adding ``debug=True`` to see the compiled code:
_______________________________________________

.. code-block:: python

   def group_by(data_, convert_to_currency):
       global add_label_, get_by_label_
       _none = v383_497
       signature_to_agg_data_ = defaultdict(AggData277)
       for row_ in data_:
           agg_data_ = signature_to_agg_data_[
               (row_["company"], row_["department"],)
           ]

           if row_["date"] >= "2019-01-01":
               if agg_data_.v1 is _none:
                   agg_data_.v1 = row_["sales"] or 0

               else:
                   agg_data_.v1 += row_["sales"] or 0

           if agg_data_.v0 is _none:
               agg_data_.v0 = row_["sales"] or 0
               agg_data_.v3 = row_["company_address"]
               agg_data_.v5 = _d = defaultdict(int)
               _d[row_["employee"]] += row_["sales"] or 0
               agg_data_.v6 = _d = defaultdict(int)
               _d[row_["currency"]] += row_["sales"] or 0

           else:
               agg_data_.v0 += row_["sales"] or 0
               pass
               agg_data_.v5[row_["employee"]] += row_["sales"] or 0
               agg_data_.v6[row_["currency"]] += row_["sales"] or 0

           if agg_data_.v2 is _none:
               agg_data_.v2 = lambda305_238(0, row_["sales"])

           else:
               agg_data_.v2 = lambda305_238(agg_data_.v2, row_["sales"])

           if agg_data_.v4 is _none:
               if row_["age"] is not None:
                   agg_data_.v4 = (row_["age"], row_)

           else:
               if row_["age"] is not None and agg_data_.v4[0] < row_["age"]:
                   agg_data_.v4 = (row_["age"], row_)

       result_ = [
           {
               "company": signature_[0],
               "department": signature_[1],
               lambda212_482(signature_[0]): signature_[1].replace("PREFIX", ""),
               "sales_total": (0 if agg_data_.v0 is _none else agg_data_.v0),
               "sales_2019": (0 if agg_data_.v1 is _none else agg_data_.v1),
               "sales_total_too": (
                   None if agg_data_.v2 is _none else agg_data_.v2
               ),
               "company_address": (
                   None if agg_data_.v3 is _none else agg_data_.v3
               ),
               "oldest_employee": (
                   None if agg_data_.v4 is _none else agg_data_.v4[1]
               )["employee"],
               "employee_to_sales": (
                   None if agg_data_.v5 is _none else (dict(agg_data_.v5))
               ),
               "postprocessed_dict_reduce": (
                   (lambda273_656(i276_863[0], convert_to_currency, i276_863[1]))
                   for i276_863 in (
                       dict() if agg_data_.v6 is _none else (dict(agg_data_.v6))
                   ).items()
               ),
           }
           for signature_, agg_data_ in signature_to_agg_data_.items()
       ]

       return result_


   def converter277_660(data_, *, convert_to_currency):
      global add_label_, get_by_label_
      return group_by386_836(data_, convert_to_currency)

Fortunately this code is auto-generated (there's no joy in writing this).


.. _ref_c_joins:

c.join
======

.. autofunction:: convtools.conversion.join

.. code-block:: python

   s = '''{"left": [
       {"id": 1, "value": 10},
       {"id": 2, "value": 20}
   ], "right": [
       {"id": 1, "value": 100},
       {"id": 2, "value": 200}
   ]}'''
   conv1 = (
       c.call_func(json.loads, c.this())
       .pipe(
           c.join(
               c.item("left"),
               c.item("right"),
               c.and_(
                   c.LEFT.item("id") == c.RIGHT.item("id"),
                   c.RIGHT.item("value") > 100
               ),
               how="left",
           )
       )
       .pipe(
           c.list_comp({
               "id": c.item(0, "id"),
               "value_left": c.item(0, "value"),
               "value_right": c.item(1).and_(c.item(1, "value")),
           })
       )
       .gen_converter(debug=True)
   )
   assert conv1(s) == [
       {'id': 1, 'value_left': 10, 'value_right': None},
       {'id': 2, 'value_left': 20, 'value_right': 200}
   ]

