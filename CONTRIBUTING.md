# Contributing

I'd love you to contribute to `convtools`!

## Questions / discussions

Should you have any questions, feel free to start a discussion
[here](https://github.com/westandskif/convtools/discussions).

## Issues

Feature requests and bug reports are all welcome, please
submit an issue
[here](https://github.com/westandskif/convtools/issues).


## Security 

To report a security issue, please see the
[security policy](https://github.com/westandskif/convtools/security/policy).

## Pull requests

Unless your change is trivial, please start a discussion or submit an issue to
discuss before creating a pull request.

1. clone the repo
1. install dev requrements: `pip install -r requirements/dev.in`
1. install docs requirements: `pip install -r requirements/docs.txt`
   (_versions are pinned for python 3.9_)
1. make a change
1. make sure tests are passed: `pytest`
1. make sure docs are building: `make docs && make docs_serve`
1. include the info to be put into the changelog in PR description
1. commit the changes and open a pull request
