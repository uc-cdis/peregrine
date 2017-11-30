# -*- coding: utf-8 -*-
"""
This module is only to test that setting the environment variable
GDC_API_LEGACY_MODE properly turns on LEGACY_MODE and uses the legacy
mapping. The test suite should be repeated both with
``GDC_API_LEGACY_MODE=true`` set and without.
"""

import os

from peregrine.config import LEGACY_MODE
from peregrine.models.mapping import mappings

from esbuild.graph.active import mappings as active_mappings
from esbuild.graph.legacy import mappings as legacy_mappings


IS_LEGACY_MODE = os.environ.get('GDC_API_LEGACY_MODE', '').lower() == 'true'


def test_legacy_mode_flag():
    assert IS_LEGACY_MODE == LEGACY_MODE


def test_conditional_mapping():
    if IS_LEGACY_MODE:
        assert mappings == legacy_mappings
    else:
        assert mappings == active_mappings
