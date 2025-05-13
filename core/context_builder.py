"""
Module for building code context around issues for LLM analysis.

This module provides functionality to extract relevant code snippets from source files
based on different strategies (e.g., fixed number of lines, function scope).
"""

import os
import re
from typing import Optional, Dict, Any, Tuple, List
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
        *args: Any,
        **kwargs: Dict[str, Any]
    ) -> Optional[str]:
        """
        Build code context around the specified line number using the given strategy.
        
        Args:
            file_path (str): Absolute path to the source file.
            line_number (int): Line number where the issue was found.
            strategy (str): Strategy to use for building context. 
                            Options: "fixed_lines", "function_scope", or "file_scope".
            **kwargs: Additional strategy-specific parameters.
        
        Returns:
            Optional[str]: The extracted code context, or None if the file path is unsafe
                         or the file cannot be read.
        
        Raises:
            ValueError: If the strategy is not supported.
        """
        # Validate file path
        if not is_path_safe(file_path, self.project_root):
            return None
        
        print(f"Building context for {file_path}:{line_number} with strategy {strategy}, kwargs: {kwargs}")
        # Select strategy
        if strategy == "fixed_lines":
            return self._build_fixed_lines_context(file_path, line_number, **kwargs)
        elif strategy == "function_scope":
            return self._build_function_scope_context(file_path, line_number, **kwargs)
        elif strategy == "file_scope":
            return self._build_file_scope_context(file_path, line_number, **kwargs)
        elif strategy == "project_scope":
            return self._build_project_scope_context(file_path, line_number, **kwargs)
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
    
    def _build_function_scope_context(
        self, 
        file_path: str, 
        line_number: int,
        max_lines: int = 100,  # Safety limit for function size
        **kwargs
    ) -> Optional[str]:
        """
        Build context by extracting the entire function or method surrounding the issue.
        
        Args:
            file_path (str): Absolute path to the source file.
            line_number (int): Line number where the issue was found.
            max_lines (int): Maximum number of lines to include to prevent excessive context.
            **kwargs: Additional parameters (unused).
            
        Returns:
            Optional[str]: The extracted function context, or None if:
                         - The file cannot be read
                         - No function can be found around the specified line
                         - The function is too large (exceeds max_lines)
        """
        try:
            # First, read a large section around the line to find function boundaries
            # Read 50 lines before and 200 lines after as an initial window
            window_start = max(1, line_number - 50)
            window_end = line_number + 200
            
            window_content = read_file_lines(file_path, window_start, window_end)
            if not window_content:
                return None
                
            lines = window_content.split('\n')
            
            # Find the function start (look backward for a line ending with '{')
            func_start_idx = None
            brace_count = 0
            found_function_signature = False
            
            # Look backward to find the function signature
            for i in range(min(50, line_number - window_start), -1, -1):
                line = lines[i].strip()
                
                # Check for opening braces
                if '{' in line:
                    brace_count += line.count('{')
                    if not found_function_signature:
                        # Look for likely function signature patterns
                        if re.search(r'(\w+\s+)+\w+\s*\([^)]*\)\s*({|$)', line):
                            found_function_signature = True
                            
                            # Find where the function actually starts (could be earlier)
                            j = i
                            while j > 0:
                                prev_line = lines[j-1].strip()
                                # If we find an empty line or a line with comment or a line ending with ;
                                # this might be the boundary
                                if (not prev_line or 
                                    prev_line.startswith('//') or 
                                    prev_line.startswith('/*') or
                                    prev_line.endswith(';')):
                                    break
                                j -= 1
                            
                            func_start_idx = j
                            break
                
                # If we see a closing brace or semicolon, we've gone too far back
                if '}' in line or line.endswith(';'):
                    brace_count -= line.count('}')
                    # If this is a balanced block, we're outside our target function
                    if brace_count <= 0:
                        break
            
            # If we couldn't find the function start
            if func_start_idx is None:
                # Fallback to fixed lines context
                return self._build_fixed_lines_context(file_path, line_number, **kwargs)
            
            # Find the function end (look forward for matching closing brace)
            func_end_idx = None
            brace_count = 0
            
            # Count opening braces including and after the function start
            for i in range(func_start_idx, len(lines)):
                line = lines[i]
                brace_count += line.count('{')
                brace_count -= line.count('}')
                
                # When brace count drops to 0, we've found the end of the function
                if brace_count == 0 and i > func_start_idx:
                    func_end_idx = i
                    break
            
            # If we couldn't find the function end or it's too large
            if func_end_idx is None or (func_end_idx - func_start_idx) > max_lines:
                # Fallback to fixed lines context
                return self._build_fixed_lines_context(file_path, line_number, **kwargs)
            
            # Extract the function lines with line numbers
            func_lines = []
            for i in range(func_start_idx, func_end_idx + 1):
                absolute_line_num = window_start + i
                func_lines.append(f"{absolute_line_num}: {lines[i]}")
            
            return '\n'.join(func_lines)
            
        except Exception as e:
            print(f"Error building function scope context: {str(e)}")
            # Fallback to fixed lines context on error
            return self._build_fixed_lines_context(file_path, line_number, **kwargs)
    
    def _build_file_scope_context(
        self,
        file_path: str,
        line_number: int,
        max_lines: int = 1000,  # Safety limit for file size
        highlight_issue_line: bool = True,  # Whether to highlight the issue line
        **kwargs
    ) -> Optional[str]:
        """
        Build context by extracting the entire file content.
        
        Args:
            file_path (str): Absolute path to the source file.
            line_number (int): Line number where the issue was found.
            max_lines (int): Maximum number of lines to include to prevent excessive context.
            highlight_issue_line (bool): Whether to highlight the issue line.
            **kwargs: Additional parameters (unused).
            
        Returns:
            Optional[str]: The extracted file context, or None if:
                         - The file cannot be read
                         - The file is too large (exceeds max_lines)
        """
        try:
            # Count file lines first to check if it exceeds max_lines
            with open(file_path, 'r', encoding='utf-8') as f:
                file_line_count = sum(1 for _ in f)
                
            if file_line_count > max_lines:
                # If file is too large, fallback to function scope or fixed lines
                context = self._build_function_scope_context(file_path, line_number, **kwargs)
                if context is not None:
                    return context
                return self._build_fixed_lines_context(file_path, line_number, **kwargs)
                
            # Read the entire file
            context = read_file_lines(file_path, 1, file_line_count)
            if not context:
                return None
                
            # Add line numbers to the context
            lines = context.split('\n')
            numbered_lines = []
            
            for i, line in enumerate(lines):
                line_num = i + 1
                
                # Optionally highlight the issue line
                if highlight_issue_line and line_num == line_number:
                    numbered_lines.append(f"{line_num}: >>> {line} <<<")
                else:
                    numbered_lines.append(f"{line_num}: {line}")
            
            return '\n'.join(numbered_lines)
            
        except Exception as e:
            print(f"Error building file scope context: {str(e)}")
            # Fallback to fixed lines context on error
            return self._build_fixed_lines_context(file_path, line_number, **kwargs) 
        
    def _build_project_scope_context(
        self,
        file_path: str,
        line_number: int,
        **kwargs
    ) -> Optional[str]:
        """
        According to the designated file, find all the relevant files (the file it included) and append it to the context.
        
        
        Args:
            file_path (str): The path of the file to be analyzed.
            line_number (int): The line number of the issue.
            
        Returns:
            Optional[str]: The extracted relevant context(the file itself and the files it included)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            # Find all the <#include> part
            include_part = re.findall(r'<#include>(.*?)</#include>', file_content, re.DOTALL)
            # exclude the standard library
            include_part = [include_file for include_file in include_part if not include_file.startswith('<') and not include_file.endswith('>') and not include_file.startswith('"') and not include_file.endswith('"')]
            designated_file_content = read_file_lines(file_path, 1, file_line_count)
            relevant_content = []
            
            for include_file in include_part:
                include_file_path = os.path.abspath(os.path.join(os.path.dirname(file_path), include_file))
                include_file_content = read_file_lines(include_file_path, 1, file_line_count)
                if not include_file_content:
                    continue
                prompt_prefix = f"This is the content of the file {include_file}:\n"
                relevant_content.append(prompt_prefix + include_file_content)
            return {
                "designated_file_content": designated_file_content,
                "relevant_content": relevant_content
            }
        except Exception as e:
            print(f"Error building project scope context: {str(e)}")
            return None
        
        