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

   .. note::
     every converter has a ``try/except`` clause, which on exception populates python ``linecache``
     with converter source code to allow for ``pdb`` debugging and is used for normal stacktraces

 * **input** - the input data to be transformed

   .. note::
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

     No worries, we'll cover these below.

2. Intro
________

Please make sure you've read - :ref:`base info here<ref_index_intro>`.

Let's review the most basic conversions:

 * returns an input untoched: :ref:`c.this<ref_c_this>`
 * returns an object passed to a conversion: :ref:`c.naive<ref_c_naive>`
 * returns a converter input argument: :ref:`c.input_arg<ref_c_input_arg>`
 * makes any number of dictionary/index lookups, supports ``default``: :ref:`c.item<ref_c_item>`
 * makes any number of attribute lookups, supports ``default``: :ref:`c.attr<ref_c_attr>`

Example:

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

Advanced example (keys/indexes/attrs can be conversions themselves):

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


3. Creating collections - c() wrapper, overloaded operators and debugging
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
       try:
           return {
                "sum": ((data_[0] + data_[1]) + data_[2]),
                "and_or": ((data_[0] and data_[1]) or data_[2]),
                "comparisons": (data_[0] > data_[1]),
            }
       except Exception:
           import linecache
           linecache.cache[converter42_67._fake_filename] = (
               len(converter42_67._code_str),
               None,
               converter42_67._code_str.splitlines(),
               converter42_67._fake_filename,
           )
           raise


4. Passing/calling functions & objects into conversions; defining converter signature
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


5. List/dict/set/tuple comprehensions & inline expressions
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

6. Filters, pipes and conditions
________________________________

Points to learn:

 1. :ref:`c.filter<ref_c_filter>` iterates through the iterable, filtering it
    by a passed conversion, taking items for which the conversion resolves to true
 2. :ref:`(...).pipe<ref_pipes>` chains two conversions by passing the result of
    the first one to the second one. If piping is done at the top level of a
    resulting conversion (not nested), then it's going to be represented as
    several statements.
 3. :ref:`c.if_<ref_c_conditions>` allows to build ``1 if a else 2`` expressions.
    It's possible to pass not every parameter:
    
    * if a condition is not passed, then the input is used as a condition
    * if any branch is not passed, then the input is passed untouched
 
Let's use every thing on some input data:

.. code-block:: python

   input_data = range(100)

   c.filter(
       c.this() % 3 == 0
   ).pipe(
       c.generator_comp(
           c.this().as_type(str)
       )
   ).pipe(
       c.if_(
           c.this().pipe(len) > 10, c(","), c(";")
       ).call_method("join", c.this())
   ).gen_converter(debug=True)

   # prints:

   def converter365_417(data_):
       pipe365_801 = (i349_248 for i349_248 in data_ if ((i349_248 % 3) == 0))
       pipe365_781 = (vstr351_159(i353_292) for i353_292 in pipe365_801)
       return ("," if (vlen355_986(pipe365_781) > 10) else ";").join(
           pipe365_781
       )

Of course one pipe above is not necessary here, it has been done
for demonstrational purposes only.
A more efficient way would be:

.. code-block:: python

   c.list_comp(
       c.this().as_type(str)
   ).filter(
       # this is the filter method of a comprehension,
       # so c.this() here is a collection item before casting to str
       c.this() % 3 == 0
   ).pipe(
       c.if_(
           c.this().pipe(len) > 10, c(","), c(";")
       ).call_method("join", c.this())
   ).gen_converter(debug=True)

   # prints:

   def converter320_422(data_):
       pipe387_801 = [
           vstr368_159(i370_248)
           for i370_248 in data_
           if ((i370_248 % 3) == 0)
       ]
       return ("," if (vlen377_986(pipe387_801) > 10) else ";").join(
           pipe387_801
       )



7. Aggregations
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
           "app_name": "Learn QFT",
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
           "app_name_to_countries": {"Learn QFT": ["US"]},
           "app_name_to_sales": {"Learn QFT": Decimal("86869.12")},
           "company_hq": "NY",
           "company_name": "BRAINCORP",
           "none_sensitive_sum": Decimal("86869.12"),
           "top_sales_app": "Learn QFT",
           "top_sales_day": date(2019, 1, 1),
       },
   ]

**Don't get scared, but this is the code which is generated under the hood:**

.. code-block:: python

  def group_by(data):
      _none = v650_26
      try:
          signature_to_agg_data = defaultdict(AggData)
          for row in data:
              agg_data = signature_to_agg_data[row["company_name"]]
 
              if agg_data.v0 is _none:
                  agg_data.v0 = row["sales"]
              else:
                  if row["sales"] is None:
                      agg_data.v0 = None
                  elif agg_data.v0 is not None:
                      agg_data.v0 = agg_data.v0 + row["sales"]
 
              if agg_data.v1 is _none:
                  if row["sales"] is not None:
                      agg_data.v1 = (row["sales"], row)
              else:
                  if row["sales"] is not None and agg_data.v1[0] < row["sales"]:
                      agg_data.v1 = (row["sales"], row)
 
              if agg_data.v2 is _none:
                  agg_data.v2 = row["company_hq"]
              else:
                  pass
 
              if agg_data.v3 is _none:
                  agg_data.v3 = _d = defaultdict(dict)
                  _d[row["app_name"]][row["country"]] = None
              else:
                  agg_data.v3[row["app_name"]][row["country"]] = None
 
              if agg_data.v4 is _none:
                  agg_data.v4 = _d = defaultdict(int)
                  _d[row["app_name"]] += row["sales"] or 0
              else:
                  agg_data.v4[row["app_name"]] += row["sales"] or 0
 
          result = [
              {
                  "company_name": signature.upper(),
                  "none_sensitive_sum": (
                      None if agg_data.v0 is _none else agg_data.v0
                  ),
                  "top_sales_app": (
                      None if agg_data.v1 is _none else agg_data.v1[1]
                  )["app_name"],
                  "top_sales_day": vstrptime553_735(
                      (None if agg_data.v1 is _none else agg_data.v1[1])["date"],
                      "%Y-%m-%d",
                  ).date(),
                  "company_hq": (None if agg_data.v2 is _none else agg_data.v2),
                  "app_name_to_countries": (
                      None
                      if agg_data.v3 is _none
                      else {
                          i31_99[0]: vlist29_223(i31_99[1].keys())
                          for i31_99 in agg_data.v3.items()
                      }
                  ),
                  "app_name_to_sales": (
                      None if agg_data.v4 is _none else vdict34_186(agg_data.v4)
                  ),
              }
              for signature, agg_data in signature_to_agg_data.items()
          ]
 
          return result
      except Exception:
          import linecache
 
          linecache.cache[group_by._fake_filename] = (
              len(group_by._code_str),
              None,
              group_by._code_str.splitlines(),
              group_by._fake_filename,
          )
          raise
 
 
  def converter539_13(data_):
      try:
          return vgroup_by652_349(data_)
      except Exception:
          import linecache
 
          linecache.cache[converter539_13._fake_filename] = (
              len(converter539_13._code_str),
              None,
              converter539_13._code_str.splitlines(),
              converter539_13._fake_filename,
          )
          raise
