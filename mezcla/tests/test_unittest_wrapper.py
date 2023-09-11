#! /usr/bin/env python
#
# Test(s) for ../unittest_wrapper.py
#
# Notes:
# - For debugging the tested script, the ALLOW_SUBCOMMAND_TRACING environment
#   option shows tracing output normally suppressed by unittest_wrapper.py.
# - This can be run as follows:
#   $ PYTHONPATH=".:$PYTHONPATH" python ./mezcla/tests/test_unittest_wrapper.py
#

"""Tests for unittest_wrapper module"""

# Installed packages
import pytest

# Local packages
## TODO (effing pytest): from mezcla.unittest_wrapper import TestWrapper, trap_exception, pytest_fixture_wrapper
from mezcla.unittest_wrapper import TestWrapper
from mezcla import debug
from mezcla.my_regex import my_re

# Note: Two references are used for the module to be tested:
#    THE_MODULE:                  global module object
#    TestTemplate.script_module:  path to file
import mezcla.unittest_wrapper as THE_MODULE
#
# Note: sanity test for customization (TODO: remove if desired)
if not my_re.search(__file__, r"\btemplate.py$"):
    debug.assertion("mezcla.template" not in str(THE_MODULE))


## TODO (use TestWrapper directly):

## class TestIt(TestWrapper):
##     """Class for command-line based testcase definition"""
##     script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)
## 
##     ## TODO: @pytest.mark.xfail                   # TODO: remove xfail
##     ## TODO:
##     ## @pytest_fixture_wrapper
##     ## @trap_exception
##     def test_do_assert(self, capsys):
##         """Ensure do_assert identifies failing line"""
##         debug.trace(4, f"TestIt.test_do_assert({capsys}); self={self}")
##         captured_trace = ""
##         try:
##             captured_trace = capsys.readouterr()
##             self.do_assert(False)
##         except AssertionError:
##             pass
##         self.do_assert(my_re.search("do_assert", captured_trace))
##         return

class TestIt2:
    """Class for API usage"""

    ## TODO:
    ## @pytest_fixture_wrapper
    ## @trap_exception
    def test_do_assert(self, capsys):
        """Ensure do_assert identifies failing line"""
        debug.trace(4, f"TestIt.test_do_assert({capsys}); self={self}")
        #
        class SubTestIt(TestWrapper):
            """Embedded test suite"""
            pass
        #
        sti = SubTestIt()        
        captured_trace = ""
        try:
            sti.do_assert(False)
        except AssertionError:
            pass
        captured_trace = capsys.readouterr().err
        debug.trace_expr(5, captured_trace)
        assert(my_re.search(r"\bdo_assert\b", captured_trace))
        return

#------------------------------------------------------------------------

if __name__ == '__main__':
    debug.trace_current_context()
    pytest.main([__file__])
