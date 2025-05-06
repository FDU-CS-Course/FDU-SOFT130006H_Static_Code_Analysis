"""Parser for cppcheck CSV output files.

This module provides functionality to parse cppcheck CSV output files into a structured format
that can be used by the Review Helper application.
"""

import csv
import io
from typing import Dict, List, Union, Any
import logging

logger = logging.getLogger(__name__)

def parse_cppcheck_csv(file_path_or_buffer: Union[str, io.BytesIO]) -> List[Dict[str, Any]]:
    """Parse a cppcheck CSV output file into a list of issue dictionaries.
    
    Args:
        file_path_or_buffer: Either a path to a CSV file or a file-like object containing CSV data.
        
    Returns:
        A list of dictionaries, each representing a cppcheck issue with the following keys:
        - File: Path to the source file
        - Line: Line number where the issue was found
        - Severity: Issue severity (error, warning, style, etc.)
        - Id: Unique identifier for the issue type
        - Summary: Detailed description of the issue
        
    Raises:
        FileNotFoundError: If file_path_or_buffer is a string and the file doesn't exist
        ValueError: If the CSV file is malformed or missing required columns
        IOError: If there are issues reading the file
    """
    issues = []
    required_columns = {'File', 'Line', 'Severity', 'Id', 'Summary'}
    
    try:
        # Handle both file paths and file-like objects
        if isinstance(file_path_or_buffer, str):
            with open(file_path_or_buffer, 'r', encoding='utf-8') as f:
                fields = f.readline().split(',')
                fields = [field.strip() for field in fields]
                rows = [line.strip().split(',', maxsplit=len(fields) - 1) for line in f if line.strip()]
        else:
            # Handle file-like objects (e.g., BytesIO)
            content = file_path_or_buffer.getvalue().decode('utf-8')
            fields = content.split(',')
            fields = [field.strip() for field in fields]
            rows = [line.strip().split(',', maxsplit=len(fields) - 1) for line in content.splitlines() if line.strip()]
        
        # Convert rows to list[dict[str, str]]
        rows = [{fields[i]: row[i] for i in range(len(fields))} for row in rows]

        _validate_columns(fields, required_columns)
        issues = _process_rows(rows)
            
        return issues
        
    except Exception as e:
        logger.error(f"Error parsing cppcheck CSV: {str(e)}")
        raise

def _validate_columns(fieldnames: List[str], required_columns: set) -> None:
    """Validate that all required columns are present in the CSV.
    
    Args:
        fieldnames: List of column names from the CSV
        required_columns: Set of required column names
        
    Raises:
        ValueError: If any required columns are missing
    """
    if not fieldnames:
        raise ValueError("CSV file appears to be empty or malformed")
        
    missing_columns = required_columns - set(fieldnames)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

def _process_rows(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Process CSV rows into issue dictionaries.
    
    Args:
        reader: CSV DictReader object
        
    Returns:
        List of issue dictionaries
    """
    issues = []
    for row_num, row in enumerate(rows, start=2):  # Start from 2 to account for header row
        try:
            # Convert Line to integer
            row['Line'] = int(row['Line'])
            
            # Create a new dict to avoid modifying the original
            issue = {
                'cppcheck_file': row['File'],
                'cppcheck_line': row['Line'],
                'cppcheck_severity': row['Severity'],
                'cppcheck_id': row['Id'],
                'cppcheck_summary': row['Summary']
            }
            issues.append(issue)
            
        except (ValueError, KeyError) as e:
            logger.warning(f"Error processing row {row_num}: {str(e)}")
            continue
            
    return issues 