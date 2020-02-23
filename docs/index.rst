=========
convtools
=========

.. _ref_index_intro:

**convtools** is a python library to declaratively define fast conversions
from python objects to python objects, including processing collections and
doing complex aggregations.

The speed of **convtools** comes from the approach of generating code & compiling
conversion functions, which don't have any generic code like superfluous
loops, ifs, etc.

.. note::

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
 * has a method ``gen_converter`` returning a function compiled at runtime
 * despite being compiled at runtime, is debuggable with `pdb` due to `linecache` populating.


Installation:
=============

.. code-block:: bash

   pip install convtools

Next steps:
===========

 1. :ref:`QuickStart<convtools_quickstart>`
 2. :ref:`Cheatsheet<convtools_cheatsheet>`
 3. :ref:`API doc<convtools_api_doc>`


Contents
========

.. toctree::
   :maxdepth: 2

   QuickStart <quick_start>
   Cheatsheet <cheatsheet>
   API doc <api_doc>
   License <license>
   Changelog <changelog>
   Authors <authors>
   Module Reference <api/modules>


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
