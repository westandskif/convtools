=========
convtools
=========

**convtools** is a python library to declaratively define conversions from python
objects to python objects, including processing collections and doing complex
aggregations.

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


Installation:
=============

.. code-block:: bash

   pip install convtools

Next steps:
===========

 1. :ref:`Cheatsheet<convtools cheatsheet>`
 2. :ref:`Reference doc<convtools Reference Doc>`


Contents
========

.. toctree::
   :maxdepth: 2

   License <license>
   Changelog <changelog>
   Cheatsheet <cheatsheet>
   Reference Doc <reference_doc>
   Module Reference <api/modules>
   Authors <authors>


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _toctree: http://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html
.. _reStructuredText: http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html
.. _references: http://www.sphinx-doc.org/en/stable/markup/inline.html
.. _Python domain syntax: http://sphinx-doc.org/domains.html#the-python-domain
.. _Sphinx: http://www.sphinx-doc.org/
.. _Python: http://docs.python.org/
.. _Numpy: http://docs.scipy.org/doc/numpy
.. _SciPy: http://docs.scipy.org/doc/scipy/reference/
.. _matplotlib: https://matplotlib.org/contents.html#
.. _Pandas: http://pandas.pydata.org/pandas-docs/stable
.. _Scikit-Learn: http://scikit-learn.org/stable
.. _autodoc: http://www.sphinx-doc.org/en/stable/ext/autodoc.html
.. _Google style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings
.. _NumPy style: https://numpydoc.readthedocs.io/en/latest/format.html
.. _classical style: http://www.sphinx-doc.org/en/stable/domains.html#info-field-lists
