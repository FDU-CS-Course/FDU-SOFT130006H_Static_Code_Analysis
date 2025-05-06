"""
Tests for the context_builder module.
"""

import os
import tempfile
import unittest
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
            "test.cpp",
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
            "test.cpp",
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
            "test.cpp",
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
                "test.cpp",
                line_number=5,
                strategy="invalid_strategy"
            )
    
    def test_build_context_custom_lines(self):
        """Test building context with custom number of lines."""
        context = self.context_builder.build_context(
            "test.cpp",
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
            "test.cpp",
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
            "test.cpp",
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
                "long.cpp",
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

if __name__ == "__main__":
    unittest.main() 