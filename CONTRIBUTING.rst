Contributing
============

Instructions for contributors
-----------------------------


In order to make a clone of the GitHub_ repo: open the link and press the
"Fork" button on the upper-right menu of the web page.

I hope everybody knows how to work with git and github nowadays :)

Workflow is pretty straightforward:

  1. Clone the GitHub_ repo

  2. Setup your machine with the required dev environment

        * ``pip install -e .``
        * install ``aspell``

  3. Make a change

  4. Make sure all tests passed, docs are building, spelling is ok (or add words):

        * ``pytest .``
        * ``make docs``
        * ``make spellcheck``

  5. Add a file into the ``CHANGES`` folder, named after the ticket or PR number
       towncrier has a few standard types of news fragments, signified by the file extension. These are:

        * .feature: Signifying a new feature.
        * .bugfix: Signifying a bug fix.
        * .doc: Signifying a documentation improvement.
        * .removal: Signifying a deprecation or removal of public API.
        * .misc: A ticket has been closed, but it is not of interest to users.

  6. Commit changes to your own convtools clone

  7. Make a pull request from the github page of your clone against the master branch

  8. Optionally make backport Pull Request(s) for landing a bug fix into released convtools versions.

.. _GitHub: https://github.com/aio-libs/aiohttp
