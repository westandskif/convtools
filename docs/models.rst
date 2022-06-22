.. _convtools_models:

================================================
convtools Model - data validation (experimental)
================================================

Vision
______

#. validation first
#. no implicit type casting
#. no implicit data losses during type casting - `e.g. casting 10.0 to int is
   fine, 10.1 is not`
#. if there's a model instance, it is valid.

Interface
_________

``pip install convtools``

.. code-block:: python

   import typing as t
   from convtools.contrib.models import (
       DictModel,
       ObjectModel,
       cached_model_method,
       cast,
       casters,
       field,
       init,
       init_or_raise,
       json_dumps,
       validate,
       validators,
   )
   
   class AddressModel(DictModel):
       apt: int
   
   class UserModel(DictModel):
       addresses: t.List[AddressModel] = (
           # Define field processing pipeline.
           # Fetch defines how-to-fetch:
           #  - either by specifying a path
           #  - or by passing cls_method (True or cls method name)
           #  - or allows to specify default or default_factory
           field(...)
           # run any number of validate / cast steps (order matters)
           .validate(...)
           # if cast has no arguments passed, it will cast to the output type
           .cast(...)
           # output type is checked implicitly
       )

   user, errors = init(UserModel, {"addresses": [{"apt": 221}]})

   # either there's a valid user and errors is None
   # or the user is None and there's nested errors dict

   user = init_or_raise(UserModel, {"addresses": [{"apt": 221}]})

   user.to_dict()
   # extended JSONEncoder, which handles models
   json_dumps(user)


   # if we need to validate objects, traversing attributes and indexes, use
   # ObjectModel
   class AddressModel(ObjectModel):
       apt: int

1. Validation - basics
______________________


.. code-block:: python

   from convtools.contrib.models import DictModel, init

   class UserModel(DictModel):
       name: str
       age: int

   user, errors = init(UserModel, {"name": "John", "age": 33})

   In [1]: errors is None
   Out[1]: True

   In [2]: user
   Out[2]: UserModel(name='John', age=33)

   In [3]: user.name
   Out[3]: 'John'

   In [4]: user["name"]
   Out[4]: 'John'

   In [5]: user.to_dict()
   Out[5]: {'name': 'John', 'age': 33}


And when validation fails:

.. code-block:: python

   user, errors = init(UserModel, {"age": 33.0})

   In [4]: errors
   Out[4]:
   defaultdict(dict,
               {'name': {'required': True},
                'age': {'type': 'float instead of int'}})


2. Validation - built-in & custom validators
____________________________________________

Built-in validators:

* :py:obj:`Gt<convtools.contrib.models.validators.validators.Gt>` - ``Gt(10)``
* :py:obj:`Gte<convtools.contrib.models.validators.validators.Gte>` - ``Gte(10)``
* :py:obj:`Lt<convtools.contrib.models.validators.validators.Lt>` - ``Lt(10)``
* :py:obj:`Lte<convtools.contrib.models.validators.validators.Lte>` - ``Lte(10)``
* :py:obj:`Regex<convtools.contrib.models.validators.validators.Regex>` - ``Regex(r"\d+")``
* :py:obj:`Custom<convtools.contrib.models.validators.validators.Custom>` - ``Custom("is_blank", lambda x: len(x))``
* :py:obj:`Type<convtools.contrib.models.validators.validators.Type>` - ``Type(int, float)`` - this one
  is used under the hood to check output types


All-in-one example:

.. code-block:: python

   class UserModel(DictModel):
       # either None or int (under the hood it's t.Union, so unions are supported too)
       user_id: t.Optional[int]
   
       # field with default
       is_active: bool = True
       # or the same
       is_active: bool = field(default=True)
       # or the same
       is_active: bool = field(default_factory=lambda: True)
   
       # any number of validators
       age: int = validate(validators.Gte(18), validators.Lt(100))
   
       # custom getter + validation
       name: str = field(cls_method=True).validate(
           validators.Type(str), validators.Regex("[\w\s]+")
       )
   
       @classmethod
       def get_name(cls, data):
           # returns data, errors
           if not data:
               return None, {"missing": True}
           name = data.get("name")
           if not name:
               return None, {"blank": True}
           return name, None
   
       # if something needs to be cached on a single model instance level
       random_number: float = field(cls_method="get_random")
       same_random_number: float = field(cls_method="get_random")
   
       @cached_model_method
       def get_random(self, data):
           # returns data, errors
           return random(), None

       # traverses path like: data["objects"][0]["amount"]
       deep_value: str = field("objects", 0, "amount", default="")


   # IF WE NEED TO VALIDATE OBJECTS, TRAVERSING ATTRIBUTES AND INDEXES, NOT
   # KEYS AND INDEXES, USE ObjectModel
   class OtherModel(ObjectModel):
       # traverses path like: data.objects[0].amount
       deep_value: str = field("objects", 0, "amount", default="")


3. Type casting
_______________

Type casting is explicit and it's done in 2 cases:

#. ``cast`` forces type casting (`either using passed casters OR by inferring
   required casters from the expected output type`)
#. model usage builds a model instance

When ``cast()`` is run without arguments, the following built-in casters are
inferred automatically:

* ``str``
* ``float``
* :py:obj:`Int<convtools.contrib.models.casters.casters.Int>` - casting ``10.1``
  to int leads to a validation error (see ``IntLossy`` below)
* :py:obj:`Decimal<convtools.contrib.models.casters.casters.Decimal>` -
  initializing from floats with non-zero decimal part leads to a validation
  error (see ``DecimalLossy`` below)
* :py:obj:`List<convtools.contrib.models.casters.casters.List>`
* :py:obj:`Dict<convtools.contrib.models.casters.casters.Dict>`
* :py:obj:`Enum<convtools.contrib.models.casters.casters.Enum>`
* :py:obj:`Union<convtools.contrib.models.casters.casters.Union>`

.. code-block:: python

   from decimal import Decimal

   class UserModel(DictModel):
       numbers: t.List[int] = cast()  # casts each list item to int
       number: Decimal = cast()


   In [38]: init(UserModel, {"numbers": [1, 2.0, 2.5], "number": 1.1})
   Out[38]:
   (None,
    defaultdict(dict,
                {'numbers': defaultdict(dict,
                             {2: {'int_caster': 'losing fractional part: 2.5; if desired, use casters.IntLossy'}}),
                 'number': {'decimal_caster': 'imprecise init from float: 1.1; if desired, use casters.DecimalLossy'}}))
    # to explain what happens when casting 1.1 float to Decimal
    # In [15]: Decimal(1.1)
    # Out[15]: Decimal('1.100000000000000088817841970012523233890533447265625')


   In [39]: init(UserModel, {"numbers": [1, 2.0, "2"], "number": 1.0})
   Out[39]: (UserModel(numbers=[1, 2, 2], number=Decimal('1')), None)


Along with the above, the following casters are available for explicit use:

* :py:obj:`IntLossy<convtools.contrib.models.casters.casters.IntLossy>` - allows
  to cast with data loss, e.g. 10.1 to 10
* :py:obj:`DecimalLossy<convtools.contrib.models.casters.casters.DecimalLossy>`
  - allows to cast floats with non-zero decimal part to Decimal
* :py:obj:`DateFromStr<convtools.contrib.models.casters.casters.DateFromStr>` - ``DateFromStr("%m/%d/%Y")``
* :py:obj:`DatetimeFromStr<convtools.contrib.models.casters.casters.DatetimeFromStr>` - ``DatetimeFromStr("%m/%d/%Y %H:%M %p")``
* :py:obj:`Custom<convtools.contrib.models.casters.casters.Custom>` - ``Custom("float_caster", float, (TypeError, ValueError))``
* :py:obj:`CustomUnsafe<convtools.contrib.models.casters.casters.CustomUnsafe>` - ``CustomUnsafe(int)`` - can raise exceptions

.. code-block:: python

   class UserModel(DictModel):
       numbers: t.List[int] = cast(casters.List(casters.IntLossy()))

   In [8]: init(UserModel, {"numbers": [1, 2.0, 2.5]})
   Out[8]: (UserModel(numbers=[1, 2, 2]), None)


As we mentioned above, model usage in type definition is the 2nd case when data
mutates -- as it builds model instances:

.. code-block:: python

   class AddressModel(DictModel):
       apt: int = cast()
   
   class UserModel(DictModel):
       addresses: t.List[AddressModel]

   In [17]: user = init_or_raise(UserModel, {"addresses": [{"apt": "221"}]})
   In [18]: user
   Out[18]: UserModel(name='John', addresses=[AddressModel(apt=221)])

   In [19]: user.name
   Out[19]: 'John'
   
   In [20]: user.addresses[0].apt
   Out[20]: 221


   # the following works too:
   In [21]: init_or_raise(t.List[AddressModel], [{"apt": 221}])
   Out[21]: [AddressModel(apt=221)]


4. Generic models
_________________

Generic models are supported.

.. code-block:: python

   T = t.TypeVar("T")
   
   class ResponseModel(DictModel, t.Generic[T]):
       data: t.List[T]
   
   class UserModel(DictModel, t.Generic[T]):
       parameter: T = cast()
   
   
   response = init_or_raise(
       ResponseModel[UserModel[int]], {"data": [{"parameter": " 123 "}]}
   )
   
   In [2]: response
   Out[2]: ResponseModel(data=[UserModel(parameter=123)])

   In [3]: response.data[0].parameter
   Out[3]: 123


   In [4]: json_dumps(response)
   Out[4]: '{"data": [{"parameter": 123}]}'


5. Model-level prepare/validate methods
_______________________________________

It's possible to implement custom class method - ``prepare`` (or ``prepare__``)
to prepare initial data before model processing kicks in.

Also final validation is available as well through ``validate`` (or
``validate__``) class methods.

.. code-block:: python

   class TestModel(DictModel):
       a: int
       b: str

       @classmethod
       def prepare(cls, data):
           if data:
               return json.loads(data), None
           return None, {"is_blank": True}

       @classmethod
       def validate(cls, model):
           if model.a > 100:
               return None, {"a_too_big": True}

           if not model.b:
               return None, {"b_blank": True}

           return model, None


6. Configuration
________________

By default models cache ``128`` least recently used converters. Should you want
to reset cache and/or change cache size, run the following function:

.. code-block:: python

   from convtools.contrib.models import set_max_cache_size

   set_max_cache_size(256)
