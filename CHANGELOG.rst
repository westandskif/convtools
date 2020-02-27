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
