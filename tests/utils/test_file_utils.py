"""
Tests for the file_utils module.
"""

import os
import tempfile
import unittest
from utils.file_utils import (
    is_path_safe,
    read_file_lines,
    get_file_extension,
    is_source_file
)

class TestFileUtils(unittest.TestCase):
    """Test cases for file utility functions."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create a test file
        self.test_file_content = """Line 1
Line 2
Line 3
Line 4
Line 5"""
        
        self.test_file_path = os.path.join(self.test_dir, "test.cpp")
        with open(self.test_file_path, "w") as f:
            f.write(self.test_file_content)
            
        # Create a symbolic link
        self.symlink_path = os.path.join(self.test_dir, "symlink.cpp")
        os.symlink(self.test_file_path, self.symlink_path)
        
        # Create a subdirectory
        self.subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.subdir)
        
        # Create a file in subdirectory
        self.subdir_file = os.path.join(self.subdir, "test.cpp")
        with open(self.subdir_file, "w") as f:
            f.write(self.test_file_content)
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove symbolic link
        if os.path.exists(self.symlink_path):
            os.remove(self.symlink_path)
            
        # Remove files
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        if os.path.exists(self.subdir_file):
            os.remove(self.subdir_file)
            
        # Remove directories
        if os.path.exists(self.subdir):
            os.rmdir(self.subdir)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)
    
    def test_is_path_safe_valid_file(self):
        """Test is_path_safe with a valid file path."""
        self.assertTrue(is_path_safe(self.test_file_path, self.test_dir))
    
    def test_is_path_safe_outside_root(self):
        """Test is_path_safe with a path outside project root."""
        outside_path = os.path.abspath("/etc/passwd")
        self.assertFalse(is_path_safe(outside_path, self.test_dir))
    
    def test_is_path_safe_nonexistent_file(self):
        """Test is_path_safe with a nonexistent file."""
        nonexistent_path = os.path.join(self.test_dir, "nonexistent.cpp")
        self.assertFalse(is_path_safe(nonexistent_path, self.test_dir))
    
    def test_is_path_safe_directory(self):
        """Test is_path_safe with a directory path."""
        self.assertFalse(is_path_safe(self.subdir, self.test_dir))
    
    def test_is_path_safe_symlink(self):
        """Test is_path_safe with a symbolic link."""
        self.assertFalse(is_path_safe(self.symlink_path, self.test_dir))
    
    def test_read_file_lines_valid_range(self):
        """Test read_file_lines with a valid line range."""
        content = read_file_lines(self.test_file_path, 2, 4)
        expected = """Line 2
Line 3
Line 4"""
        self.assertEqual(content, expected)
    
    def test_read_file_lines_start_before_1(self):
        """Test read_file_lines with start_line < 1."""
        content = read_file_lines(self.test_file_path, 0, 3)
        expected = """Line 1
Line 2
Line 3"""
        self.assertEqual(content, expected)
    
    def test_read_file_lines_end_after_file(self):
        """Test read_file_lines with end_line > file length."""
        content = read_file_lines(self.test_file_path, 4, 10)
        expected = """Line 4
Line 5"""
        self.assertEqual(content, expected)
    
    def test_read_file_lines_nonexistent_file(self):
        """Test read_file_lines with a nonexistent file."""
        content = read_file_lines("nonexistent.cpp", 1, 5)
        self.assertIsNone(content)
    
    def test_get_file_extension_with_extension(self):
        """Test get_file_extension with a file that has an extension."""
        self.assertEqual(get_file_extension(self.test_file_path), "cpp")
    
    def test_get_file_extension_without_extension(self):
        """Test get_file_extension with a file that has no extension."""
        no_ext_path = os.path.join(self.test_dir, "test")
        self.assertIsNone(get_file_extension(no_ext_path))
    
    def test_get_file_extension_invalid_path(self):
        """Test get_file_extension with an invalid path."""
        self.assertIsNone(get_file_extension(""))
    
    def test_is_source_file_cpp(self):
        """Test is_source_file with a .cpp file."""
        self.assertTrue(is_source_file(self.test_file_path))
    
    def test_is_source_file_hpp(self):
        """Test is_source_file with a .hpp file."""
        hpp_path = os.path.join(self.test_dir, "test.hpp")
        self.assertTrue(is_source_file(hpp_path))
    
    def test_is_source_file_h(self):
        """Test is_source_file with a .h file."""
        h_path = os.path.join(self.test_dir, "test.h")
        self.assertTrue(is_source_file(h_path))
    
    def test_is_source_file_non_source(self):
        """Test is_source_file with a non-source file."""
        txt_path = os.path.join(self.test_dir, "test.txt")
        self.assertFalse(is_source_file(txt_path))
    
    def test_is_source_file_no_extension(self):
        """Test is_source_file with a file that has no extension."""
        no_ext_path = os.path.join(self.test_dir, "test")
        self.assertFalse(is_source_file(no_ext_path))

if __name__ == "__main__":
    unittest.main() 