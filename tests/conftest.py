# -*- coding: utf-8 -*-
"""Test harness: strict ctx so undeclared globals fail the suite."""

from convtools._base import BaseConversion

from .utils import _StrictCtx

BaseConversion.ctx_factory = _StrictCtx
