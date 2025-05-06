"""
Utility functions for file operations and path validation.

This module provides functions for safe file operations and path validation,
ensuring that file access is restricted to the project directory.
"""

import os
from typing import Optional

def is_path_safe(file_path: str, project_root: str) -> bool:
    """
    Validate if a file path is safe to access within the project root.
    
    Args:
        file_path (str): The file path to validate.
        project_root (str): The absolute path to the project root directory.
    
    Returns:
        bool: True if the path is safe, False otherwise.
    
    Note:
        A path is considered safe if:
        1. It exists
        2. It is within the project root directory
        3. It is not a directory
        4. It is not a symbolic link
    """
    try:
        # Convert to absolute paths
        abs_file_path = os.path.abspath(file_path)
        abs_project_root = os.path.abspath(project_root)
        
        # Check if path exists
        if not os.path.exists(abs_file_path):
            return False
            
        # Check if path is within project root
        if not abs_file_path.startswith(abs_project_root):
            return False
            
        # Check if path is a file (not a directory)
        if not os.path.isfile(abs_file_path):
            return False
            
        # Check if path is a symbolic link
        if os.path.islink(abs_file_path):
            return False
            
        return True
        
    except Exception:
        # If any error occurs during validation, consider the path unsafe
        return False

def read_file_lines(file_path: str, start_line: int, end_line: int) -> Optional[str]:
    """
    Read specific lines from a file.
    
    Args:
        file_path (str): Path to the file to read.
        start_line (int): First line to read (1-based).
        end_line (int): Last line to read (inclusive).
    
    Returns:
        Optional[str]: The content of the specified lines, or None if an error occurs.
    
    Note:
        - Line numbers are 1-based (first line is 1)
        - If start_line is less than 1, it will be set to 1
        - If end_line is greater than the file length, it will be set to the last line
        - Empty lines are preserved
    """
    try:
        # Validate line numbers
        start_line = max(1, start_line)
        end_line = max(start_line, end_line)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read all lines
            lines = f.readlines()
            
            # Adjust end_line if it exceeds file length
            end_line = min(end_line, len(lines))
            
            # Extract requested lines
            selected_lines = lines[start_line - 1:end_line]
            
            # Join lines and remove trailing newline
            return ''.join(selected_lines).rstrip('\n')
            
    except Exception as e:
        # Log the error (in a real implementation, use proper logging)
        print(f"Error reading file lines: {str(e)}")
        return None

def get_file_extension(file_path: str) -> Optional[str]:
    """
    Get the extension of a file.
    
    Args:
        file_path (str): Path to the file.
    
    Returns:
        Optional[str]: The file extension (without the dot), or None if the file has no extension.
    """
    try:
        _, ext = os.path.splitext(file_path)
        return ext[1:] if ext else None
    except Exception:
        return None

def is_source_file(file_path: str) -> bool:
    """
    Check if a file is a source code file.
    
    Args:
        file_path (str): Path to the file to check.
    
    Returns:
        bool: True if the file is a source code file, False otherwise.
    
    Note:
        Currently supports common C++ source file extensions:
        - .cpp, .cc, .cxx
        - .hpp, .hh, .hxx
        - .h
    """
    ext = get_file_extension(file_path)
    if not ext:
        return False
        
    return ext.lower() in {
        'cpp', 'cc', 'cxx',  # C++ source files
        'hpp', 'hh', 'hxx',  # C++ header files
        'h'                   # C header files
    } 