.. _convtools_fs:

=================================
convtools fs - filesystem helpers
=================================

1. Split buffers
________________

Since Python's :py:obj:`open` doesn't support custom newlines in the text mode
and doesn't support "newlines" (delimiters) in binary mode, it is convenient
to have a helper for this - :py:obj:`convtools.contrib.fs.split_buffer`:

.. code-block:: python

   from convtools.contrib.fs import split_buffer

   with open("input.txt", "r") as f:
       lines_generator = split_buffer(f, delimiter=";;;")

       # e.g. convenient for
       from convtools.contrib.tables import Table
       Table.from_csv(lines_generator, header=True).into_csv("output.csv")

 
There's also a sibling method, which also runs decode on each element -
:py:obj:`convtools.contrib.fs.split_buffer_n_decode`:


.. code-block:: python

   from convtools.contrib.fs import split_buffer_n_decode

   with open("input.txt", "rb") as f:
       lines_generator = split_buffer_n_decode(f, delimiter=b";;;")

