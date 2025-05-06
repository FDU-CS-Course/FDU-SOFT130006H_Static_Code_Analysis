# Context Builder Module

## Overview

The Context Builder module is responsible for extracting relevant code snippets from source files to provide context for LLM analysis of cppcheck issues. It implements various strategies for context extraction, with the primary goal of providing meaningful code context around identified issues.

## Features

- **Multiple Context Strategies**: Currently supports the `fixed_lines` strategy, with extensibility for additional strategies.
- **Security**: Implements path validation to prevent directory traversal attacks.
- **Line Numbering**: Automatically adds line numbers to the extracted context for better readability.
- **Error Handling**: Gracefully handles file access errors and invalid paths.

## Usage

```python
from core.context_builder import ContextBuilder

# Initialize with project root
builder = ContextBuilder(project_root="/path/to/project")

# Build context using fixed_lines strategy
context = builder.build_context(
    file_path="src/main.cpp",
    line_number=42,
    strategy="fixed_lines",
    lines_before=5,
    lines_after=5
)
```

## Strategies

### Fixed Lines Strategy

The `fixed_lines` strategy extracts a fixed number of lines before and after the issue line.

**Parameters:**
- `lines_before` (int): Number of lines to include before the issue line (default: 5)
- `lines_after` (int): Number of lines to include after the issue line (default: 5)

**Example Output:**
```
3: void someFunction() {
4:     int x = 42;
5:     // Issue line
6:     return x;
7: }
```

## Security Considerations

- All file paths are validated against the project root directory
- Directory traversal attempts are blocked
- File access errors are handled gracefully

## Error Handling

The module handles various error conditions:
- Invalid file paths
- Directory traversal attempts
- File access errors
- Invalid strategy selection

## Future Enhancements

1. **Function Scope Strategy**: Extract the entire function containing the issue
2. **AST-based Context**: Use Abstract Syntax Tree analysis for more precise context extraction
3. **Class Scope Strategy**: Extract the entire class definition when the issue is within a class
4. **Import Context**: Include relevant import statements for better context

## Dependencies

- `utils.file_utils`: For path validation and file reading operations
- Python standard library: `os` for path manipulation

## Testing

The module includes comprehensive test coverage:
- Basic context extraction
- Edge cases (start/end of file)
- Security validation
- Error handling
- Custom line count configuration

Run tests using:
```bash
python -m unittest tests/core/test_context_builder.py
``` 