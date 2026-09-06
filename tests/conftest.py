# -*- coding: utf-8 -*-
"""Test harness: strict ctx so undeclared globals fail the suite."""

from convtools._base import BaseConversion

BaseConversion.strict_ctx = True
