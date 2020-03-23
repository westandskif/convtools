0.5.0 (2020-03-23)
------------------

Features
++++++++

- - increased the speed of ``c.aggregate`` and ``c.group_by`` by collapsing multiple ``if`` statements into one
  - updated labeling functionality
  `#11 <https://github.com/itechart-almakov/convtools/issues/11>`_


----


0.4.0 (2020-03-19)
------------------

Features
++++++++

- Improved the way ``linecache`` is used: now the number of files to be put
  into the ``linecache`` is limited to 100. The eviction is done by implementing
  recently used strategy.
  `#9 <https://github.com/itechart-almakov/convtools/issues/9>`_
- - introduced ``c.join``
  - improved & fixed pipes (code with side-effects piped to a constant)
  `#10 <https://github.com/itechart-almakov/convtools/issues/10>`_


----


0.3.3 (2020-03-06)
------------------

Features
++++++++

- 1. fixed main example docs
  2. improved ``c.aggregate`` speed
  `#8 <https://github.com/itechart-almakov/convtools/issues/8>`_


----


0.3.2 (2020-03-05)
------------------

Improved Documentation
++++++++++++++++++++++

- * updated docs (fixed numbers) and updated pypi docs


----


0.3.1 (2020-03-05)
------------------

Features
++++++++

- * introduced c.OptionsCtx
  * improved tests - memory leaks
  * improved docs - added the index page example; added an example to QuickStart
  `#7 <https://github.com/itechart-almakov/convtools/issues/7>`_


----


0.3.0 (2020-03-01)
------------------

Features
++++++++

- Introduced `labeling`:

    * ``c.item("companies").add_label("first_company", c.item(0))`` labels the first
      company in the list as `first_company` and allows to use it as
      ``c.label("first_company") further in next and even nested conversions
  
    * ``(...).pipe`` now receives 2 new arguments: 

      * `label_input`, to put some labels on the pipe input data
      * `label_output` to put labels on the output data.

      Both can be either ``str`` (label name to put on) or ``dict`` (keys are label names
      and values are conversions to apply to the data before labeling)
  `#6 <https://github.com/itechart-almakov/convtools/issues/6>`_


Bugfixes
++++++++

- Added ``__name__`` attribute to ctx. Now internal code from the generated converter is sending to Sentry (not only file name).
  Also the generated converter became a callable object, not a function.
  `#5 <https://github.com/itechart-almakov/convtools/issues/5>`_


----


0.2.3 (2020-02-27)
------------------

Bugfixes
++++++++

- Fixed ``c.group_by((c.item("name"),)).aggregate((c.item("name"), c.reduce(...)))``.
  Previously it was compiling successfully, now it raises ``ConversionException`` on ``gen_converter``
  because there is no explicit mention of ``c.item("name")`` field in group by keys (only tuple).
  `#4 <https://github.com/itechart-almakov/convtools/issues/4>`_


----


0.2.2 (2020-02-25)
------------------

Bugfixes
++++++++

- fixed ``c.aggregate`` to return a single value for empty input
  `#3 <https://github.com/itechart-almakov/convtools/issues/3>`_


----


0.2.1 (2020-02-24)
------------------

Bugfixes
++++++++

- ``c.aggregate`` now returns a single value (previously the result was a list of one item)
  `#2 <https://github.com/itechart-almakov/convtools/issues/2>`_


----


0.2.0 (2020-02-23)
------------------

Features
++++++++

- added ``c.if_`` conversion and introduced QuickStart docs
  `#1 <https://github.com/itechart-almakov/convtools/issues/1>`_


----
