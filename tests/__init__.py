"""
Test Suite for ath_core
"""

import unittest
import os
import sys

# Bootstrap the external libs
TEST_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.abspath(os.path.join(TEST_DIR, '../external')))  # dependencies
sys.path.insert(0, os.path.abspath(os.path.join(TEST_DIR, '../core')))  # core code to test
sys.path.insert(0, os.path.abspath(os.path.join(TEST_DIR, '../')))  # project root to import tests
sys.path.insert(0, TEST_DIR)  # test support for auth_core_settings etc


class TestCaseBase(unittest.TestCase):
    """
    Base Unit Test Case
    """
    is_unit = True
