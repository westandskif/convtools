=========
convtools
=========


**convtools** is a python library to declaratively define fast conversions from python
objects to python objects, including processing collections and doing complex
aggregations.

.. image:: https://github.com/itechart-almakov/convtools/workflows/tests/badge.svg
   :target: https://github.com/itechart-almakov/convtools/workflows/tests/badge.svg
   :alt: Tests Status

.. image:: https://codecov.io/gh/itechart-almakov/convtools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/itechart-almakov/convtools

.. image:: https://readthedocs.org/projects/convtools/badge/?version=latest
   :target: https://convtools.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://badge.fury.io/py/convtools.svg
   :target: https://badge.fury.io/py/convtools

.. image:: https://img.shields.io/github/tag/itechart-almakov/convtools.svg
   :target: https://GitHub.com/itechart-almakov/convtools/tags/

.. image:: https://img.shields.io/github/license/itechart-almakov/convtools.svg
   :target: https://github.com/itechart-almakov/convtools/blob/master/LICENSE.txt


Description
===========

The speed of **convtools** comes from the approach of generating code & compiling
conversion functions, which don't have any generic code like superfluous
loops, ifs, etc.

So you can follow the DRY principle by storing and reusing the code on the
python expression level, but at the same time be able to run the
``gen_converter`` and get the compiled code which doesn't care about being DRY
and is generated to be highly specialized for the specific need.


Conversions are not limited to simple data transformations, there are
``GroupBy`` & ``Aggregate`` conversions with many useful reducers:

 * from common `Sum`, `Max`
 * and less widely supported `First`/`Last`, `Array`/`ArrayDistinct`
 * to `DictSum`-like ones (for nested aggregation) and `MaxRow`/`MinRow`
   (for finding an object with max/min value and further processing)

Every conversion:
 * contains the information of how to transform an input
 * can be piped into another conversion (same as wrapping)
 * has a method ``gen_converter`` returning a function compiled at runtime,
   which benefits from being highly specialized for the particular need
   (no superflious loops, minimum number of function calls)
 * despite being compiled at runtime, is debuggable due to `linecache` populating.

Installation:
=============

.. code-block:: bash

   pip install convtools

Documentation
=============

`convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
