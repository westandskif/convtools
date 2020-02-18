=========
convtools
=========


**convtools** is a python library to declaratively define conversions from python
objects to python objects, including processing collections and doing complex
aggregations.

.. image:: https://readthedocs.org/projects/convtools/badge/?version=latest
   :target: https://convtools.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

Description
===========

Conversions are not limited to simple data transformations, there are
``GroupBy`` & ``Aggregate`` conversions with many useful reducers:

 * from common `Sum`, `Max`
 * and less widely supported `First`/`Last`, `Array`/`ArrayDistinct`
 * to `DictSum`-like ones (for nested aggregation) and `MaxRow`/`MinRow`
   (for finding an object with max/min value and further processing)

Every conversion:
 * contains the information of how to transform input data
 * can be piped into another conversion (same as wrapping)
 * has a method ``gen_converter`` returning a function compiled at runtime,
   which benefits from being highly specialized for the particular need
   (no superflious loops, minimum number of function calls)
 * despite being compiled at runtime, is debuggable due to `linecache` populating.


Documentation
=============

`convtools on Read the Docs <https://convtools.readthedocs.io/en/latest/>`_
