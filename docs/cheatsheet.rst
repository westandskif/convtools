.. _convtools_cheatsheet:

====================
convtools cheatsheet
====================

0. Prerequisites:
_________________

To install the library run ``pip install convtools``

.. code-block:: python

   from convtools import conversion as c
   from convtools.contrib.tables import Table

1. Simple conversion: keys, attrs, indexes, function calls, type casting
________________________________________________________________________

.. list-table::
 :header-rows: 1
 :class: cheatsheet-table

 * - in
   - out
   - conversion
 * - .. code-block:: python

      {
          "fullName": "Tim Cook",
          "salary": "1500000",
          "phones": [
              "+1567678789",
              "+1567678790",
          ]
      }

   - .. code-block:: python

      {
          "full_name": "Tim Cook",
          "salary": Decimal("1500000"),
          "main_phone": "+1567678789",
      }
   - .. code-block:: python

      converter = c({
          "full_name": c.item("fullName"),
          "salary": c.item("salary").as_type(Decimal),
          "main_phone": c.item("phones", 0, default=None),
      }).gen_converter()
      converter(input_data)

 * - .. code-block:: python

      # same structure, but
      # "fullName", "salary",
      # "phones" are attributes

   - .. code-block:: python

      {
          "full_name": "Tim Cook",
          "salary": Decimal("1500000"),
          "main_phone": "+1567678789",
      }
   - .. code-block:: python

      converter = c({
          "full_name": c.attr("fullName"),
          "salary": c.attr("salary").as_type(Decimal),
          "main_phone": c.attr("phones").item(0, default=None),
      }).gen_converter()
      converter(input_data)

 * - .. code-block:: python

      # same structure as previous

   - .. code-block:: python

      UserModel(
          "Tim Cook",
          salary=Decimal("1500000"),
          main_phone="+1567678789",
      )

   - .. code-block:: python

      converter = c.call_func(
          UserModel,
          c.attr("fullName"),
          salary=c.attr("salary").as_type(Decimal),
          main_phone=c.attr("phones").item(0, default=None),
      ).gen_converter()
      converter(input_data)

2.1 Operators
_____________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      (10, 20)

   - .. code-block:: python

      # DIY

   - .. code-block:: python

      converter = c({
          "-a": -c.item(0),
          "a + b": c.item(0) + c.item(1),
          "a - b": c.item(0) - c.item(1),
          "a * b": c.item(0) * c.item(1),
          "a / b": c.item(0) / c.item(1),
          "a // b": c.item(0) // c.item(1),
          "a % b": c.item(0) % c.item(1),

          "a == b": c.item(0) == c.item(1),
          "a >= b": c.item(0) >= c.item(1),
          "a <= b": c.item(0) <= c.item(1),
          "a < b": c.item(0) < c.item(1),
          "a > b": c.item(0) > c.item(1),

          "a or b": c.item(0) | c.item(1),
          "a and b": c.item(0) & c.item(1),
          "not a": ~c.item(0),

          "a is b": c.item(a).is_(c.item(1)),
          "a is not b": c.item(a).is_not(c.item(1)),

          "a in b": c.item(a).in_(c.item(1)),
          "a not in b": c.item(a).not_in(c.item(1)),

      }).gen_converter()
      converter(input_data)

2.2 Collections & Comprehensions
________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion

 * - .. code-block:: python

      input_data = [{"id": 1}, {"id": 2}]

   - .. code-block:: python

      # generator of IDs
      result = (item["id"] for item in input_data)

   - .. code-block:: python

      c.iter(c.item("id")).execute(input_data)

 * - .. code-block:: python

      input_data = [{"id": 1}, {"id": 2}]

   - .. code-block:: python

      # list of IDs
      result = [1, 2]

   - .. code-block:: python

      c.list_comp(c.item("id")).execute(input_data)
      # OR
      c.iter(c.item("id")).as_type(list).execute(input_data)

 * - .. code-block:: python

      input_data = [{"id": 1}, {"id": 2}]

   - .. code-block:: python

      # ID-to-object mapping
      result = {
          1: {"id": 1},
          2: {"id": 2},
      }

   - .. code-block:: python

      c.dict_comp(
          c.item("id"),
          c.this()
      ).execute(input_data)
      # OR
      c.iter(
          (c.item("id"), c.this())
      ).as_type(dict).execute(input_data)


2.3 Logical operators & conditions
__________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion

 * - .. code-block:: python

      input_data = [1, 2, 3]

   - .. code-block:: python

      # Iterate through the list
      # filter out values less than 5
      # If the result is empty, replace with None
      result = None

   - .. code-block:: python

      converter = c.list_comp(
          c.this(),
          where=c.this() >= 5
      ).pipe(
          c.if_(
              if_true=c.this(),
              if_false=None,
          )
      ).gen_converter(debug=True)
      converter(input_data)

 * - .. code-block:: python

      input_data = [
          ("Nick", "2020-01-01"),
          ("Nick", "2020-01-02"),
          ("John", "2020-01-03"),
          ("John", "2020-01-03"),
      ]

   - .. code-block:: python

      # Get a dict: mapping names to tuples
      # of unique dates.
      # Replace tuples with values where
      # there's just one item inside
      result = {
          "Nick": ("2020-01-01", "2020-01-02"),
          "John": "2020-01-03"
      }

   - .. code-block:: python

      converter = c.aggregate(
          c.ReduceFuncs.DictArrayDistinct(
              (c.item(0), c.item(1)),
              default=dict,
          )
      ).call_method("items").pipe(
          c.dict_comp(
              c.item(0),
              c.if_(
                  c.item(1).pipe(len) > 1,
                  c.item(1).pipe(tuple),
                  c.item(1).item(0),
              )
          )
      ).gen_converter(debug=True)

      converter(input_data)

 * - .. code-block:: python

      input_data = [3, 2, 1]

   - .. code-block:: python

      # just sort the list
      result = [1, 2, 3]

   - .. code-block:: python

      c.this().sort().execute(input_data)


3. Parametrized conversion with some baked in arguments and optional items
__________________________________________________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      [
          (1, "Nick", "38.21", "BYN"),
          (7, "John", "26.45", "USD", "check"),
      ]

   - .. code-block:: python

      {
          1: {
              "id": 1,
              "name": "Nick",
              "amount_usd": Decimal("18.15"),
          },
          7: {
              "id": 7,
              "name": "John",
              "amount_usd": Decimal("26.45"),
              "type": "check",
          },
      }

   - .. code-block:: python

      converter = c.dict_comp(
          c.item(0),
          {
              "id": c.item(0),
              "name": c.item(1),
              "amount_usd": c.call_func(
                  convert_currency_func,
                  c.item(3),         # currency_from
                  "USD",             # currency_to (baked in arg)
                  c.input_arg("dt"), # becomes keyword argument
                  c.item(2),         # amount
              ),
              "type": c.optional(c.item(4, default=None)),
              # # same
              # "type": c.optional(
              #     c.item(4, default=None),
              #     skip_if=c.item(4, default=None).is_(None)
              # ),
              # # same
              # "type": c.optional(
              #     c.item(4, default=None),
              #     keep_if=c.item(4, default=None).is_not(None)
              # ),
          }
      ).gen_converter()
      converter(input_data, dt=date.today())

4. Converting using hardcoded maps + filters
____________________________________________


.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      [
          # date, event_name, quantity
          ("2019-10-01", "Start trial",       42),
          ("2019-10-02", "Paid subscription", 10),
          ("2019-10-03", "Renewal",           11),
          ("2019-10-03", "Cancel",            1),
      ]

   - .. code-block:: python

      # let's exclude "Cancel" ones
      # AND "dt" > date(2019, 10, 3)
      [
          {
              "dt": date(2019, 10, 1),
              "_same_dt2": date(2019, 10, 1),
              "_same_dt3": date(2019, 10, 1),
              "event_type": 1,
              "quantity": 42
          },
          {
              "dt": date(2019, 10, 2),
              "_same_dt2": date(2019, 10, 2),
              "_same_dt3": date(2019, 10, 2),
              "event_type": 2,
              "quantity": 10
          },
      ]

   - .. code-block:: python

      converter = c.generator_comp(
          {
              "dt": c.call_func(
                  datetime.strptime,
                  c.item(0),
                  "%Y-%m-%d"
              ).call_method("date"),

              # ==== SAME ====
              # "_same_dt2": c(datetime.strptime).call(
              #     c.item(0),
              #     "%Y-%m-%d"
              # ).call_method("date"),
              # "_same_dt3": c.item(0).pipe(
              #     datetime.strptime,
              #     "%Y-%m-%d"
              # ).call_method("date"),
              # ==== SAME ====

              "event_type": c.naive({
                  "Introductory price: trial": 1,
                  "Paid subscription": 2,
                  "Renewal": 3,
                  "Cancel": 4,
              }).item(c.item(1)),
              "quantity": c.item(2).as_type(int),
          }
      ).filter(
          (
              c.item("dt") <= c.input_arg("dt_end")
          ).and_(
              c.input_arg("event_type_filter_func").call(
                  c.item("event_type"),
              ),
          ),
          cast=list,
      ).gen_converter(debug=True)

      converter(
          input_data,
          dt_end=date(2019, 10, 2),
          event_type_filter_func=(
              lambda ev_type: "Cancel" not in event_type
          )
      )

5. Pipes and Labels: chaining multiple conversions & c.this()
_____________________________________________________________


.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      data = {"objects": [
          {"dt": "2019-10-01",
           "app_name": "Tardygram"},
          {"dt": "2019-10-02",
           "app_name": "Facebrochure"},
          {"dt": "2019-10-02",
           "app_name": "Facebrochure"},
      ], "timestamp": 123123123, "error": ""}

   - .. code-block:: python

      # let's assume there is no group_by conversion
      # and there's no way to do the following in 1 step.

      # get distinct apps
      # WHERE "dt" >= "2019-10-02"

      {
          "distinct_apps": {"Facebrochure"},
          "timestamp": 123123123,
          "error": "",
      }

   - .. code-block:: python

      filter_by_dt = c.generator_comp(
          c.this()
      ).filter(
          c.item("dt") >= c.input_arg("dt_start")
      )
      app_name_getter = c.generator_comp(c.item("app_name"))
      take_distinct = c.call_func(set, c.this())

      converter = c.tuple(
          c.item("timestamp").add_label("timestamp"),
          c.item("objects"),
          c.item("error"),
      ).pipe(
          c.item(1).pipe(filter_by_dt),
          label_input={
              "error": c.item(2),
          },
          # # if we needed to label output OR via dict
          # label_output="filtered_input",
      ).pipe(
          app_name_getter
      ).pipe({
          "timestamp": c.label("timestamp"),
          "error": c.label("error"),
          "distinct_apps": take_distinct
      }).gen_converter(debug=True)

      converter(data, dt_start="2019-10-02")


6. Group by: simple
___________________

# put tables into cheatsheet as well
# add Filters to the doc
#
# Tables doc -> another
#
# tell a user that there's no way to chain table iterables to other conversions
# prepare = c.iter(...)
# processed_rows = (
#     Table.from_rows(prepare.execute(data))
#     .filter(c.col("a") > 0)
#     .into_iter_rows(dict)
# )
# c.aggregate(c.ReduceFuncs.Sum(c.item("a"))).execute(processed_rows)



.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      [
          ("2019-01-01", 15),
          ("2019-01-01", 10),
          ("2019-01-02", 10),
      ]

   - .. code-block:: python

      # group by date, sum amounts

      [
          {"dt": "2019-01-01", "total": 25},
          {"dt": "2019-01-02", "total": 10},
      ]

   - .. code-block:: python

      converter = c.group_by(
          c.item(0)
      ).aggregate({
          "dt": c.item(0),
          "total": c.ReduceFuncs.Sum(c.item(1)),
      }).gen_converter()
      converter(input_data)

 * - .. code-block:: python

      [
          ("2019-01-01", 15),
          ("2019-01-01", 10),
          ("2019-01-02", 10),
      ]

   - .. code-block:: python

      # aggregate, take sum and max amounts

      (35, 15)

   - .. code-block:: python

      converter = c.aggregate(
          (
              c.ReduceFuncs.Sum(c.item(1)),
              c.ReduceFuncs.Max(c.item(1)),
          )
      ).gen_converter()
      converter(input_data)

.. _convtools_cheatsheet_reducefuncs_list:

7. Reduce Funcs: list
_____________________

* Sum
* SumOrNone
* Max
* MaxRow
* Min
* MinRow
* Count
* CountDistinct
* First
* Last
* Average
* Median
* Mode
* TopK
* Array
* ArrayDistinct
* Dict
* DictArray
* DictSum
* DictSumOrNone
* DictMax
* DictMin
* DictCount
* DictCountDistinct
* DictFirst
* DictLast

8. Group by: c.call_func, pipes and DictSum
___________________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      [
          {"dt": "2019-10-01",
           "currency": "USD",
           "amount": 100,
           "app_name": "Tardygram"},
          {"dt": "2019-10-02",
           "currency": "EUR",
           "amount": 90,
           "app_name": "Facebrochure"},
          {"dt": "2019-10-02",
           "currency": "GBP",
           "amount": 75,
           "app_name": "Facebrochure"},
          {"dt": "2019-10-02",
           "currency": "CHF",
           "amount": 101,
           "app_name": "Facebrochure"},
      ]

   - .. code-block:: python

      # group by uppercase app name
      # sum amounts converted to specified
      # currency as of the date

      {"TARDYGRAM": 100,
       "FACEBROCHURE": 300}

   - .. code-block:: python

      converter = c.group_by(
          c.item("app_name")
      ).aggregate(
          (
              c.item("app_name").call_method("upper"),
              c.ReduceFuncs.Sum(
                  c.call_func(
                      convert_to_currency_func,
                      c.item("currency"),
                      c.input_arg("currency_to"),
                      c.item("dt"),
                      c.item("amount"),
                  )
              )
          )
      ).pipe(
          c.call_func(dict, c.this())
      ).gen_converter()
      converter(input_data, currency_to="USD")

 * -

   - .. code-block:: python

      # in case convert_to_currency_func is expensive,
      # we can run it just once per group
      # since nested aggregations are available
      # via dict reducers

   - .. code-block:: python

      converter = c.group_by(
          c.item("app_name")
      ).aggregate(
          (
              c.item("app_name").call_method("upper"),
              c.ReduceFuncs.DictSum(
                  # key
                  (c.item("currency"), c.item("dt")),
                  # value to be summed
                  c.item("amount"),
                  default=dict,
              ).call_method(
                  "items"
              ).iter(
                  c.call_func(
                      convert_to_currency_func,
                      c.item(0, 0),
                      c.input_arg("currency_to"),
                      c.item(0, 1),
                      c.item(1),
                  ),
                  where=c.item(1)
              ).pipe(
                  c.call_func(sum, c.this())
              )
          )
      ).pipe(
          c.call_func(dict, c.this())
      ).gen_converter()
      converter(input_data, currency_to="USD")


9. Reduce Funcs: with filtering
_______________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      [
          {"company": "ABC Inc.",
           "name": "John",
           "sales": 150,
           "department": "BD1"},
          {"company": "ABC Inc.",
           "name": "Nick",
           "sales": 200,
           "department": "BD2"},
          {"company": "ABC Inc.",
           "name": "Hanna",
           "sales": 175,
           "department": "BD2"},
          {"company": "CODE GmhB",
           "name": "Ulrich",
           "sales": 160,
           "department": "BD"},
      ]

   - .. code-block:: python

      # grouping by company
      # 1. sum all sales > 155
      # 2. find a man with highest sales
      # 3. take the first company employee
      # 4. take distinct employee names
      # 5. dict department to sum of sales
      # 6. custom reduce function where sales > 155

      [
          {
              "company": "ABC Inc.",
              "total_sales": 375,
              "top_sales_person": "Nick",
              "first_employee": "John",
              "distinct_employee_names: [
                  "John", "Nick", "Hanna"
              ],
              "department_to_sales": {
                  "BD1": 150,
                  "BD2": 375,
              },
              "stream_consumer": StreamConsumer(...),
          },
          {
              "company": "CODE GmhB",
              "total_sales": 160,
              "top_sales_person": "Ulrich",
              "first_employee": "Ulrich",
              "distinct_employee_names: ["Ulrich"],
              "department_to_sales": {"BD": 160},
              "stream_consumer": StreamConsumer(...),
          },
      ]

   - .. code-block:: python

      converter = c.group_by(
          c.item("company")
      ).aggregate(
          {
              "company": c.item("company"),
              "total_sales": c.ReduceFuncs.Sum(
                  c.item("sales"),
                  where=c.item("sales") > 155
              ),
              "top_sales_person": c.ReduceFuncs.MaxRow(
                  c.item("sales")
              ).item("name"), # or we could return full row
              "first_employee": c.ReduceFuncs.First(
                  c.item("name"),
              ),
              "distinct_employee_names": c.ReduceFuncs.ArrayDistinct(
                  c.item("name"),
              ),
              "department_to_sales": c.ReduceFuncs.DictSum(
                  (c.item("department"), c.item("sales"))
              ),
              "stream_consumer": c.reduce(
                  lambda consumer, b: consumer.consume(b) or consumer,
                  c.this(), # passing full row
                  initial=StreamConsumer,
                  default=None, # in case all sales <= 155
                  where=c.item("sales") > 155
              ),
          }
      ).gen_converter()
      converter(input_data)

10. Manipulating converter function signatures: methods, classmethods, \*args, \*\*kwargs
_________________________________________________________________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      class A:
          def __init__(
              self, multiplier: int
          ):
              self.multiplier = multiplier

   - .. code-block:: python

      # 1. add method
      A(10).sum_and_multiply_1(
          1, 2, 3
      ) == 60
      # 2. add classmethod
      A.sum_and_multiply_2(
          1, 2, 3,
          multiplier=10
      ) == 60

   - .. code-block:: python

      class A:
          # ...
          sum_and_multiply_1 = (
              c.call_func(sum, c.this())
              * c.input_arg("self").attr("multiplier")
          ).gen_converter(signature="self, \*data_")

          sum_and_multiply_2 = classmethod(
              (
                  c.call_func(sum, c.this())
                  * c.input_arg("multiplier")
              ).gen_converter(signature="cls, \*data_, multiplier=1")
          )
          # ==== SAME ===
          # sum_and_multiply_2 = classmethod(
          #     (
          #         c.call_func(sum, c.this())
          #         * c.input_arg("kwargs").call_method("get", "multiplier", 1)
          #     ).gen_converter(signature="cls, \*data_, \*\*kwargs")
          # )
          # ==== SAME ===

11. Joins
_________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      s = '''{"left": [
          {"id": 1, "value": 10},
          {"id": 2, "value": 20}
      ], "right": [
          {"id": 1, "value": 100},
          {"id": 2, "value": 200}
      ]}'''

   - .. code-block:: python

      # 1. parse json
      # 2. join "left" and "right" collections
      # 3. merge into dicts
      expected_result = [
          {'id': 1, 'value_left': 10, 'value_right': None},
          {'id': 2, 'value_left': 20, 'value_right': 200}
      ]

   - .. code-block:: python

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
      assert conv1(s) == expected_result


12. Passing options to converters
_________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      ...

   - .. code-block:: python

      # enable debug, 2 ways

   - .. code-block:: python

      # No. 1
      c.this().gen_converter(debug=True)

      # No. 2
      with c.OptionsCtx() as options:
          options.debug = True
          c.this().gen_converter()

13. Mutations
_____________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      input_data = [{"a": 1, "b": 2}]

   - .. code-block:: python

      # mutate each element by
      #  - adding "c" calculated value
      #  - drop "a" key
      #  - update the dict with an input dict
      [{"b": 2, "c": 3, "d": 4}]

   - .. code-block:: python

      # generator which mutates whole sequence
      converter = c.iter_mut(
          c.Mut.set_item("c", c.item("a") + c.item("b")),
          c.Mut.del_item("a"),
          c.Mut.custom(
              c.this().call_method("update", c.input_arg("data"))
          )
      ).as_type(list).gen_converter(debug=True)

 * - .. code-block:: python

      # same

   - .. code-block:: python

      # same

   - .. code-block:: python

      # function call per element (if needed by some reason)
      converter = c.list_comp(
          c.this().tap(
              c.Mut.set_item("c", c.item("a") + c.item("b")),
              c.Mut.del_item("a"),
              c.Mut.custom(
                  c.this().call_method( "update", c.input_arg("data"))
              )
          )
      ).gen_converter(debug=True)

14. Shortcuts I: zip, repeat, flatten, min, max
_______________________________________________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      input_data = [
          ([1,2], {"abc": 1}),
          ([3,4], {"cde": 2}),
      ]

   - .. code-block:: python

      #  - zip list with single dicts element-wise
      #  - flatten list
      [
          (1, {"abc": 1}),
          (2, {"abc": 1}),
          (3, {"cde": 2}),
          (4, {"cde": 2}),
      ]

   - .. code-block:: python

      converter = (
          c.iter(
              c.zip(
                  c.item(0),
                  c.repeat(c.item(1))
              )
          )
          .flatten()
          .as_type(list)
          .gen_converter(debug=True)
      )

 * - .. code-block:: python

      data = {
          "ids": [1, 2],
          "names": ["Nick", "John"],
      }

   - .. code-block:: python

      data = [
          {"id": 1, "name": "Nick"},
          {"id": 2, "name": "John"},
      ]

   - .. code-block:: python

      converter = c.zip(
          id=c.item("ids"),
          name=c.item("names"),
      ).as_type(list).gen_converter(debug=True)

 * - .. code-block:: python

      data = {"a": 1, "b": 2}

   - .. code-block:: python

      # take min among "a" and "b"
      1

   - .. code-block:: python

      converter = c.min(
          c.item("a"),
          c.item("b"),
      ).gen_converter(debug=True)

15. Debugging
_____________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 25 40
 :header-rows: 1

 * - in
   - out
   - conversion
 * - .. code-block:: python

      input_data = [
          {"name": "John"},
          {"name": "Nick"},
      ]

   - .. code-block:: python

      #  INVESTIGATE WHAT WE GET INSIDE LIST_COMP
      [
          {"name": "John"},
          {"name": "Nick"},
      ]

   - .. code-block:: python

      converter = (
          c.list_comp(c.breakpoint())
          .gen_converter()
      )
      converter(input_data)

 * - .. code-block:: python

      input_data = [
          {"name": "John"},
          {"name": "Nick"},
      ]

   - .. code-block:: python

      #  INVESTIGATE WHAT WE GET AFTER "name" LOOKUP
      ["John", "Nick"]

   - .. code-block:: python

      converter = (
          c.list_comp(c.item("name").breakpoint())
          .gen_converter()
      )
      converter(input_data)


16. Tables
__________

.. list-table::
 :class: cheatsheet-table
 :widths: 25 65
 :header-rows: 1

 * - task
   - conversion
 * - .. code-block:: python

      # 1) read tab-separated "tests/csvs/ac.csv"
      # 2) take columns "a" and "b"
      # 3) add column "C" as sum of "a" and "b"
      # 4) rename "a" -> "A"
      # 5) drop column "b"
      # 6) put the output to "tests/csvs/out.csv"

   - .. code-block:: python

      (
          Table
          .from_csv(
              "tests/csvs/ac.csv",
              header=True,
              dialect=Table.csv_dialect(delimiter="\t"),
          )
          .take("a", "c")
          .update(B=c.col("a") + c.col("c"))
          .rename({"a": "A"})
          .drop("c")
          .into_csv("tests/csvs/out.csv")
      )
 * - .. code-block:: python

      # 1) read Iterable of dicts
      # 2) use ["A", "B"] as a header
      # 3) cast all columns to int
      # 4) swap "a" and "b" places
      # 5) output as iterable of dict/tuple/list

   - .. code-block:: python

      list(
          Table
          .from_rows(
              [["1", "2"], ["10", "20"]],
              header=["A", "B"],
              # SAME:
              # header={"A": 0, "B": 1},
          )
          .take("B", "A")
          .update_all(int)
          .into_iter_rows(tuple)
      )
 * - .. code-block:: python

      # 1) read Iterables of tuples, use
      #    ("a", "b") and ("a", "c") as headers
      # 2) filter rows with "b" >= 0 and "c" >= 0
      # 3) join tables on "a"
      # 4) output as iterable of dict/tuple/list

   - .. code-block:: python

      list((
          Table
          .from_rows(
              [(0, -1), (1, 2), (10, 20)],
              header=["a", "b"],
          )
          .filter(c.col("b") >= 0)
      ).join(
          Table
          .from_rows(
              [(10, 5), (3, -5), (1, 7)],
              header=["a", "c"],
          )
          .filter(c.col("c") >= 0),
          on=["a"],
          how="inner",

          # SAME, but would replace "a" with "a_LEFT" and "a_RIGHT"
          # on=c.LEFT.col("a") == c.RIGHT.col("a"),
      ).into_iter_rows(dict))
