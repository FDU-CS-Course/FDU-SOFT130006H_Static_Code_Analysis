"""
Module for building code context around issues for LLM analysis.

This module provides functionality to extract relevant code snippets from source files
based on different strategies (e.g., fixed number of lines, function scope).
"""

import os
from typing import Optional, Dict, Any
from utils.file_utils import is_path_safe, read_file_lines

class ContextBuilder:
    """Class for building code context around issues."""
    
    def __init__(self, project_root: str):
        """
        Initialize the ContextBuilder.
        
        Args:
            project_root (str): Absolute path to the project root directory.
        """
        self.project_root = os.path.abspath(project_root)
    
    def build_context(
        self,
        file_path: str,
        line_number: int,
        strategy: str = "fixed_lines",
        **kwargs: Dict[str, Any]
    ) -> Optional[str]:
        """
        Build code context around the specified line number using the given strategy.
        
        Args:
            file_path (str): Relative path to the source file from project root.
            line_number (int): Line number where the issue was found.
            strategy (str): Strategy to use for building context. Defaults to "fixed_lines".
            **kwargs: Additional strategy-specific parameters.
        
        Returns:
            Optional[str]: The extracted code context, or None if the file path is unsafe
                         or the file cannot be read.
        
        Raises:
            ValueError: If the strategy is not supported.
        """
        # Construct absolute path and validate
        abs_file_path = os.path.join(self.project_root, file_path)
        if not is_path_safe(abs_file_path, self.project_root):
            return None
            
        # Select strategy
        if strategy == "fixed_lines":
            return self._build_fixed_lines_context(abs_file_path, line_number, **kwargs)
        else:
            raise ValueError(f"Unsupported context building strategy: {strategy}")
    
    def _build_fixed_lines_context(
        self,
        file_path: str,
        line_number: int,
        lines_before: int = 5,
        lines_after: int = 5
    ) -> Optional[str]:
        """
        Build context by extracting a fixed number of lines before and after the issue.
        
        Args:
            file_path (str): Absolute path to the source file.
            line_number (int): Line number where the issue was found.
            lines_before (int): Number of lines to include before the issue. Defaults to 5.
            lines_after (int): Number of lines to include after the issue. Defaults to 5.
        
        Returns:
            Optional[str]: The extracted code context, or None if the file cannot be read.
        """
        try:
            start_line = max(1, line_number - lines_before)
            end_line = line_number + lines_after
            
            context = read_file_lines(file_path, start_line, end_line)
            
            # Add line numbers to the context
            lines = context.split('\n')
            numbered_lines = [
                f"{start_line + i}: {line}"
                for i, line in enumerate(lines)
            ]
            
            return '\n'.join(numbered_lines)
            
        except Exception as e:
            # Log the error (in a real implementation, use proper logging)
            print(f"Error building context: {str(e)}")
            return None 