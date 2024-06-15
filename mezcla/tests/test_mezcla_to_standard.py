"""
Tests for mezcla_to_standard module
"""

# Standard packages
## NOTE: this is empty for now
from unittest.mock import patch, MagicMock, ANY
import logging

# Installed packages
import pytest
import libcst as cst

# Local packages
import mezcla.mezcla_to_standard as THE_MODULE
from mezcla import system, debug, glue_helpers as gh
from mezcla.my_regex import my_re
from mezcla.unittest_wrapper import TestWrapper

class TestEqCall(TestWrapper):
    """Class for test usage of EqCall class in mezcla_to_standard"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)

    # @pytest.mark.parametrize(
    #     "eq_call, params, expected_dest_arguments", 
    #     [
    #         (THE_MODULE[0], {"source": "src_file", "target": "dst_file"}, ("src_file", "dst_file")),
    #         (THE_MODULE[1], {"filename": "file.txt"}, ("file.txt",)),
    #         (THE_MODULE[2], {"filenames": ["dir", "file.txt"]}, (["dir", "file.txt"],)),
    #         (THE_MODULE[3], {"text": "debug message"}, ("debug message",)),
    #         (THE_MODULE[4], {"text": "info message"}, ("info message",)),
    #         (THE_MODULE[5], {"text": "warning message"}, ("warning message",)),
    #         (THE_MODULE[6], {"text": "error message"}, ("error message",))
    #     ]
    # )
    # @patch('os.rename')         # Equivalent: gh.rename_file
    # @patch('os.remove')         # Equivalent: gh.delete_file
    # @patch('os.path.join')      # Equivalent: gh.form_path
    # @patch('logging.debug')     # Equivalent: debug.trace level=4
    # @patch('logging.info')      # Equivalent: debug.trace level=3
    # @patch('logging.warning')   # Equivalent: debug.trace level=2
    # @patch('logging.error')     # Equivalent: debug.trace level=1

    # def test_eq_calls(
    #     mock_rename,
    #     mock_remove,
    #     mock_join,
    #     mock_debug,
    #     mock_info,
    #     mock_warning,
    #     mock_error,
    #     eq_call, params, expected_dest_args
    # ):
    #     eq_call = THE_MODULE.EqCall()
    #     # Choose a mock based on the destination function
    #     mock_dest = {
    #     os.rename: mock_rename,
    #     os.remove: mock_remove,
    #     os.path.join: mock_join,
    #     logging.debug: mock_debug,
    #     logging.info: mock_info,
    #     logging.warning: mock_warning,
    #     logging.error: mock_error
    # }[eq_call.dest]
        
    #     # Ensure condition is met
    #     if "level" in params:
    #         condition_met = eq_call.condition(params["level"])
    #     else:
    #         condition_met = eq_call.condition()

    #     if condition_met:
    #         # Translate eq_params to standard
    #         standard_params = {
    #             val: params[key] for key, val in (eq_call.eq_params or {}).items()
    #         }
    #         if eq_call.extra_params:
    #             standard_params.update(eq_call.extra_params)
            
    #         # Call the destination function with translated params
    #         eq_call.dest(**standard_params)

    #         # Assert the destination function was called with expected params
    #         mock_dest.assert_called_once_with(*expected_params)
    
    def helper_get_eqcall(self, func):
        """Helper function for obtaining all equivalent calls for a function"""
        return next(
            call
            for call in THE_MODULE.mezcla_to_standard
            if call.target is func
        )
    
    def test_rename_file(self):
        """Tests for equivalence of gh.rename_file to os.rename"""
        eq_call = self.helper_get_eqcall(gh.rename_file)
        # self.assertEqual(eq_call.dest, os.rename)
        self.assertEqual(eq_call.eq_params, {"source": "src", "target": "dst"})

    def test_delete_file(self):
        """Tests for equivalence of gh.delete_file to os.remove"""
        eq_call = self.helper_get_eqcall(gh.delete_file)
        # self.assertEqual(eq_call.dest, os.remove)
        self.assertEqual(eq_call.eq_params, {"filename": "path"})

    def test_form_path(self):
        """Tests for equivalence of gh.form_path to os.path.join"""
        eq_call = self.helper_get_eqcall(gh.form_path)
        # self.assertEqual(eq_call.dest, os.path.join)
        self.assertEqual(eq_call.eq_params, {"filenames": "a"})

    def test_trace_logging_levels(self):
        """Tests for equivalence of debug (mezcla) to logging module"""
        for level, log_func in \
            [(4, logging.debug), (3, logging.info), (2, logging.warning), (1, logging.error)]:
            eq_call = next((call for call in THE_MODULE.mezcla_to_standard if call.target is debug.trace and call.condition(level)), None)
            self.assertIsNotNone(eq_call)
            self.assertEqual(eq_call.dest, log_func)
            self.assertEqual(eq_call.eq_params, {"text": "msg"})
            self.assertEqual(eq_call.extra_params, {"level": int(level)})

class TestBaseTransformerStrategy:
    """Class for test usage of ToStandard class in mezcla_to_standard"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)
    
    # Creating mock functions for testing        
    def slope(x1:int, y1:int, x2:int, y2:int):
        return (y2 - y1)/(x2 - x1)
    
    def distance(x1:int, y1:int, x2:int, y2:int) -> float:
        return round(( (x2 - x1) ** 2 + (y2 - y1) ** 2 ) ** 0.5, 2)

    @pytest.mark.xfail  ## TODO: Fix XFAIL (result is weird)
    def test_insert_extra_params(self):
        """Ensures that insert_extra_params method of BaseTransformerStrategy class works as expected"""
        extra_params = {"x1": 3, "y1": 5, "x2": 6}
        args = {"x1": 10, "y2": 12}

        expected_result = extra_params|args # Union of dictionary

        eqcall = THE_MODULE.EqCall(target=self.slope, dest=None, extra_params=extra_params)
        bts = THE_MODULE.BaseTransformerStrategy()
        result = bts.insert_extra_params(self, eq_call=eqcall, args=args)
        print(result, "="*50, expected_result)
        assert result == expected_result

    def test_filter_args_by_function(self):
        ## OLD: Eqcall._filter_args_by_function
        """Ensures that filter_args_by_function method of BaseTransformerStrategy class works as expected"""
        args= {"x1": 23, "x2": 322, "x3": -54, "y1":12, "y2": -34, "y3": 111}
        expected_args = {"x1": 23, "y1": 12, "x2":322, "y2":-34}
        bts = THE_MODULE.BaseTransformerStrategy
        result = bts.filter_args_by_function(self, self.slope, args)
        assert result == expected_args

    def test_get_replacement(self):
        ## OLD: Eqcall._filter_args_by_function
        """Ensures that get_replacement method of BaseTransformerStrategy class works as expected"""
        args = {"x1": 20, "y1": 10, "x2":30, "y2":-60}
        pass

    @pytest.mark.xfail  
    def test_eq_call_to_module_func(self):
        """Ensures that eq_call_to_module_func method of BaseTransformerStrategy class works as expected"""
        assert False, "NOT_IMPLEMENTED_IN_FILE"
        ## TODO: Wait for function to be implemented
    
    @pytest.mark.xfail  
    def test_find_eq_call(self):
        """Ensures that find_eq_call method of BaseTransformerStrategy class works as expected"""
        assert False, "NOT_IMPLEMENTED_IN_FILE"
        ## TODO: Wait for function to be implemented
    
    @pytest.mark.xfail  
    def test_get_args_replacement(self):
        """Ensures that get_args_replacement_func method of BaseTransformerStrategy class works as expected"""
        assert False, "NOT_IMPLEMENTED_IN_FILE"
        ## TODO: Wait for function to be implemented
    
    @pytest.mark.xfail  
    def test_is_condition_to_replace_met(self):
        """Ensures that is_condition_to_replace_met method of BaseTransformerStrategy class works as expected"""
        assert False, "NOT_IMPLEMENTED_IN_FILE"
        ## TODO: Wait for function to be implemented


class TestToStandard:
    """Class for test usage of ToStandard class in mezcla_to_standard"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)

    # Sample functions to be used in tests
    @staticmethod
    def sample_func1(a):
        """First sample function"""
        pass

    @staticmethod
    def sample_func2(b):
        """Second sample function"""
        pass

    @pytest.fixture
    def setup_to_standard(self):
        to_standard = THE_MODULE.ToStandard()
        mezcla_to_standard = [
            THE_MODULE.EqCall(target=self.sample_func1, dest=self.sample_func1),
            THE_MODULE.EqCall(target=self.sample_func2, dest=self.sample_func2)
        ]
        to_standard.mezcla_to_standard = mezcla_to_standard
        return to_standard

    ## find_eq_call does not work as intended (e.g. eq_call = None and None is not None)
    @pytest.mark.xfail
    def test_tostandard_find_eq_call_existing(self, setup_to_standard):
        """Test for finding an existing equivalent call"""
        module = "mezcla"
        method = "sample_func1"
        args = ['a']
        to_standard = setup_to_standard
        eq_call = to_standard.find_eq_call(module=module, func=method, args=args)
        assert eq_call is not None
        assert eq_call.target == self.sample_func1

    def test_tostandard_find_eq_call_non_existing(self, setup_to_standard):
        """Test for trying to find a non-existing equivalent call"""
        module = "mezcla"
        method = "no_exist_func"
        args = ['b']
        to_standard = setup_to_standard
        # Correct assertion, but does not work as intended (no need for XFAIL)
        eq_call = to_standard.find_eq_call(module=module, func=method, args=args)
        assert eq_call is None

    # Does not work as intended (Result = None)
    @pytest.mark.xfail
    def test_tostandard_find_eq_call(self):
        """Ensures that find_eq_call of ToStandard class works as expected"""
        
        class MockEqCall:
            def __init__(self, module, func, condition_met=True):
                self.target = type(
                'MockClass', (object,), {'__module__': f'{module}.mock'}
                )()
                self.target.__name__ = func
                self.condition_met = condition_met

            def is_condition_to_replace_met(self, args):
                return self.condition_met
        # Create a ToStandard instance
        to_standard = THE_MODULE.ToStandard()
        mezcla_to_standard = [
            MockEqCall('my_module', 'my_function'),
            MockEqCall('other_module', 'other_function')
        ]
        # Assertion for eq_call match
        result = to_standard.find_eq_call("my_module", "my_function", ['arg1', 'arg2'])
        assert result == mezcla_to_standard[0]

    # Static sample functions for is_condition_to_replace_met
    @staticmethod
    def sample_func1(a, b):
        """First sample function"""
        pass

    @staticmethod
    def sample_func2(a, b):
        """Second sample function"""
        pass

    @pytest.fixture
    def setup_to_standard(self):
        to_standard = THE_MODULE.ToStandard()
        mezcla_to_standard = [
            THE_MODULE.EqCall(target=self.sample_func1, dest=None, condition=lambda a, b: a > b),
            THE_MODULE.EqCall(target=self.sample_func2, dest=None, condition=lambda a, b: a == b)
        ]
        to_standard.mezcla_to_standard = mezcla_to_standard
        return to_standard

    @pytest.mark.xfail
    # Error Involved: on arg_to_value(arg: cst.Arg) -> object
    # AttributeError: 'int' object has no attribute 'value'
    def test_is_condition_to_replace_met(self, setup_to_standard):
        """Ensures that is_condition_to_replace_met of ToStandard class works as expected"""
        to_standard = setup_to_standard

        eq_call = THE_MODULE.EqCall(target=self.sample_func1, dest=None, condition=lambda a, b: a > b)
        args = [4, 3]
        result = to_standard.is_condition_to_replace_met(eq_call, args)
        assert result is True

    @pytest.mark.xfail
    def test_get_args_replacement(self):
        """Ensures that get_args_replacement method of ToStandard class works as expected"""
        result = THE_MODULE.ToStandard.get_args_replacement()
        assert False, "TODO: Implement"

    @pytest.mark.xfail
    def test_replace_args_keys(self):
        """Ensures that replace_args_keys method of ToStandard class works as expected"""
        result = THE_MODULE.ToStandard.replace_args_keys()
        assert False, "TODO: Implement"
        
    @pytest.mark.xfail
    def test_eq_call_to_module_func(self):
        """Ensures that eq_call_to_module_func method of ToStandard class works as expected"""
        result = THE_MODULE.ToStandard.eq_call_to_module_func()
        assert False, "TODO: Implement"

# Unit testing of function
class TestToMezcla:
    """Class for test usage of ToMezcla class in mezcla_to_standard"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)

    @staticmethod
    def sample_func1(a, b):
        """First sample function"""
        pass

    @staticmethod
    def sample_func2(a, b):
        """Second sample function"""
        pass

    @staticmethod
    def standard_func1(src, dst):
        """Standard equivalent function for sample_func1"""
        pass

    @staticmethod
    def standard_func2(path):
        """Standard equivalent function for sample_func2"""
        pass

    @pytest.fixture
    def setup_to_mezcla(self):
        to_mezcla = THE_MODULE.ToMezcla()
        mezcla_to_standard = [
            THE_MODULE.EqCall(
                target=self.sample_func1,
                dest=self.standard_func1,
                condition=lambda a, b: a > b,
                eq_params={"a": "src", "b": "dst"}
            ),
            THE_MODULE.EqCall(
                target=self.sample_func2,
                dest=self.standard_func2,
                condition=lambda a, b: a == b,
                eq_params={"a": "path"}
            )
        ]
        # Directly assigning mezcla_to_standard to the instance
        setattr(to_mezcla, 'mezcla_to_standard', mezcla_to_standard)
        return to_mezcla

    ## TEST 1: find_eq_call (existing function)
    ## Error encountered: FAILED mezcla/tests/test_mezcla_to_standard.py::TestToMezcla::test_tomezcla_find_eq_call_existing - AttributeError: 'list' object has no attribute '__module__'
    @pytest.mark.xfail
    def test_tomezcla_find_eq_call_existing(self, setup_to_mezcla):
        """Test for finding an existing equivalent call for ToMezcla class"""
        to_mezcla = setup_to_mezcla
        module, method, args = "mezcla", "standard_func1", [4, 3]
        eq_call = to_mezcla.find_eq_call(module, method, args)
        assert eq_call is not None
        assert eq_call.target == self.sample_func1

    
    ## TEST 2: find_eq_call (non-existing function)
    ## Error encountered: FAILED mezcla/tests/test_mezcla_to_standard.py::TestToMezcla::test_tomezcla_find_eq_call_existing - AttributeError: 'list' object has no attribute '__module__'
    @pytest.mark.xfail
    def test_tomezcla_find_eq_call_non_existing(self, setup_to_mezcla):
        """Test for not finding an existing equivalent call for ToMezcla class"""
        to_mezcla = setup_to_mezcla
        module, method, args = "mezcla", "standard_func3", [4, 3]
        eq_call = to_mezcla.find_eq_call(module, method, args)
        assert eq_call is None

    ## TEST 3: is_condition_to_replace_met
    ## NOTE: AttributeError detected

    #     def arg_to_value(arg: cst.Arg) -> object:
    #         """Convert the argument to a value"""
    # >       return eval(arg.value.value)
    # E       AttributeError: 'int' object has no attribute 'value'
    
    @pytest.mark.xfail
    def test_is_condition_to_replace_met(self, setup_to_mezcla):
        """Test for is_condition_to_replace_met in ToMezcla class"""
        to_mezcla = setup_to_mezcla
        
        eq_call = THE_MODULE.EqCall(target=self.sample_func1, dest=self.standard_func1, condition=lambda a, b: a > b, eq_params={"a": "src", "b": "dst"})
        args = [4, 3]
        result = to_mezcla.is_condition_to_replace_met(eq_call, args)
        assert result is True

        args = [3, 4]
        result = to_mezcla.is_condition_to_replace_met(eq_call, args)
        assert result is False

        eq_call = THE_MODULE.EqCall(target=self.sample_func2, dest=self.standard_func2, condition=lambda a, b: a == b, eq_params={"a": "path"})
        args = [4, 4]
        result = to_mezcla.is_condition_to_replace_met(eq_call, args)
        assert result is True

        args = [4, 5]
        result = to_mezcla.is_condition_to_replace_met(eq_call, args)
        assert result is False

    ## TEST 4: get_args_replacement
    def test_get_args_replacement(self, setup_to_mezcla):
        """Test for get_args_replacement method in ToMezcla class"""
        to_mezcla = setup_to_mezcla
        eq_call = THE_MODULE.EqCall(target=self.sample_func1, dest=self.standard_func1, condition=lambda a, b: a > b, eq_params={"a": "src", "b": "dst"})

        # For multiple arguments in function using multiple arguments
        args = [4, 3]
        kwargs = {}
        result = to_mezcla.get_args_replacement(eq_call, args, kwargs)
        assert result == [4, 3]

        # For multiple arguments in function using single argument (selects first arg)
        eq_call = THE_MODULE.EqCall(target=self.sample_func2, dest=self.standard_func2, condition=lambda a, b: a == b, eq_params={"a": "path"})
        args = [4, 4]
        kwargs = {}
        result = to_mezcla.get_args_replacement(eq_call, args, kwargs)
        assert result == [4]

    ## TEST 5: replace_args_keys
    def test_replace_args_keys(self, setup_to_mezcla):
        """Test for replace_args_keys method in ToMezcla class"""
        to_mezcla = setup_to_mezcla
        
        # For multiple arguments
        eq_call = THE_MODULE.EqCall(target=self.sample_func1, dest=self.standard_func1, eq_params={"a": "src", "b": "dst"})
        args = {"src": 4, "dst": 3}
        result = to_mezcla.replace_args_keys(eq_call, args)
        assert result == {"a": 4, "b": 3}

        # For single argument
        eq_call = THE_MODULE.EqCall(target=self.sample_func2, dest=self.standard_func2, eq_params={"a": "path"})
        args = {"path": 4}
        result = to_mezcla.replace_args_keys(eq_call, args)
        assert result == {"a": 4}

    ## TEST 6: eq_call_to_module_func
    def test_eq_call_to_module_func(self, setup_to_mezcla):
        """Test for eq_call_to_module_func method in ToMezcla class"""
        to_mezcla = setup_to_mezcla

        eq_call = THE_MODULE.EqCall(target=self.sample_func1, dest=self.standard_func1)
        module, func = to_mezcla.eq_call_to_module_func(eq_call)
        assert module == self.sample_func1.__module__
        assert func == self.sample_func1.__name__

        eq_call = THE_MODULE.EqCall(target=self.sample_func2, dest=self.standard_func2)
        module, func = to_mezcla.eq_call_to_module_func(eq_call)
        assert module == self.sample_func2.__module__
        assert func == self.sample_func2.__name__


@pytest.fixture
def mock_to_module():
    """Mock for the to_module dependency"""
    # Define mock behavior for get_replacement
    mock_to_module = MagicMock()

    # Mock function for get_replacement method
    def mock_get_replacement(module_name, func, args):
        new_module = cst.Name(f"import_{module_name}")
        new_func_node = cst.Name(f"new_func_{module_name}")
        new_args_nodes = args
        return new_module, new_func_node, new_args_nodes

    mock_to_module.get_replacement.side_effect = mock_get_replacement
    return mock_to_module
    
class TestTransform(TestWrapper):
    """Class for test usage for methods of transform method in mezcla"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_to_module):
        self.mock_to_module = mock_to_module
    
    @pytest.mark.xfail
    def test_transform(self):
        """Unit test for transform function"""
        # Example Python code to transform
        code = """
import module_a
from module_b import func1, func2
from module_c import func3 as f3
from other_module import func4
x = func1(1, 2)
y = module_a.func2(3, 4)
z = func3(5, 6)
        """
        
        # Expected transformed code after calling transform function
        expected_transformed_code = """
import import_module_a
import import_module_b
from other_module import func4
x = new_func_module_b(1, 2)
y = new_func_module_a(3, 4)
z = func3(5, 6)
        """

        # Acutal transformed code is a bit confusing, this marking the test as xfail
        _expected_transformed_code = """
import import_module_a
import module_a
from module_b import func1, func2
from module_c import func3 as f3
from other_module import func4
x = func1(1, 2)
y = new_func_module_a(3, 4)
z = func3(5, 6)
"""       
        # Call transform function
        transformed_code = THE_MODULE.transform(self.mock_to_module, code)
        # Assert that the transformed code matches the expected transformed code
        assert transformed_code.strip() == expected_transformed_code.strip()

        # Additional assertions if needed to verify mock interactions
        self.mock_to_module.get_replacement.assert_any_call('module_a', ANY, ANY)
        self.mock_to_module.get_replacement.assert_any_call('module_b', ANY, ANY)
        self.mock_to_module.get_replacement.assert_any_call('module_c', ANY, ANY)
    
    # Unit Testing I
    @pytest.mark.xfail
    def test_leave_module(self):
        """Ensures that leave_Module method of CustomVisitor works as expected"""
        
        class TestVisitor(THE_MODULE.transform.CustomVisitor):
            def __init__(self, to_module):
                super().__init__(to_module)
        
        code = """
import module_a
x = module_a.func1(1, 2)
        """

        tree = cst.parse_module(code)
        visitor = TestVisitor(mock_to_module)
        visitor.to_import.append(cst.Name("new_module"))
        modified_tree = tree.visit(visitor)

        expected_code = """
import new_module
import module_a
x = module_a.func1(1, 2)
        """
        # Result currently similar/same to original code (no changes)
        # BAD: assert result.strip() == code.strip()
        assert modified_tree.code.strip() == cst.parse_module(expected_code).code.strip()
    
    # Unit Testing II
    # Error: AttributeError: 'function' object has no attribute 'CustomVisitor'
    @pytest.mark.xfail
    def test_visit_importalias(self):
        """Ensures that visit_ImportAlias method of CustomVisitor works as expected"""
        
        code = """
import my_module as mm
from another_module import submodule as sm
"""
        expected_aliases = {
            "mm": "my_module",
            "sm": "submodule"
        }

        # Parse the code into a CST tree
        tree = cst.parse_module(code)

        # Create an instance of CustomVisitor
        visitor = THE_MODULE.transform.CustomVisitor(None)

        # Visit the tree with the custom visitor
        tree.visit(visitor)

        # Assert that the aliases were correctly stored
        assert visitor.aliases == expected_aliases

    
    # Unit Testing III
    @pytest.mark.xfail
    def test_leave_call(self):
        """Ensures that leave_Call method of CustomVisitor works as expected"""
        original_code = """
result = old_module.old_function(2, 3)
"""
        expected_code = """
from new_module import new_function
result = new_function(2, 3)
"""
        result = THE_MODULE.transform(self.to_module, original_code)
        assert result.strip() == expected_code.strip()
    
    # Unit Testing IV
    @pytest.mark.xfail
    def test_replace_call_if_needed(self):
        """Ensures that replace_call_if_needed method of CustomVisitor works as expected"""
        assert False, "TODO: Implement"

class TestUsageImportTypes(TestWrapper):
    """Class for test usage for several methods of import in mezcla_to_standard"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)

    ## TODO: Add a helper function
    # def helper_import(self, code_combinations, explicit_run = True)

    ## NOTE: When testing code, DO NOT follow the code in this format
    ## NOTE: Instead, DO NOT apply any indentations on code
    # code_direct_import = '''
    #     from mezcla.debug import trace
    #     trace(1, "error")
    #     '''

    @pytest.mark.xfail
    def test_import_types(self):
        """Usage test for conversion of various mezcla import styles to standard import (VANILLA: no comments or multiline imports)"""

        # 4 Styles of import: Direct, using alias, from ... import, import
        code_direct_import = '''
from mezcla.debug import trace
trace(1, "error")
'''
        
        code_alias_import = '''
from mezcla import debug as dbg
dbg.trace(1, "error")
'''
        
        code_from_import = '''
from mezcla import debug
debug.trace(1, "error")
'''
        
        code_import = '''
import mezcla
mezcla.debug.trace(1, "error")
'''

        expected_output = '''
import logging
logging.error("error")
'''

        # Storing all possible code combinations
        code_combinations = [code_direct_import, code_alias_import, code_from_import, code_import]
        
        # Writing code to input file/function and transforming it for assertion
        for code in code_combinations:
            
            ## ATTEMPT 1: Did not work as expected
            # temp_file = gh.create_temp_file(contents=code)
            # command = f"python3 mezcla/mezcla_to_standard.py --to_standard {temp_file}"
            # result = gh.run(command)
            
            ## ATTEMPT 2: Did not work either
            result = THE_MODULE.transform(THE_MODULE.ToStandard(), code)
            self.assertEqual(result.strip(), expected_output.strip())
            

    @pytest.mark.xfail
    def test_import_with_comments(self):
        """Usage test for conversion of various mezcla import styles to standard import (WITH_COMMENTS: comments)"""
        
        code_with_comment = '''
# This is a comment
from mezcla.debug import trace
trace(1, "error")
'''
        
        expected_output = '''
# This is a comment
import logging

logging.error("error")
'''

        code_combinations = [code_with_comment]

        for code in code_combinations:
            # Refer from test_import_types
            self.assertEqual(code, None, "TODO: Implement")
    
    @pytest.mark.xfail
    def test_import_multiple(self):
        """Usage test for conversion of various mezcla import styles to standard import (MULTIPLE: import of more than one module, class, function)"""
        
        code_multiple_imports = '''
        from mezcla.debug import trace, log
        trace(1, "error")
        log("info", "message")'''
        
        expected_output = '''
        import logging
        
        logging.error("error")
        logging.info("message")
        '''

        code_combinations = [code_multiple_imports]

        for code in code_combinations:
            # Refer from test_import_types
            self.assertEqual(code, None, "TODO: Implement")

    def test_import_no_transformation(self):
        """Usage test for conversion of various mezcla import styles to standard import (NO_TRANSFORMATION: Input code written with standard module)"""

        code_no_transformation = '''
import logging
logging.error("error")'''

        expected_output = '''
import logging
logging.error("error")'''

        code_combinations = [code_no_transformation]

        for code in code_combinations:
            # Refer from test_import_types
            result = THE_MODULE.transform(THE_MODULE.ToStandard(), code)
            self.assertEqual(result.strip(), expected_output.strip())


class TestUsage(TestWrapper):
    """Class for several test usages for mezcla_to_standard"""
    script_module = TestWrapper.get_testing_module_name(__file__, THE_MODULE)

    def test_unsupported_function_to_standard(self):
        """Test for conversion of an unsupported function during mezcla to standard conversion (commented as #Warning not supported)"""
        
        input_code = """
from mezcla import glue_helpers as gh
gh.run("python3 --version")
"""

        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_module=to_standard, code=input_code)
        unsupported_message = '# WARNING not supported: gh.run("python3 --version")'
        assert result is not None
        assert unsupported_message in result

    @pytest.mark.xfail
    def test_unsupported_function_to_mezcla(self):
        """Test for conversion of an unsupported function during standard to mezcla conversion (commented as #Warning not supported)"""
        ## TODO: Wait until the fix: AttributeError: 'list' object has no attribute '__module__'. Did you mean: '__mul__'?
        input_code = """
import os
os.getenv("HOME")
"""
        to_mezcla = THE_MODULE.ToMezcla()
        result = THE_MODULE.transform(to_module=to_mezcla, code=input_code)
        unsupported_message = '# WARNING not supported: gh.run("python3 --version")'
        assert result is not None
        assert unsupported_message in result

    def test_conversion_mezcla_to_standard(self):
        """Test the conversion from mezcla to standard calls"""
        
        ## NOTE: Old code of test_conversion_mezcla_to_standard moved to test_run_supported_and_unsupported_function
        ## NOTE: This was done to test both supported and unsupported functions
        # Standard code uses POSIX instead of os (as of 2024-06-10)
        input_code = """
from mezcla import glue_helpers as gh
gh.delete_file("/tmp/fubar.list")
gh.rename_file("/tmp/fubar.list1", "/tmp/fubar.list2")
gh.form_path("/tmp", "fubar")
        """
        
        # Standard code consistes of glue helpers commands as well (as of 2024-06-10)
        expected_output_code = """
import os
from mezcla import glue_helpers as gh
os.remove("/tmp/fubar.list")
os.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
os.path.join("/tmp", "fubar")
        """
        
        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, input_code)
        self.assertEqual(result.strip(), expected_output_code.strip())    
    
    # NOTE: Does not work as intended (output code is similar to standard code)
    ## ERROR: FAILED mezcla/tests/test_mezcla_to_standard.py::TestUsage::test_conversion_standard_to_mezcla - AttributeError: 'list' object has no attribute '__module__'. Did you mean: '__mul__'?
    @pytest.mark.xfail
    def test_conversion_standard_to_mezcla(self):
        """Test the conversion from standard to mezcla calls"""

        input_code = """
import os
os.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
os.remove("/tmp/fubar.list")
        """
        
        expected_output_code = """
import os
from mezcla import glue_helpers as gh
gh.rename_file("/tmp/fubar.list1", "/tmp/fubar.list2")
gh.delete_file("/tmp/fubar.list")
        """

        to_mezcla = THE_MODULE.ToMezcla()
        result = THE_MODULE.transform(to_mezcla, input_code)
        self.assertEqual(result.strip(), expected_output_code.strip())

    
    # TODO: Fix and implement for command-line like runs  
    @pytest.mark.xfail
    def test_run_from_command_to_mezcla(self):
        """Test the working of the script through command line/stdio (--to_standard option)"""
        
        input_code = """
import os
os.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
os.remove("/tmp/fubar.list")
        """
        expected_code = """
import os
from mezcla import glue_helpers as gh
gh.rename_file("/tmp/fubar.list1", "/tmp/fubar.list2")
gh.delete_file("/tmp/fubar.list")
"""
        input_file = gh.create_temp_file(contents=input_code)
        command = f"python3 mezcla/mezcla_to_standard.py --to_mezcla {input_file}"
        result = gh.run(command)
        self.assertEqual(result.strip(), expected_code.strip())
    
    
    def test_run_from_command_empty_file(self):
        """Test the working of the script through command line when input file is empty"""
        input_code = ""
        input_file = gh.create_temp_file(contents=input_code)
        command = f"python3 mezcla/mezcla_to_standard.py --to_standard {input_file}"
        result = gh.run(command)
        self.assertEqual(result.strip(), "")

    
    def test_run_from_command_syntax_error(self):
        """Test the working of the script through command line when input file has syntax error"""
        
        input_code = """
from mezcla import glue_helpers as gh
gh.write_file("/tmp/fubar.list", "fubar.list")
gh.copy_file("/tmp/fubar.list", "/tmp/fubar.list1
        """
        ## TODO: Write an helper functions for all functions in TestUsage
        input_file = gh.create_temp_file(contents=input_code)
        command = f"python3 mezcla/mezcla_to_standard.py --to_standard {input_file}"
        result = gh.run(command)
        self.assertIn("Traceback (most recent call last):\n", result.strip())
        self.assertIn("libcst._exceptions.ParserSyntaxError: Syntax Error @ 1:1.", result.strip())
        self.assertIn("tokenizer error: unterminated string literal", result.strip())

    def test_run_supported_and_unsupported_function(self):
        """Test the conversion with both unspported and supported functions included"""
        
        ## PREVIOUSLY: test_conversion_mezcla_to_standard
        # Standard code uses POSIX instead of os (as of 2024-06-10)
        input_code = """
from mezcla import glue_helpers as gh
gh.write_file("/tmp/fubar.list", "fubar.list")
gh.copy_file("/tmp/fubar.list", "/tmp/fubar.list1")
gh.delete_file("/tmp/fubar.list")
gh.rename_file("/tmp/fubar.list1", "/tmp/fubar.list2")
gh.form_path("/tmp", "fubar")
        """
        
        # Standard code consistes of glue helpers commands as well (as of 2024-06-10)
        expected_output_code = """
import os
from mezcla import glue_helpers as gh
# WARNING not supported: gh.write_file("/tmp/fubar.list", "fubar.list")
# WARNING not supported: gh.copy_file("/tmp/fubar.list", "/tmp/fubar.list1")
os.remove("/tmp/fubar.list")
os.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
os.path.join("/tmp", "fubar")
        """
        
        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, input_code)
        self.assertEqual(result.strip(), expected_output_code.strip()) 
        
    def test_run_from_command_to_standard(self):
        """Test the working of the script through command line/stdio (--to_standard option)"""
        
        input_code = """
from mezcla import glue_helpers as gh
gh.rename_file("/tmp/fubar.list1", "/tmp/fubar.list2")
gh.delete_file("/tmp/fubar.list")
"""
        expected_code = """
import os
from mezcla import glue_helpers as gh
os.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
os.remove("/tmp/fubar.list")
"""

        input_file = gh.create_temp_file(contents=input_code)
        command = f"python3 mezcla/mezcla_to_standard.py --to_standard {input_file}"
        result = gh.run(command)
        self.assertEqual(result.strip(), expected_code.strip())


    @pytest.mark.xfail
    def test_conversion_to_mezcla_round_robin(self):
        """Test conversion of script in round robin (e.g. standard -> mezcla -> standard)"""
        
        ## NOTE: This test passed, however, result_temp is same as result (i.e. to_mezcla not working as expected)
        ## UPDATE: This test has failed as output is similar to mezcla translation

        ## OLD: This section used POSIX instead of OS 
        ## This code returns AttributeError: 'list' object has no attribute '__module__'. Did you mean: '__mul__'?

#       std_code = """
# import posix
# posix.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
# posix.remove("/tmp/fubar.list")
#        """
        
        ## This code returns TypeError: /usr/lib/python3.10/inspect.py:1287: TypeError
        std_code = """
import os
os.rename("/tmp/fubar.list1", "/tmp/fubar.list2")
os.remove("/tmp/fubar.list")
"""
        
        to_mezcla = THE_MODULE.ToMezcla()
        result_temp = THE_MODULE.transform(to_mezcla, std_code)
        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, result_temp)
        self.assertEqual(result, std_code)
    
    ## NOTE: This test failed due to ToMezcla class not working as expected
    @pytest.mark.xfail
    def test_conversion_to_standard_round_robin(self):
        """Test conversion of script in round robin (e.g. mezcla -> standard -> mezcla)"""
        
        mezcla_code = """
from mezcla import glue_helpers as gh
gh.rename_file("/tmp/fubar.list1", "/tmp/fubar.list2")
gh.delete_file("/tmp/fubar.list")
        """
        
        to_mezcla = THE_MODULE.ToMezcla()
        to_standard = THE_MODULE.ToStandard()
        result_temp = THE_MODULE.transform(to_standard, mezcla_code)
        result = THE_MODULE.transform(to_mezcla, result_temp)
        # DEBUG: print(result, "="*20, result_temp)
        self.assertEqual(result, mezcla_code)

    def test_conversion_nested_functions(self):
        """Test conversion of script containing nested functions"""
        ## TODO: Include tests for standard to mezcla
        ## NOTE: Add support for nested functions

        input_code = """
from mezcla import glue_helpers as gh
gh.delete_file(gh.form_path("/var", "log", "application", "old_app.log"))
"""
        expected_code = """
import os
from mezcla import glue_helpers as gh
os.remove(os.path.join("/var", "log", "application", "old_app.log"))
"""
        actual_output = """
import os
from mezcla import glue_helpers as gh
os.remove(gh.form_path("/var", "log", "application", "old_app.log"))
"""
        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, input_code)
        assert result == actual_output
    
    
    def test_conversion_assignment_to_var(self):
        """Test conversion of script for assignment of function to a variable"""

        input_code = """
from mezcla import glue_helpers as gh
path = gh.form_path("/var", "log", "application", "app.log")
"""
        expected_code = """
import os
from mezcla import glue_helpers as gh
path = os.path.join("/var", "log", "application", "app.log")
"""

        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, input_code)
        assert result == expected_code

    def test_conversion_multiple_imports(self):
        """Test conversion of script for multiple imports"""
        
        input_code = """
from mezcla import glue_helpers as gh
from mezcla import debug
from os import path
gh.write_file("/tmp/test.txt", "test content")
gh.copy_file("/tmp/test.txt", "/tmp/test_copy.txt")
debug.trace("Copy created", level=3)
gh.delete_file("/tmp/test.txt")
if path.exists("/tmp/test_copy.txt"):
    debug.trace("File exists", level=2)
    """
        
        actual_code = """
import os
from mezcla import glue_helpers as gh
from mezcla import debug
from os import path
# WARNING not supported: gh.write_file("/tmp/test.txt", "test content")
# WARNING not supported: gh.copy_file("/tmp/test.txt", "/tmp/test_copy.txt")
# WARNING not supported: debug.trace("Copy created", level=3)
os.remove("/tmp/test.txt")
if path.exists("/tmp/test_copy.txt"):
    # WARNING not supported: debug.trace("File exists", level=2)
"""

        expected_code = """
from mezcla import glue_helpers as gh
from mezcla import debug
from os import path
import os
import logging
# WARNING not supported: gh.write_file("/tmp/test.txt", "test content")
# WARNING not supported: gh.copy_file("/tmp/test.txt", "/tmp/test_copy.txt")
# WARNING not supported: debug.trace("Copy created", level=3)
os.remove("/tmp/test.txt")
if path.exists("/tmp/test_copy.txt"):
    logging.warning("File exists", level=2)
    """
        
        ## NOTE: Support for logging (debug in case of mezcla) not present
        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, input_code)
        assert result.strip() == actual_code.strip()

    def test_conversion_conditional_statement(self):
        """Test conversion of script when conditional statements are used"""
        
        input_code = """
from mezcla import glue_helpers as gh
if gh.form_path("/home", "user") == "/home/user":
    gh.rename_file("/home/user/file1.txt", "/home/user/file2.txt")
    gh.delete_file("/home/user/file1.txt")
else:
    gh.write_file("/home/user/file2.txt", "content")
    pass
"""
        
        expected_code = """
import os
from mezcla import glue_helpers as gh
if os.path.join("/home", "user") == "/home/user":
    os.rename("/home/user/file1.txt", "/home/user/file2.txt")
    os.remove("/home/user/file1.txt")
else:
    # WARNING not supported: gh.write_file("/home/user/file2.txt", "content")
    pass
"""

        to_standard = THE_MODULE.ToStandard()
        result = THE_MODULE.transform(to_standard, input_code)
        assert result.strip() == expected_code.strip()


if __name__ == '__main__':
    debug.trace_current_context()
    pytest.main([__file__])