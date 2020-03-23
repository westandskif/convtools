.. _convtools_quickstart:

====================
convtools QuickStart
====================

1. Installation
_______________

``pip install convtools``

For the sake of conciseness, let's assume the following import statement is in place:

.. code-block:: python

 from convtools import conversion as c

This is an object which exposes public API.

2. Glossary
___________

Hereinafter the docs the following terms are used:
 * **conversion** - any instance of :ref:`BaseConversion<ref_c_base_conversion>`

 * **converter** - a function obtained by calling :ref:`gen_converter<ref_c_gen_converter>` method of `conversion`

 * **input** - the input data to be transformed

3. Intro
________

Please make sure you've read - :ref:`base info here<ref_index_intro>`.

Let's review the most basic conversions:

 * returns an input untouched: :ref:`c.this<ref_c_this>`
 * returns an object passed to a conversion: :ref:`c.naive<ref_c_naive>`
 * returns a converter input argument: :ref:`c.input_arg<ref_c_input_arg>`
 * makes any number of dictionary/index lookups, supports ``default``: :ref:`c.item<ref_c_item>`
 * makes any number of attribute lookups, supports ``default``: :ref:`c.attr<ref_c_attr>`

**Example #1:**

.. code-block:: python

   converter = c({
       "full_name": c.item("data", "fullName"),
       "age": c.item("data", "age", default=None),
   }).gen_converter(debug=True)

   assert converter(
       {"data": {"fullName": "John Wick", "age": 18}}
   ) == {"full_name": "John Wick", "age": 18}

   # compiles into

   def get_or_default31_79(obj_, default_):
       try:
           return obj_["data"]["age"]
       except (TypeError, KeyError, IndexError, AttributeError):
           return default_


   def converter35_647(data_):
       return {
           "full_name": data_["data"]["fullName"],
           "age": get_or_default31_7938_271(data_, None),
       }

**Example #2 - just to demonstrate every concept mentioned above:**

.. code-block:: python

   # we'll cover this "c() wrapper" in the next section
   c({
       "input": c.this(),
       "naive": c.naive("string to be passed"),
       "input_arg": c.input_arg("dt"),
       "by_keys_and_indexes": c.item("key1", 1),
       "by_attrs": c.attr("keys"),
   }).gen_converter(debug=True)

   # compiles into
   def converter112_406(data_, *, dt):
       return {
           "input": data_,
           "naive": "string to be passed",
           "input_arg": dt,
           "by_keys_and_indexes": data_["key1"][1],
           "by_attrs": data_.keys,
       }

**Example #3 (advanced) - keys/indexes/attrs can be conversions themselves:**

.. code-block:: python

   converter = c.item(c.item("key")).gen_converter(debug=True)
   converter({"key": "amount", "amount": 15}) == 15

   # under the hood
   def converter120_406(data_):
       return data_[data_["key"]]

These were the most basic ones.
You will see how useful they are, when combining them
with manipulating converter signatures, passing functions / objects to conversions,
sharing conversion parts (honoring DRY principle).


4. Creating collections - c() wrapper, overloaded operators and debugging
_________________________________________________________________________

Next points to learn:

 1. every argument passed to a conversion is wrapped with :ref:`c() wrapper<ref_c_wrapper>`
      * leaving conversions untouched
      * interpreting python dict/list/tuple/set collections as :ref:`collection conversions<ref_c_collections>`
      * everything else is being wrapped with :ref:`c.naive<ref_c_naive>`
 2. operators are overloaded for conversions - :ref:`convtools operators<ref_c_operators>`

.. note::
  whenever you are not sure what code is going to be generated, just
  pass ``debug=True`` to the ``gen_converter`` method. Also it's useful to
  have `black` installed, because then it is used to format auto-generated
  code.


For example, to convert a tuple to a dict:

.. code-block:: python

   data_input = (1, 2, 3)

   converter = c({
       "sum": c.item(0) + c.item(1) + c.item(2),
       "and_or": c.item(0).and_(c.item(1)).or_(c.item(2)),
       "comparisons": c.item(0) > c.item(1),
   }).gen_converter(debug=True)

   converter(data_input) == {'sum': 6, 'and_or': 2, 'comparisons': False}

   # Under the hood the conversion generates and compiles the following code.

   # This is a normal python function, debuggable with pdb (since it is using
   # linecache under the hood for getting source file lines)

   def converter42_67(data_):
       return {
           "sum": ((data_[0] + data_[1]) + data_[2]),
           "and_or": ((data_[0] and data_[1]) or data_[2]),
           "comparisons": (data_[0] > data_[1]),
       }


5. Passing/calling functions & objects into conversions; defining converter signature
_____________________________________________________________________________________

Next:
  * :ref:`gen_converter<ref_c_gen_converter>` takes ``signature`` argument
    to modify a signature of the resulting converter. Also there are 2 shortcuts:
    ``method=True`` for defining methods and ``class_method=False`` for classmethods

  * there are 3 different ways of calling functions, see :ref:`this section<ref_c_calls>` for details:

    * ``c.call_func`` - to call a function and pass arguments (of course each
      is being wrapped with ``c()`` wrapper)
    * ``c.call`` - to call a callable and pass args
    * ``(...).call_method`` - to call a method of the conversion and pass args


Imagine we have the following:

.. code-block:: python

   from datetime import date
   from decimal import Decimal

   # A function to convert amounts
   def convert_currency(
       currency_from: str, currency_to: str, dt: date, amount: Decimal
   ):
       # ...
       return amount

   # An object to use to convert amounts
   class CurrencyConverter:
       def __init__(self, currency_to="USD"):
           self.currency_to = currency_to

       def convert_currency(self, currency_from, dt, amount):
           # ...
           return amount

    currency_converter = CurrencyConverter(currency_to="GBP")

and some mapping to add company name:

.. code-block:: python

   company_id_to_name = {"id821": "Tardygram"}

**Let's prepare the converter to get a dict with company name and USD amount
from a tuple:**

.. code-block:: python

   data_input = ("id821", "EUR", date(2020, 1, 1), Decimal("100"))

   converter = c({
       "id": c.item(0),

       # naive makes the mapping available to a generated code
       "company_name": c.naive(company_id_to_name).item(c.item(0)),

       "amount_usd": c.call_func(
           convert_currency,
           c.item(1),
           "USD",
           c.input_arg("kwargs").item("dt"),
           c.item(3),
       ),
       "amount_usd2": c.naive(currency_converter).call_method(
           "convert_currency",
           c.item(1),
           c.input_arg("kwargs").item("dt"),
           c.item(3),
       ),
       # of course we could take "dt" as an argument directly, but doing the
       # following is here just for demonstrational purposes
   }).gen_converter(debug=True, signature="data_, **kwargs")

   converter(data_input, dt=date(2020, 1, 1)) == {
       "id": "id821",
       "company_name": "Tardygram",
       "amount_usd": Decimal("110"),
       "amount_usd2": Decimal("110"),
   }


   # omitting the try/except, see the generated code below:
   def converter83_406(data_):
       return {
           "id": data_[0],
           "company_name": v167_312[data_[0]],
           "amount_usd": vlambda178_738(
               data_[1], "USD", kwargs["dt"], data_[3]
           ),
           "amount_usd2": v213_273.convert_currency(
               data_[1], kwargs["dt"], data_[3]
           ),
       }


6. List/dict/set/tuple comprehensions & inline expressions
__________________________________________________________

Next:

  1. the following conversions generate comprehension code:

    * ``c.generator_comp``
    * ``c.dict_comp``
    * ``c.list_comp``
    * ``c.set_comp``
    * ``c.tuple_comp``, see :ref:`comprehensions section<ref_comprehensions>` for details:

  2. every comprehension, except ``c.set_comp`` supports sorting by calling e.g.
     ``c.list_comp(...).sort(key=None, reverse=False)``

  3. every comprehension supports filtering:
     ``c.list_comp(...).filter(condition_conv)``

  4. to avoid unnecessary function call overhead, there is a way to pass an inline
     python expression :ref:`c.inline_expr<ref_c_inline_expr>`


**Lets do all at once:**

.. code-block:: python

   input_data = [
       {"value": 100, "country": "US"},
       {"value": 15, "country": "CA"},
       {"value": 74, "country": "AU"},
       {"value": 350, "country": "US"},
   ]

   c.list_comp(
       c.inline_expr(
           "({number}).bit_length()"
       ).pass_args(number=c.item("value"))
   ).filter(
       c.item("country") == "US"
   ).sort(
       # working with the resulting item here
       key=lambda item: item,
       reverse=True,
   ).gen_converter(debug=True)

   # compiled converter:

   def converter268_422(data_):
       return sorted(
           [
               ((i268_194["value"]).bit_length())
               for i268_194 in data_
               if (i268_194["country"] == "US")
           ],
           key=vlambda273_26,
           reverse=True,
       )

**Example of custom nested comprehension:**

.. code-block::

   conv = c.inline_expr(
       "[(left_item, right_item)"
       " for left_item, right_items in {}"
       " for right_item in right_items]"
   ).pass_args(c.this()).gen_converter(debug=True)
   assert conv([[1, [2,3]], [10, [4,5]]]) == [(1, 2), (1, 3), (10, 4), (10, 5)]

**This may be useful in cases where you work with dicts, where values are lists:**

.. code-block::

   conv = c.this().call_method("items").pipe(
       c.inline_expr(
           "(key, item)"
           " for key, items in {}"
           " for item in items"
           " if key"
       ).pass_args(c.this())
   ).gen_converter(debug=True)
   # # of course we could continue doing something interesting here
   # .pipe(
   #     # c.group_by(...).aggregate(...)
   # )

   # COMPILES INTO

    def converter80_647(data_):
        pipe80_338 = data_.items()
        return ((key, item) for key, items in pipe80_338 for item in items if key)

7. Filters, pipes, labels and conditions
________________________________________

Points to learn:

 1. :ref:`c.filter<ref_c_filter>` iterates through the iterable, filtering it
    by a passed conversion, taking items for which the conversion resolves to true
 2. :ref:`(...).pipe<ref_pipes>` chains two conversions by passing the result of
    the first one to the second one. If piping is done at the top level of a
    resulting conversion (not nested), then it's going to be represented as
    several statements in the resulting code.
 3. :ref:`c.if_<ref_c_conditions>` allows to build ``1 if a else 2`` expressions.
    It's possible to pass not every parameter:

      * if a condition is not passed, then the input is used as a condition
      * if any branch is not passed, then the input is passed untouched
 4. :ref:`labels<ref_labels>` extend pipe and regular conversions
    functionality:

      * ``(...).add_label("first_el", c.item(0))`` allows to apply
        any conversion and then add a label to the result
      * to reference the result ``c.label("first_el")`` is used
      * any ``(...).pipe`` supports ``label_input`` and ``label_output``
        parameters, both accept either ``str`` (a label name) or ``dict`` (keys
        are label names, values are conversions to be applied before labeling)

A simple pipe first:

.. code-block:: python

   conv = c.generator_comp(
       c.this() * 2
   ).pipe(
       sum
   ).gen_converter(debug=True)

   # GENERATES:
   def converter35_941(data_):
       return sum(((i32_722 * 2) for i32_722 in data_))

____

A bit more complex ones:

.. code-block:: python

   conv = c.dict_comp(
       c.item("name"),
       c.item("transactions").pipe(
           c.list_comp(
               {
                   "id": c.item(0).as_type(str),
                   "amount": c.item(1).pipe(
                       c.if_(c.this(), c.this().as_type(Decimal), None)
                   ),
               }
           )
       ),
   ).gen_converter(debug=True)
   assert conv([{"name": "test", "transactions": [(0, 0), (1, 10)]}]) == {
       "test": [
           {"id": "0", "amount": None},
           {"id": "1", "amount": Decimal("10")},
       ]
   }

   # UNDER THE HOOD GENERATES:
   def converter72_941(data_):
       return {
           i72_722["name"]: [
               {
                   "id": str(i71_913[0]),
                   "amount": (
                       Decimal60_929(cached_val_75)
                       if (
                           globals().__setitem__("cached_val_75", i71_913[1])
                           or globals()["cached_val_75"]
                       )
                       else None
                   ),
               }
               for i71_913 in i72_722["transactions"]
           ]
           for i72_722 in data_
       }

____


Now let's use some labels:

.. code-block:: python

   conv1 = (
       c.this().add_label("input")
       .pipe(
           c.filter(c.this() % 3 == 0),
           label_input={
               "input_type": c.call_func(type, c.this()),
           },
       )
       .pipe(
           c.list_comp(c.this().as_type(str)),
           label_output={
               "list_length": c.call_func(len, c.this()),
               "separator": c.if_(c.label("list_length") > 10, ",", ";"),
           },
       )
       .pipe({
           "result": c.label("separator").call_method("join", c.this()),
           "input_type": c.label("input_type"),
           "input_data": c.label("input"),
       })
       .gen_converter(debug=True)
   )
    assert conv1(range(30)) == {
        "result": "0;3;6;9;12;15;18;21;24;27",
        "input_type": range
    }
    assert conv1(range(40)) == {
        "result": "0,3,6,9,12,15,18,21,24,27,30,33,36,39",
        "input_type": range
    }

Generates:

.. code-block:: python

   def converter137_941(data_):
       pipe137_725 = (
           globals().__setitem__(
               "cached_val_106",
               (
                   globals().__setitem__("cached_val_89", data_)
                   or globals().__setitem__("input", globals()["cached_val_89"])
                   or globals()["cached_val_89"]
               ),
           )
           or globals().__setitem__(
               "input_type", type(globals()["cached_val_106"])
           )
           or globals()["cached_val_106"]
       )
       input_type = globals()["input_type"]
       pipe137_489 = (
           i122_258 for i122_258 in pipe137_725 if ((i122_258 % 3) == 0)
       )
       pipe137_362 = (
           globals().__setitem__(
               "cached_val_124", [str(i123_386) for i123_386 in pipe137_489]
           )
           or globals().__setitem__(
               "list_length", len(globals()["cached_val_124"])
           )
           or globals().__setitem__(
               "separator", ("," if (globals()["list_length"] > 10) else ";")
           )
           or globals()["cached_val_124"]
       )
       list_length = globals()["list_length"]
       separator = globals()["separator"]
       return {
           "result": separator.join(pipe137_362),
           "input_type": input_type,
           "input_data": input,
       }


8. Aggregations
_______________

Points to learn:

 1. first, call :ref:`c.group_by<ref_c_group_by>` to specify one or many
    conversions of item of input iterable to group by (results in a list of items)
    OR no conversions to aggregate (results in a single item).
    Then call the ``aggregate`` method to define the desired output, comprised of:

      * further conversions of group by keys
      * :ref:`c.reduce<ref_c_reduce>` and further conversions

 2. :ref:`c.aggregate<ref_c_aggregate>` is a shortcut for
    ``c.group_by().aggregate(...)``

 3. there are many :ref:`c.ReduceFuncs<ref_c_reduce_funcs>` available out of the
    box, please check the link. Also it's possible to pass a function of
    2 arguments.

 4. there is a way to pass additional arguments to the reduce
    function, see ``additional_args`` argument of :ref:`c.reduce<ref_c_reduce>`


Not to provide a lot of boring examples, let's use the most interesting
reduce functions:

  * use sum or none reducer
  * find a row with max value of one field and return a value of another field
  * take first value (one per group)
  * use dict array reducer
  * use dict sum reducer

.. code-block:: python

   input_data = [
       {
           "company_name": "Facebrochure",
           "company_hq": "CA",
           "app_name": "Tardygram",
           "date": "2019-01-01",
           "country": "US",
           "sales": Decimal("45678.98"),
       },
       {
           "company_name": "Facebrochure",
           "company_hq": "CA",
           "app_name": "Tardygram",
           "date": "2019-01-02",
           "country": "US",
           "sales": Decimal("86869.12"),
       },
       {
           "company_name": "Facebrochure",
           "company_hq": "CA",
           "app_name": "Tardygram",
           "date": "2019-01-03",
           "country": "CA",
           "sales": Decimal("45000.35"),
       },
       {
           "company_name": "BrainCorp",
           "company_hq": "NY",
           "app_name": "Learn FT",
           "date": "2019-01-01",
           "country": "US",
           "sales": Decimal("86869.12"),
       },
   ]

   # we are going to reuse this reducer
   top_sales_day = c.reduce(
       c.ReduceFuncs.MaxRow,
       c.item("sales"),
   )

   # so the result is going to be a list of dicts
   converter = c.group_by(c.item("company_name")).aggregate({

       "company_name": c.item("company_name").call_method("upper"),
       # this would work as well
       # c.item("company_name"): ...,

       "none_sensitive_sum": c.reduce(c.ReduceFuncs.SumOrNone, c.item("sales")),

       # as you can see, next two reduce objects do the same except taking
       # different fields after finding a row with max value.
       # but please check the generated code below, you'll see that it is
       # calculated just once AND then reused to take necessary fields
       "top_sales_app": top_sales_day.item("app_name"),
       "top_sales_day": top_sales_day.item("date").pipe(
           datetime.strptime,
           "%Y-%m-%d",
       ).call_method("date"),

       "company_hq": c.reduce(c.ReduceFuncs.First, c.item("company_hq")),

       "app_name_to_countries": c.reduce(
           c.ReduceFuncs.DictArrayDistinct,
           (
               c.item("app_name"),
               c.item("country")
           )
       ),
       "app_name_to_sales": c.reduce(
           c.ReduceFuncs.DictSum,
           (
               c.item("app_name"),
               c.item("sales")
           )
       ),
   }).gen_converter(debug=True)

   converter(input_data) == [
       {
           "app_name_to_countries": {"Tardygram": ["US", "CA"]},
           "app_name_to_sales": {"Tardygram": Decimal("177548.45")},
           "company_hq": "CA",
           "company_name": "FACEBROCHURE",
           "none_sensitive_sum": Decimal("177548.45"),
           "top_sales_app": "Tardygram",
           "top_sales_day": date(2019, 1, 2),
       },
       {
           "app_name_to_countries": {"Learn FT": ["US"]},
           "app_name_to_sales": {"Learn FT": Decimal("86869.12")},
           "company_hq": "NY",
           "company_name": "BRAINCORP",
           "none_sensitive_sum": Decimal("86869.12"),
           "top_sales_app": "Learn FT",
           "top_sales_day": date(2019, 1, 1),
       },
   ]

**Don't get scared, but this is the code which is generated under the hood:**

.. code-block:: python

   def group_by(data_):
       global add_label_, get_by_label_
       _none = v528_497
       signature_to_agg_data_ = defaultdict(AggData454)
       for row_ in data_:
           agg_data_ = signature_to_agg_data_[row_["company_name"]]

           if agg_data_.v0 is _none:
               agg_data_.v0 = row_["sales"]
               agg_data_.v2 = row_["company_hq"]
               agg_data_.v3 = _d = defaultdict(dict)
               _d[row_["app_name"]][row_["country"]] = None
               agg_data_.v4 = _d = defaultdict(int)
               _d[row_["app_name"]] += row_["sales"] or 0

           else:
               if row_["sales"] is None:
                   agg_data_.v0 = None
               elif agg_data_.v0 is not None:
                   agg_data_.v0 = agg_data_.v0 + row_["sales"]
               pass
               agg_data_.v3[row_["app_name"]][row_["country"]] = None
               agg_data_.v4[row_["app_name"]] += row_["sales"] or 0

           if agg_data_.v1 is _none:
               if row_["sales"] is not None:
                   agg_data_.v1 = (row_["sales"], row_)

           else:
               if row_["sales"] is not None and agg_data_.v1[0] < row_["sales"]:
                   agg_data_.v1 = (row_["sales"], row_)

       result_ = [
           {
               "company_name": signature_.upper(),
               "none_sensitive_sum": (
                   None if agg_data_.v0 is _none else agg_data_.v0
               ),
               "top_sales_app": (
                   None if agg_data_.v1 is _none else agg_data_.v1[1]
               )["app_name"],
               "top_sales_day": strptime430_101(
                   (None if agg_data_.v1 is _none else agg_data_.v1[1])["date"],
                   "%Y-%m-%d",
               ).date(),
               "company_hq": (None if agg_data_.v2 is _none else agg_data_.v2),
               "app_name_to_countries": (
                   None
                   if agg_data_.v3 is _none
                   else ({k_: list(v_.keys()) for k_, v_ in agg_data_.v3.items()})
               ),
               "app_name_to_sales": (
                   None if agg_data_.v4 is _none else (dict(agg_data_.v4))
               ),
           }
           for signature_, agg_data_ in signature_to_agg_data_.items()
       ]

       return result_


   def converter454_660(data_):
       global add_label_, get_by_label_
       return group_by530_779(data_)


9. Joins
________

There is JOIN functionality which returns generator of joined pairs.
Points to learn:

 1. :ref:`c.join<ref_c_joins>` exposes API for joins

      - first two positional arguments are conversions which are considered as
        2 iterables to be joined
      - the third argument is a join condition, represented as a conversion
        based on ``c.LEFT`` and ``c.RIGHT``

 2. the following join types are supported (via passing ``how``):

     - inner (default)
     - left
     - right
     - outer
     - cross (inner with ``condition=True``)

Let's say we want to parse JSON string, take 2 collections, join them on
``left id == right id AND right value > 100`` condition, and then merge data
of joined pairs into dicts:

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

10. Debugging & setting Options
_______________________________

Compiled converters are debuggable callables, which populate linecache with
generated code either on exception inside a converter OR on setting
``debug=True``.  There are 2 ways of doing this:

.. code-block:: python

   # No. 1:
   c.this().gen_converter(debug=True)

   # No. 2:
   with c.OptionsCtx() as options:
       options.debug = True
       c.this().gen_converter()

See :ref:`c.OptionsCtx()<ref_optionsctx>` API docs for the full list
of available options.


11. Details: inner input data passing
_____________________________________

There are few conversions which change the input for next conversions:
  * :ref:`Comprehensions<ref_comprehensions>`
      *inside a comprehension the input is an item of an iterable*
  * :ref:`Pipes<ref_pipes>`
      *next conversion gets the result of a previous one*
  * :ref:`Filters<ref_c_filter>`
      *next conversion gets the result of a previous one*
  * :ref:`Aggregations<ref_c_aggregations>`
      *e.g. any further conversions done either to group by fields or
      to reduce objects take the result of aggregation as the input*
