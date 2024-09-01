# Contributing

The best way to support the development of convtools is to spread the word!

Also, if you already are a convtools user, we would love to hear about your use
cases and challenges in the [Discussions
section](https://github.com/westandskif/convtools/discussions).

To report a bug or suggest enhancements, please open [an
issue](https://github.com/westandskif/convtools/issues) and/or submit [a pull
request](https://github.com/westandskif/convtools/pulls).


**Reporting a Security Vulnerability**: see the [security policy](https://github.com/westandskif/convtools/security/policy).

## Pull requests

Unless your change is trivial, please start a discussion or submit an issue to
discuss before creating a pull request.

1. clone the repo
1. install python 3.10
1. install dev requrements: `pip install -r ci-requirements/requirements3.10.out`
1. make a change
1. make sure tests are passed: `pytest`
1. make sure checks are passed: `make checks`
1. make sure docs are building: `make docs`
1. include the info to be put into the changelog in PR description
1. commit the changes and open a pull request
