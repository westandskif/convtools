.. _ref_models_vs_pydantic:

========================================
Comparison: convtools models vs pydantic
========================================

Context:

* documented on 2022-07-10
* ``python==3.9.7``
* ``pydantic==1.8.2``
* ``convtools==0.31.0``

To keep the below concise, let's assume the following imports are made:

.. literalinclude:: test_doc__models_vs_pydantic.py
   :language: python
   :start-after: START__PART_0
   :end-before: END__PART_0

1. Validation-only mode
_______________________

 "pydantic currently leans on the side of trying to coerce types rather
 than raise an error if a type is wrong". -
 https://pydantic-docs.helpmanual.io/usage/validation_decorator/#coercion-and-strictness

So to perform validation-only, you have to use strict mode in pydantic, while
convtools models default to validation-only mode because of PEP-20 (namely:
*Beautiful is better than ugly. Explicit is better than implicit.*):


.. list-table::
 :header-rows: 1
 :class: cheatsheet-table

 * - pydantic
   - convtools

 * - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_01__1
        :end-before: PART_01__1

   - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_01__2
        :end-before: PART_01__2


2. Type casting & validation
____________________________

Casting to int
--------------

.. list-table::
 :header-rows: 1
 :class: cheatsheet-table

 * - pydantic
   - convtools

 * - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_02__1
        :end-before: PART_02__1

   - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_02__2
        :end-before: PART_02__2

So pydantic defaults make 2 assumptions:
 1. that we'd like to cast to int
 2. and that we are fine with the data loss (the missing decimal part).

While convtools models keep both explicit.


Casting to Decimal
------------------

.. list-table::
 :header-rows: 1
 :class: cheatsheet-table

 * - pydantic
   - convtools

 * - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_03__1
        :end-before: PART_03__1

   - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_03__2
        :end-before: PART_03__2


Under the hood pydantic does ``Decimal(str(0.1 + 0.1 + 0.1)``).

Convtools again forces you to confirm both type casting & data losses; when
both confirmed, it runs simple ``Decimal(0.1 + 0.1 + 0.1)``


3. Performance & memory usage
_____________________________

Collected as ``$ pytest --benchmark-min-time=0.05 -k bench``.

.. literalinclude:: test_doc__models_vs_pydantic.py
   :language: python
   :start-after: PART_04
   :end-before: PART_04

4. Error format
_______________

convtools model error format is designed to allow for automated processing.

Error dicts have reserved keys:

* ``"__ERRORS"`` - dict with errors is behind this key

* ``"__KEYS"`` - dict where keys are keys from data and values are error dicts
  of key validation

* ``"__VALUES"`` - dict where keys are keys from data and values are error
  dicts of dict value validation

* ``"__SET_ITEMS"`` - dict where keys are set items and values are error dicts
  of set item validation

.. list-table::
 :header-rows: 1
 :class: cheatsheet-table

 * - pydantic
   - convtools

 * - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_05__1
        :end-before: PART_05__1

   - .. literalinclude:: test_doc__models_vs_pydantic.py
        :language: python
        :start-after: PART_05__2
        :end-before: PART_05__2
