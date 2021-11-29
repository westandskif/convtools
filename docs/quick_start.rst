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

* **conversion** - any instance of :py:obj:`convtools.base.BaseConversion`
* **converter** - a function obtained by calling :py:obj:`gen_converter<convtools.base.BaseConversion.gen_converter>` method of `conversion`
* **input** - the input data to be transformed (passed to a `converter`)

3. Intro
________

Please make sure you've read - :ref:`base info here<ref_index_intro>`.

Let's review the most basic conversions:
  * :py:obj:`c.this<convtools.base.This>` returns an input untouched
  * :py:obj:`c.item<convtools.base.GetItem>` makes any number of dictionary/index lookups, supports ``default=...``
  * :py:obj:`c.attr<convtools.base.GetAttr>` makes any number of attribute lookups, supports ``default=...``
  * :py:obj:`c.naive<convtools.base.NaiveConversion>` returns an object passed to ``naive`` untouched
  * :py:obj:`c.input_arg<convtools.base.InputArg>` returns an input argument of a resulting converter

**Example #1:**

.. tabs::

  .. tab:: convtools

    .. code-block:: python

      # we'll cover this "c() wrapper" in the next section
      converter = c({
          "full_name": c.item("data", "fullName"),
          "age": c.item("data", "age", default=None),
      }).gen_converter(debug=True)

      input_data = {"data": {"fullName": "John Wick", "age": 18}}
      assert converter(input_data) == {"full_name": "John Wick", "age": 18}

  .. tab:: compiled code

    .. code-block:: python

      def get_or_default_a7(obj_, default_):
          global labels_
          try:
              return obj_["data"]["age"]
          except (TypeError, KeyError, IndexError, AttributeError):
              return default_


      def converter_zs(data_):
          global labels_
          return {
              "full_name": data_["data"]["fullName"],
              "age": get_or_default_a7(data_, None),
          }

**Example #2 - just to demonstrate every concept mentioned above:**

.. tabs::
  .. tab:: convtools

    .. code-block:: python

      # we'll cover this "c() wrapper" in the next section
      c({
          "input": c.this(),
          "naive": c.naive("string to be passed"),
          "input_arg": c.input_arg("dt"),
          "by_keys_and_indexes": c.item("key1", 1),
          "by_attrs": c.attr("keys"),
      }).gen_converter(debug=True)

  .. tab:: compiled code

    .. code-block:: python

      def converter112_406(data_, *, dt):
          return {
              "input": data_,
              "naive": "string to be passed",
              "input_arg": dt,
              "by_keys_and_indexes": data_["key1"][1],
              "by_attrs": data_.keys,
          }

**Example #3 (advanced) - keys/indexes/attrs can be conversions themselves:**

.. tabs::
  .. tab:: convtools

    .. code-block:: python

       converter = c.item(c.item("key")).gen_converter(debug=True)
       converter({"key": "amount", "amount": 15}) == 15

  .. tab:: compiled code

    .. code-block:: python

       # under the hood
       def converter120_406(data_):
           return data_[data_["key"]]

These were the most basic ones.
You will see how useful they are, when combining them
with manipulating converter signatures, passing functions / objects to conversions,
sharing conversion parts (honoring DRY principle).


4. Creating collections - c() wrapper, Optional items, overloaded operators and debugging
_________________________________________________________________________________________

Next points to learn:
  #. operators are overloaded for conversions - :ref:`convtools operators<ref_cheatsheet_operators>`
  #. every argument passed to a conversion is wrapped with :py:obj:`c() wrapper<convtools.base.ensure_conversion>` which:

     * leaves conversions untouched
     * rebuilds python dict/list/tuple/set collections as literals, e.g. :ref:`collection conversions<ref_cheatsheet_collections>`
     * everything else is being wrapped with :py:obj:`c.naive<convtools.base.NaiveConversion>`

  #. collections support optional items :py:obj:`c.optional<convtools.base.OptionalCollectionItem>`

.. note::
  whenever you are not sure what code is going to be generated, just
  pass ``debug=True`` to the ``gen_converter`` method. Also it's useful to
  have `black` installed, because then it is used to format auto-generated
  code.


For example, to convert a tuple to a dict:

.. tabs::

  .. tab:: convtools

    .. code-block:: python

       data_input = (1, 2, 3)

       converter = c({
           "sum": c.item(0) + c.item(1) + c.item(2),
           "and_or": c.item(0).and_(c.item(1)).or_(c.item(2)),
           "comparisons": c.item(0) > c.item(1),
       }).gen_converter(debug=True)

       converter(data_input) == {'sum': 6, 'and_or': 2, 'comparisons': False}

  .. tab:: compiled code

    .. code-block:: python

       """ Under the hood the conversion generates and compiles the following code.

       This is a normal python function, debuggable with both pdb and pydevd"""

       def converter42_67(data_):
           return {
               "sum": ((data_[0] + data_[1]) + data_[2]),
               "and_or": ((data_[0] and data_[1]) or data_[2]),
               "comparisons": (data_[0] > data_[1]),
           }


**It's possible to define an optional key, value or list/set/tuple item, which
appears in the output only if a condition is met:**

.. tabs::

  .. tab:: convtools

    .. code-block:: python

       converter = c({
           "exists if 'key' exists": c.optional(c.item("key", default=None)),
           "exists if not None": c.optional(
               c.call_func(lambda i: i+1, c.item("key", default=None)),
               skip_value=None,
           ),
           "exists if 'amount' > 10": c.optional(
               c.call_func(bool, c.item("key", default=None)),
               skip_if=c.item("amount") <= 10,
           ),
           "exists if 'amount' > 10 (same)": c.optional(
               c.call_func(bool, c.item("key", default=None)),
               keep_if=c.item("amount") > 10,
           ),
           # works for keys too
           c.optional(
               "name",
               keep_if=c.item("tos_accepted", default=False)
            ): c.item("name"),
       }).gen_converter(debug=True)

  .. tab:: compiled code

    .. code-block:: python

      def optional_items_generator_we(data_):
          global labels_
          if get_or_default_uw(data_, None) is not None:
              yield (
                  "exists if 'key' exists",
                  get_or_default_uw(data_, None),
              )
          if lambda_q4(get_or_default_10(data_, None)) is not None:
              yield (
                  "exists if not None",
                  lambda_q4(get_or_default_10(data_, None)),
              )
          if not (data_["amount"] <= 10):
              yield (
                  "exists if 'amount' > 10",
                  bool(get_or_default_4e(data_, None)),
              )
          if data_["amount"] > 10:
              yield (
                  "exists if 'amount' > 10 (same)",
                  bool(get_or_default_7d(data_, None)),
              )
          if get_or_default_gy(data_, False):
              yield (
                  "name",
                  data_["name"],
              )

      def converter_qn(data_):
          global labels_
          return dict(optional_items_generator_we(data_))

5. Passing/calling functions & objects into conversions; defining converter signature
_____________________________________________________________________________________

Next:
  * :py:obj:`gen_converter<convtools.base.BaseConversion.gen_converter>` takes ``signature`` argument
    to modify a signature of the resulting converter. Also there are 2 shortcuts:
    ``method=True`` for defining methods and ``class_method=False`` for classmethods

  * there are 3 different ways of calling functions, see :ref:`this section<ref_cheatsheet_simple_conversions>` for examples:

    * :py:obj:`c.call_func<convtools.base.CallFunc>` - to call a function and
      pass arguments (of course each is being wrapped with ``c()`` wrapper)
    * :py:obj:`(...).call_method<convtools.base.BaseConversion.call_method>` - to call a method of the conversion and pass args
    * :py:obj:`(...).call<convtools.base.BaseConversion.call>` - to call a callable and pass args

  * also there are 3 `call` counterparts for cases where argument unpacking is
    needed and kwargs keys contain conversions

    * :py:obj:`c.apply_func<convtools.base.ApplyFunc>`
    * :py:obj:`(...).apply_method<convtools.base.BaseConversion.apply_method>`
    * :py:obj:`(...).apply<convtools.base.BaseConversion.apply>`


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

   # OR an object to use to convert amounts
   class CurrencyConverter:
       def __init__(self, currency_to="USD"):
           self.currency_to = currency_to

       def convert_currency(self, currency_from, dt, amount):
           # ...
           return amount

    currency_converter = CurrencyConverter(currency_to="GBP")

    # and some mapping to add company name:
    company_id_to_name = {"id821": "Tardygram"}

**Let's prepare the converter to get a dict with company name and USD amount
from a tuple:**

.. tabs::
  .. tab:: convtools

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

  .. tab:: compiled code

    .. code-block:: python

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

Let's review `apply` ones:

.. code-block:: python

   c.apply_func(f, args, kwargs)
   # is same as the following, but works for kwargs with conversions as keys
   c.call_func(f, *args, **kwargs)

   c.apply(args, kwargs)
   c.this().apply(args, kwargs)
   # are same as
   c.call(*args, **kwargs)
   c.this().call(*args, **kwargs)

   c.this().apply_method("foo", args, kwargs)
   # is same as
   c.this().call_method("foo", *args, **kwargs)


6. List/dict/set/tuple comprehensions & inline expressions
__________________________________________________________

Next:
  #. the following conversions generate comprehension code:

     * :py:obj:`c.iter<convtools.base.GeneratorComp>` or :py:obj:`c.generator_comp<convtools.base.GeneratorComp>`
     * :py:obj:`c.dict_comp<convtools.base.DictComp>`
     * :py:obj:`c.list_comp<convtools.base.ListComp>`
     * :py:obj:`c.set_comp<convtools.base.SetComp>`
     * :py:obj:`c.tuple_comp<convtools.base.TupleComp>`

  #. every comprehension supports if clauses to filter input:

     * ``c.list_comp(..., where=condition_conv)``
     * ``c.this().iter(..., where=condition_conv)``

  #. to avoid unnecessary function call overhead, there is a way to pass an inline
     python expression :py:obj:`c.inline_expr<convtools.base.InlineExpr>`


**Lets do all at once:**

.. tabs::

  .. tab:: convtools

    .. code-block:: python

      input_data = [
          {"value": 100, "country": "US"},
          {"value": 15, "country": "CA"},
          {"value": 74, "country": "AU"},
          {"value": 350, "country": "US"},
      ]

      converter = c.list_comp(
          c.item("value").call_method("bit_length"),
          where=c.item("country") == "US"
      ).sort(
          # working with the resulting item here
          key=lambda item: item,
          reverse=True,
      ).gen_converter(debug=True)
      converter(input_data)

  .. tab:: compiled code

    .. code-block:: python

      def converter_d5(data_):
          global labels_
          return sorted(
              (
                  i_le["value"].bit_length()
                  for i_le in data_
                  if (i_le["country"] == "US")
              ),
              key=lambda_mu,
              reverse=True,
          )



**This may be useful in cases where you work with dicts, where values are lists:**

.. tabs::

  .. tab:: convtools

    .. code-block:: python

       conv = (
           c.this()
           .call_method("items")
           .pipe(
               c.inline_expr(
                   "(key, item)"
                   " for key, items in {}"
                   " for item in items"
                   " if key"
               ).pass_args(c.this())
           )
           # of course we could continue doing something interesting here
           # .pipe(
           #     c.group_by(...).aggregate(...)
           # )
       ).gen_converter(debug=True)

  .. tab:: compiled code

    .. code-block:: python

      def converter80_647(data_):
           pipe80_338 = data_.items()
           return ((key, item) for key, items in pipe80_338 for item in items if key)

7.1. Processing collections - I: iter, filter, sort, pipe, label, if
____________________________________________________________________

Points to learn:

#. :py:obj:`c.iter<convtools.base.GeneratorComp>` iterates through an iterable,
   applying conversion to each element
#. :py:obj:`c.filter<convtools.base.FilterConversion>` iterates through an
   iterable, filtering it by a passed conversion, taking items for which the
   conversion resolves to true
#. :py:obj:`c.sort<convtools.base.SortConversion>` passes the input to
   :py:obj:`sorted`
#. :py:obj:`(...).pipe<convtools.base.BaseConversion.pipe>` chains two
   conversions by passing the result of the first one to the second one. If
   piping is done at the top level of a resulting conversion (not nested), then
   it's going to be represented as several statements in the resulting code.
#. :py:obj:`labels<convtools.base.LabelConversion>` extend pipe and regular
   conversions functionality:

   * :py:obj:`(...).add_label("first_el",
     c.item(0))<convtools.base.BaseConversion.add_label>` allows to apply any
     conversion and then add a label to the result
   * to reference the result
     :py:obj:`c.label("first_el")<convtools.base.LabelConversion>` is used
   * any :py:obj:`(...).pipe<convtools.base.BaseConversion.pipe>` supports
     ``label_input`` and ``label_output`` parameters, both accept either
     ``str`` (a label name) or ``dict`` (keys are label names, values are
     conversions to be applied before labeling)

#. :py:obj:`c.if_<convtools.base.If>` allows to build ``1 if a else 2``
   expressions.  It's possible to pass not every parameter:

   * if a condition is not passed, then the input is used as a condition
   * if any branch is not passed, then the input is passed untouched

A simple pipe first:

.. tabs::

  .. tab:: convtools

    .. code-block:: python

       conv = c.iter(c.this() * 2).pipe(sum).gen_converter(debug=True)

       # OR THE SAME
       conv = c.generator_comp(c.this() * 2).pipe(sum).gen_converter(debug=True)

  .. tab:: compiled code

    .. code-block:: python

       # GENERATES:
       def converter_lv(data_):
           global labels_
           return sum(((i_s5 * 2) for i_s5 in data_))

____

A bit more complex ones:

.. tabs::

  .. tab:: convtools

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

  .. tab:: compiled code

    .. code-block:: python

      # UNDER THE HOOD GENERATES:
      def pipe_ib(input_i2):
          global labels_
          return Decimal_8i(input_i2) if input_i2 else None


      def converter_6c(data_):
          global labels_
          return {
              i_nh["name"]: [
                  {"id": str(i_1t[0]), "amount": pipe_ib(i_1t[1])}
                  for i_1t in i_nh["transactions"]
              ]
              for i_nh in data_
          }

____


Now let's use some labels:

.. tabs::

  .. tab:: convtools

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

  .. tab:: compiled code

    .. code-block:: python

      def pipe_hh(input_ag):
          global labels_
          labels_["input"] = input_ag
          result_w9 = input_ag
          pass
          return result_w9


      def pipe_74(input_uf):
          global labels_
          labels_["input_type"] = type(input_uf)
          result_dj = (i_bl for i_bl in input_uf if ((i_bl % 3) == 0))
          pass
          return result_dj


      def pipe_ns(input_i7):
          global labels_
          pass
          result_le = [str(i_sy) for i_sy in input_i7]
          labels_["list_length"] = len(result_le)
          labels_["separator"] = "," if (labels_["list_length"] > 10) else ";"
          return result_le


      def pipe_yo(input_s8):
          global labels_
          return {
              "result": labels_["separator"].join(input_s8),
              "input_type": labels_["input_type"],
              "input_data": labels_["input"],
          }


      def converter_yo(data_):
          global labels_
          return pipe_yo(pipe_ns(pipe_74(pipe_hh(data_))))

It works as follows: if it finds any function calls, index/attribute lookups,
it just caches the input, because the IF cannot be sure whether it's cheap or
applicable to run the input code twice.

7.2. Processing collections - II: chunk_by, chunk_by_condition
______________________________________________________________

Points to learn:

#. :py:obj:`c.chunk_by<convtools.conversion.Conversion.chunk_by>` allows to
   slice iterables into chunks by values and chunk sizes
#. :py:obj:`c.chunk_by_condition<convtools.conversion.Conversion.chunk_by_condition>`
   allows to slice iterables into chunks based on a condition, which is a
   function of a current chunk and an element

A simple pipe first:

.. tabs::

  .. tab:: convtools

    .. code-block:: python

       conv = c.chunk_by(size=1000).gen_converter(debug=True)

       # OR USING A CONDITION
       # conv = c.chunk_by_condition(c.CHUNK.len() < 1000).gen_converter(debug=True)

  .. tab:: compiled code

    .. code-block:: python

       # GENERATES:
       def chunk_by_1p(items_):
           items_ = iter(items_)
           try:
               item_ = next(items_)
           except StopIteration:
               return
           chunk_ = [item_]
           size_ = 1
           for item_ in items_:
               if size_ < 1000:
                   chunk_.append(item_)
                   size_ = size_ + 1
               else:
                   yield chunk_
                   chunk_ = [item_]
                   size_ = 1
           yield chunk_


       def converter_bh(data_):
           global __naive_values__, __none__
           _naive = __naive_values__
           _none = __none__
           _labels = _none
           return chunk_by_1p(data_)

____


And a more complex one with running aggregation on each chunk:

.. tabs::

  .. tab:: convtools

    .. code-block:: python

       c.chunk_by(
           c.item("x"),
           size=1000
       ).aggregate({
           "x": c.ReduceFuncs.Last(c.item("x")),
           "y": c.ReduceFuncs.Sum(c.item("y")),
       }).gen_converter(debug=True)

       # OR USING A CONDITION
       # c.chunk_by_condition(
       #     c.and_(
       #         c.CHUNK.item(-1, "x") == c.item("x"),
       #         c.CHUNK.len() < 1000
       #     )
       # ).aggregate({
       #     "x": c.ReduceFuncs.Last(c.item("x")),
       #     "y": c.ReduceFuncs.Sum(c.item("y")),
       # }).gen_converter(debug=True)

  .. tab:: compiled code

    .. code-block:: python

       # GENERATES:
       def chunk_by_8f(items_, _naive, _labels, _none):
           items_ = iter(items_)
           try:
               item_ = next(items_)
           except StopIteration:
               return
           chunk_ = [item_]
           chunk_item_signature = item_["x"]
           size_ = 1
           for item_ in items_:
               new_item_signature = item_["x"]
               if chunk_item_signature == new_item_signature and size_ < 1000:
                   chunk_.append(item_)
                   size_ = size_ + 1
               else:
                   yield chunk_
                   chunk_ = [item_]
                   chunk_item_signature = new_item_signature
                   size_ = 1
           yield chunk_


       def aggregate__yp(data_, _naive, _labels, _none):
           agg_data__yp_v0 = agg_data__yp_v1 = _none
           expected_checksum_ = 3
           checksum_ = 0

           it_ = iter(data_)
           for row__yp in it_:
               if agg_data__yp_v0 is _none:
                   agg_data__yp_v0 = row__yp["x"]
                   agg_data__yp_v1 = row__yp["y"] or 0
                   break

           for row__yp in it_:
               agg_data__yp_v0 = row__yp["x"]
               agg_data__yp_v1 = agg_data__yp_v1 + (row__yp["y"] or 0)

           return {
               "x": (None if agg_data__yp_v0 is _none else agg_data__yp_v0),
               "y": (0 if agg_data__yp_v1 is _none else agg_data__yp_v1),
           }


        def converter_xh(data_):
           global __naive_values__, __none__
           _naive = __naive_values__
           _none = __none__
           _labels = _none
           return (
               _naive["aggregate__yp"](i_5k, _naive, _labels, _none)
               for i_5k in chunk_by_8f(data_, _naive, _labels, _none)
           )

8. Helper shortcuts
___________________

Points to learn:

#. :py:obj:`(...).len()<convtools.base.BaseConversion.len>` is a shortcut to
   python's :py:obj:`len`
#. :py:obj:`c.min<convtools.conversion.Conversion.min>` and
   :py:obj:`c.max<convtools.conversion.Conversion.max>` are shortcuts to
   python's :py:obj:`min` & :py:obj:`max`
#. :py:obj:`c.zip<convtools.conversion.Conversion.zip>` python's :py:obj:`zip` on
   batteries, because when args provided, it generates tuples; when kwargs
   provided, generates dicts
#. :py:obj:`c.repeat<convtools.conversion.Conversion.repeat>` wraps python's
   :py:obj:`itertools.repeat`
#. :py:obj:`c.flatten<convtools.conversion.Conversion.flatten>` wraps python's
   :py:obj:`itertools.chain.from_iterable`
#. :py:obj:`c.take_while<convtools.conversion.Conversion.take_while>` re-implements
   :py:obj:`itertools.takewhile`
#. :py:obj:`c.drop_while<convtools.conversion.Conversion.drop_while>` re-implements
   :py:obj:`itertools.dropwhile`

.. code-block:: python

   c.this().len()
   c.min(c.this(), 5)
   c.zip(c.item("list_a"), c.repeat(None))
   c.zip(a=c.item("list_a"), b=c.repeat(None))
   c.take_while(c.this() < 3)
   c.drop_while(c.this() < 3)

9. Aggregations
_______________

Points to learn:
  #. first, call :py:obj:`c.group_by<convtools.aggregations.GroupBy>` to
     specify one or many conversions to use as group by keys (getting list of
     items in the end) OR no conversions to aggregate (results in a single
     item)
  #. then call the
     :py:obj:`aggregate<convtools.aggregations.GroupBy.aggregate>` method to
     define the desired output, comprised of:

     * (optional) a container you want to get the results in
     * (optional) group by keys or further conversions of them
     * any number of available out of the box
       :ref:`c.ReduceFuncs<convtools_cheatsheet_reducefuncs_list>` or further
       conversions of them
     * any number of custom :py:obj:`c.reduce<convtools.aggregations.Reduce>`
       and further conversions of them

  #. :py:obj:`c.aggregate<convtools.aggregations.Aggregate>` is a shortcut for
     ``c.group_by().aggregate(...)``


Not to provide a lot of boring examples, let's use the most interesting reduce functions:
  * use sum or none reducer
  * find a row with max value of one field and return a value of another field
  * take first value (one per group)
  * use dict array reducer
  * use dict sum reducer

.. tabs::

  .. tab:: convtools

    .. include:: ../tests/test_doc__quickstart_aggregation.py
       :code: python

  .. tab:: compiled code

    .. code-block:: python

      def group_by_xu(data_):
          global labels_
          _none = v_hk
          signature_to_agg_data_ = defaultdict(AggData_wl)
          for row_ in data_:
              agg_data_ = signature_to_agg_data_[row_["company_name"]]

              if agg_data_.v0 is _none:
                  agg_data_.v0 = row_["sales"]
                  agg_data_.v2 = row_["company_hq"]
                  agg_data_.v3 = _d = defaultdict(dict)
                  _d[row_["app_name"]][row_["country"]] = None
                  agg_data_.v4 = _d = defaultdict(int)
                  _d[row_["app_name"]] = row_["sales"] or 0

              else:
                  if row_["sales"] is None:
                      agg_data_.v0 = None
                  elif agg_data_.v0 is not None:
                      agg_data_.v0 = agg_data_.v0 + row_["sales"]
                  pass
                  agg_data_.v3[row_["app_name"]][row_["country"]] = None
                  agg_data_.v4[row_["app_name"]] = agg_data_.v4[row_["app_name"]] + (
                      row_["sales"] or 0
                  )

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
                  "top_sales_day": strptime_4q(
                      (None if agg_data_.v1 is _none else agg_data_.v1[1])["date"],
                      "%Y-%m-%d",
                  ).date(),
                  "company_hq": (None if agg_data_.v2 is _none else agg_data_.v2),
                  "app_name_to_countries": (
                      None
                      if agg_data_.v3 is _none
                      else ({k_: list(v_) for k_, v_ in agg_data_.v3.items()})
                  ),
                  "app_name_to_sales": (
                      None if agg_data_.v4 is _none else (dict(agg_data_.v4))
                  ),
              }
              for signature_, agg_data_ in signature_to_agg_data_.items()
          ]

          return result_


      def converter_4q(data_):
          global labels_
          return group_by_xu(data_)


10. Joins
_________

There is JOIN functionality which returns generator of joined pairs.
Points to learn:

#. :py:obj:`c.join<convtools.joins.JoinConversion>` exposes API for joins

   * first two positional arguments are conversions which are considered as 2 iterables to be joined
   * the third argument is a join condition, represented as a conversion based on ``c.LEFT`` and ``c.RIGHT``

#. the following join types are supported (via passing ``how``):

   * inner (default)
   * left
   * right
   * outer
   * cross (inner with ``condition=True``)

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


11. Mutations
_____________

Alongside pipes, there's a way to tap into any conversion and define mutation of its result by using:
  * :py:obj:`c.iter_mut(*mutations)<convtools.base.IterMutConversion>`
  * :py:obj:`c.tap(*mutations)<convtools.base.TapConversion>`

The following :py:obj:`mutations<convtools.mutations.Mutations>` are available:
  * ``c.Mut.set_item``
  * ``c.Mut.set_attr``
  * ``c.Mut.del_item``
  * ``c.Mut.del_attr``
  * ``c.Mut.custom``

``iter_mut`` example:

.. tabs::

  .. tab:: convtools

    .. code-block:: python

      input_data = [{"a": 1, "b": 2}]

      converter = c.iter_mut(
          c.Mut.set_item("c", c.item("a") + c.item("b")),
          c.Mut.del_item("a"),
          c.Mut.custom(c.this().call_method("update", c.input_arg("data")))
      ).as_type(list).gen_converter(debug=True)

      assert converter(input_data, data={"d": 4}) == [{"b": 2, "c": 3, "d": 4}]

  .. tab:: compiled code

    .. code-block:: python

      def iter_mut_2o(data_, data):
          for item_ in data_:
              item_["c"] = item_["a"] + item_["b"]
              item_.pop("a")
              item_.update(data)
              yield item_


      def converter_w6(data_, *, data):
          global labels_
          return list(iter_mut_2o(data_, data))


``tap`` example:

.. tabs::

  .. tab:: convtools

    .. code-block:: python

      input_data = [{"a": 1, "b": 2}]

      converter = c.list_comp(
          c.this().tap(
              c.Mut.set_item("c", c.item("a") + c.item("b")),
              c.Mut.del_item("a"),
              c.Mut.custom(c.this().call_method("update", c.input_arg("data")))
          )
      ).gen_converter(debug=True)

      assert converter(input_data, data={"d": 4}) == [{"b": 2, "c": 3, "d": 4}]

  .. tab:: compiled code

    .. code-block:: python

      def tap_e6(data_, data):
          data_["c"] = data_["a"] + data_["b"]
          data_.pop("a")
          data_.update(data)
          return data_

      def converter_0p(data_, *, data):
          global labels_
          return [tap_e6(i_6w, data) for i_6w in data_]


12. Debugging & setting Options
_______________________________

Compiled converters are debuggable callables, which dump generated code on disk
to ``PY_CONVTOOLS_DEBUG_DIR`` (*if env variable is defined*) or to
:py:obj:`tempfile.gettempdir` on any of the following cases:

* on exception inside a converter
* on ``.gen_converter(debug=True)``
* if :py:obj:`breakpoint() method<convtools.base.Breakpoint>` is used.

So there are 3 options to help you debug:

.. code-block:: python

   # No. 1: just prints black-formatted code
   c.this().gen_converter(debug=True)

   # No. 2: both prints black-formatted code & puts a breakpoint after "name"
   # lookup
   c.list_comp(c.item("name").breakpoint()).gen_converter()
   # e.g. what's inside list_comp
   c.list_comp(c.breakpoint()).gen_converter()

   # No. 3: prints black-formatted code for all converters, generated within
   # the context
   with c.OptionsCtx() as options:
       options.debug = True
       c.this().gen_converter()

See :py:obj:`c.OptionsCtx()<convtools.base.ConverterOptionsCtx>` API docs for
the full list of available options.


13. Details: inner input data passing
_____________________________________

There are few conversions which change the input for next conversions:
  * comprehensions
      *inside a comprehension the input is an item of an iterable*
  * pipes
      *next conversion gets the result of a previous one*
  * filters
      *next conversion gets the result of a previous one*
  * aggregations
      *e.g. any further conversions done either to group by fields or
      to reduce objects take the result of aggregation as the input*
