# File Utilities Module

## Overview

The File Utilities module provides a set of functions for safe file operations and path validation. It ensures that file access is restricted to the project directory and handles various file operations securely.

## Features

- **Path Validation**: Ensures file paths are safe and within the project directory
- **File Reading**: Safely reads specific lines from files
- **File Type Detection**: Identifies source code files and file extensions
- **Security**: Prevents directory traversal and handles symbolic links
- **Error Handling**: Gracefully handles file access errors

## Functions

### is_path_safe

```python
def is_path_safe(file_path: str, project_root: str) -> bool
```

Validates if a file path is safe to access within the project root.

**Parameters:**
- `file_path` (str): The file path to validate
- `project_root` (str): The absolute path to the project root directory

**Returns:**
- `bool`: True if the path is safe, False otherwise

**Safety Checks:**
1. Path exists
2. Path is within project root
3. Path is a file (not a directory)
4. Path is not a symbolic link

### read_file_lines

```python
def read_file_lines(file_path: str, start_line: int, end_line: int) -> Optional[str]
```

Reads specific lines from a file.

**Parameters:**
- `file_path` (str): Path to the file to read
- `start_line` (int): First line to read (1-based)
- `end_line` (int): Last line to read (inclusive)

**Returns:**
- `Optional[str]`: The content of the specified lines, or None if an error occurs

**Features:**
- Line numbers are 1-based
- Automatically adjusts invalid line numbers
- Preserves empty lines
- Handles file access errors gracefully

### get_file_extension

```python
def get_file_extension(file_path: str) -> Optional[str]
```

Gets the extension of a file.

**Parameters:**
- `file_path` (str): Path to the file

**Returns:**
- `Optional[str]`: The file extension (without the dot), or None if the file has no extension

### is_source_file

```python
def is_source_file(file_path: str) -> bool
```

Checks if a file is a source code file.

**Parameters:**
- `file_path` (str): Path to the file to check

**Returns:**
- `bool`: True if the file is a source code file, False otherwise

**Supported Extensions:**
- C++ source files: `.cpp`, `.cc`, `.cxx`
- C++ header files: `.hpp`, `.hh`, `.hxx`
- C header files: `.h`

## Security Considerations

1. **Path Validation**
   - All file paths are validated against the project root
   - Directory traversal attempts are blocked
   - Symbolic links are not allowed

2. **File Access**
   - Files are read in text mode with UTF-8 encoding
   - File access errors are handled gracefully
   - No write operations are performed

3. **Error Handling**
   - All functions handle exceptions internally
   - Invalid paths return None or False
   - No sensitive information is exposed in error messages

## Usage Examples

```python
from utils.file_utils import is_path_safe, read_file_lines

# Check if a path is safe
if is_path_safe("src/main.cpp", "/path/to/project"):
    # Read lines from the file
    content = read_file_lines("src/main.cpp", 10, 20)
    if content:
        print(content)
```

## Testing

The module includes comprehensive test coverage:
- Path validation
- File reading
- Extension detection
- Source file detection
- Error handling
- Edge cases

Run tests using:
```bash
python -m unittest tests/utils/test_file_utils.py
```

## Dependencies

- Python standard library: `os` for path manipulation and file operations
- No external dependencies required 