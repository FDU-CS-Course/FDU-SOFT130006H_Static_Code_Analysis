"""
Tests for the context_builder module.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from core.context_builder import ContextBuilder

class TestContextBuilder(unittest.TestCase):
    """Test cases for ContextBuilder class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create a test file with known content
        self.test_file_content = """Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10"""
        
        self.test_file_path = os.path.join(self.test_dir, "test.cpp")
        with open(self.test_file_path, "w") as f:
            f.write(self.test_file_content)
        
        # Initialize ContextBuilder with test directory as project root
        self.context_builder = ContextBuilder(self.test_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove test file and directory
        os.remove(self.test_file_path)
        os.rmdir(self.test_dir)
    
    def test_build_context_fixed_lines(self):
        """Test building context with fixed_lines strategy."""
        # Test middle of file
        context = self.context_builder.build_context(
            self.test_file_path,
            line_number=5,
            strategy="fixed_lines",
            lines_before=2,
            lines_after=2
        )
        
        expected = """3: Line 3
4: Line 4
5: Line 5
6: Line 6
7: Line 7"""
        
        self.assertEqual(context, expected)
    
    def test_build_context_fixed_lines_start_of_file(self):
        """Test building context near start of file."""
        context = self.context_builder.build_context(
            self.test_file_path,
            line_number=2,
            strategy="fixed_lines",
            lines_before=3,
            lines_after=2
        )
        
        expected = """1: Line 1
2: Line 2
3: Line 3
4: Line 4"""
        
        self.assertEqual(context, expected)
    
    def test_build_context_fixed_lines_end_of_file(self):
        """Test building context near end of file."""
        context = self.context_builder.build_context(
            self.test_file_path,
            line_number=9,
            strategy="fixed_lines",
            lines_before=2,
            lines_after=3
        )
        
        expected = """7: Line 7
8: Line 8
9: Line 9
10: Line 10"""
        
        self.assertEqual(context, expected)
    
    def test_build_context_unsafe_path(self):
        """Test building context with unsafe file path."""
        context = self.context_builder.build_context(
            "../../../etc/passwd",  # Attempt directory traversal
            line_number=1,
            strategy="fixed_lines"
        )
        
        self.assertIsNone(context)
    
    def test_build_context_nonexistent_file(self):
        """Test building context with nonexistent file."""
        context = self.context_builder.build_context(
            "nonexistent.cpp",
            line_number=1,
            strategy="fixed_lines"
        )
        
        self.assertIsNone(context)
    
    def test_build_context_invalid_strategy(self):
        """Test building context with invalid strategy."""
        with self.assertRaises(ValueError):
            self.context_builder.build_context(
                self.test_file_path,
                line_number=5,
                strategy="invalid_strategy"
            )
    
    def test_build_context_custom_lines(self):
        """Test building context with custom number of lines."""
        context = self.context_builder.build_context(
            self.test_file_path,
            line_number=5,
            strategy="fixed_lines",
            lines_before=1,
            lines_after=1
        )
        
        expected = """4: Line 4
5: Line 5
6: Line 6"""
        
        self.assertEqual(context, expected)
    
    def test_build_context_file_scope(self):
        """Test building context with file_scope strategy."""
        context = self.context_builder.build_context(
            self.test_file_path,
            line_number=5,
            strategy="file_scope"
        )
        
        expected = """1: Line 1
2: Line 2
3: Line 3
4: Line 4
5: >>> Line 5 <<<
6: Line 6
7: Line 7
8: Line 8
9: Line 9
10: Line 10"""
        
        self.assertEqual(context, expected)
    
    def test_build_context_file_scope_no_highlight(self):
        """Test building context with file_scope strategy without highlighting."""
        context = self.context_builder.build_context(
            self.test_file_path,
            line_number=5,
            strategy="file_scope",
            highlight_issue_line=False
        )
        
        expected = """1: Line 1
2: Line 2
3: Line 3
4: Line 4
5: Line 5
6: Line 6
7: Line 7
8: Line 8
9: Line 9
10: Line 10"""
        
        self.assertEqual(context, expected)
    
    def test_build_context_file_scope_exceeds_max_lines(self):
        """Test building context with file_scope when file exceeds max lines."""
        # Create a test function for this specific test
        long_content = "\n".join([f"Line {i}" for i in range(1, 21)])
        long_file_path = os.path.join(self.test_dir, "long.cpp")
        with open(long_file_path, "w") as f:
            f.write(long_content)
            
        try:
            # Test with max_lines less than file length
            context = self.context_builder.build_context(
                long_file_path,
                line_number=10,
                strategy="file_scope",
                max_lines=15
            )
            
            # Should fallback to a different strategy
            self.assertIsNotNone(context)
            self.assertLess(len(context.split('\n')), 21)  # Should be fewer lines than the whole file
        finally:
            # Clean up
            os.remove(long_file_path)

    def test_build_file_with_includes_context(self):
        """Test building context with file_with_includes strategy."""
        # Create main file with includes
        main_file_content = """#include <iostream>
#include "myheader.h"
#include <vector>
#include "utils/helper.hpp"

int main() {
    // Some code here
    return 0;
}"""
        
        main_file_path = os.path.join(self.test_dir, "main.cpp")
        with open(main_file_path, "w") as f:
            f.write(main_file_content)
        
        # Create header file
        header_content = """#pragma once
// myheader.h
void helper_function();
"""
        
        # Create utils directory
        utils_dir = os.path.join(self.test_dir, "utils")
        os.makedirs(utils_dir, exist_ok=True)
        
        # Create header files
        header_path = os.path.join(self.test_dir, "myheader.h")
        with open(header_path, "w") as f:
            f.write(header_content)
            
        helper_content = """// helper.hpp
#include <string>

std::string format_string(const std::string& input);
"""
        helper_path = os.path.join(utils_dir, "helper.hpp")
        with open(helper_path, "w") as f:
            f.write(helper_content)
            
        try:
            context = self.context_builder.build_context(
                main_file_path,
                line_number=6,
                strategy="file_with_includes"
            )
            
            # Check that context is not None
            self.assertIsNotNone(context)
            
            # Verify content contains both main file and included headers 
            # but excludes std library headers
            self.assertIn("int main()", context)
            self.assertIn("myheader.h", context)
            self.assertIn("helper.hpp", context)
            # Should not include std headers
            self.assertNotIn("namespace std", context)
        finally:
            # Clean up
            os.remove(main_file_path)
            os.remove(header_path)
            os.remove(helper_path)
            os.rmdir(utils_dir)
            
    def test_find_includes(self):
        """Test the _find_includes method."""
        content = """#include <iostream>
#include "myheader.h"
#include <vector>
#include "utils/helper.hpp"
"""
        
        includes = self.context_builder._find_includes(content)
        
        # Should only contain project headers, not std library ones
        self.assertEqual(len(includes), 2)
        self.assertIn("myheader.h", includes)
        self.assertIn("utils/helper.hpp", includes)
        self.assertNotIn("iostream", includes)
        self.assertNotIn("vector", includes)
        
    def test_build_file_cache(self):
        """Test the _build_file_cache method."""
        # Create some test files
        cpp_file = os.path.join(self.test_dir, "test.cpp")
        header_file = os.path.join(self.test_dir, "test.h")
        other_file = os.path.join(self.test_dir, "test.txt")
        
        # Create test.h file
        with open(header_file, "w") as f:
            f.write("// Test header")
            
        # Create test.txt file (shouldn't be included in cache)
        with open(other_file, "w") as f:
            f.write("This is not a code file")
            
        try:
            # Build the cache
            self.context_builder._build_file_cache()
            
            # Check if cache contains the right files
            rel_cpp_path = os.path.relpath(self.test_file_path, self.test_dir)
            rel_header_path = os.path.relpath(header_file, self.test_dir)
            rel_other_path = os.path.relpath(other_file, self.test_dir)
            
            self.assertIn(rel_cpp_path, self.context_builder._file_cache)
            self.assertIn(rel_header_path, self.context_builder._file_cache)
            self.assertNotIn(rel_other_path, self.context_builder._file_cache)  # Should not include non-code files
        finally:
            # Clean up
            os.remove(header_file)
            os.remove(other_file)

if __name__ == "__main__":
    unittest.main() 