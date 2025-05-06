"""Unit tests for the issue_parser module."""

import io
import pytest
from core.issue_parser import parse_cppcheck_csv, _validate_columns, _process_rows

# Test data
VALID_CSV_CONTENT = """File,Line,Severity,Id,Summary
test.cpp,10,error,nullPointer,Null pointer dereference
test.cpp,20,warning,unusedFunction,Function 'foo' is never used
test.cpp,30,style,shadowVariable,Local variable 'i' shadows outer variable"""

MISSING_COLUMN_CSV = """File,Line,Severity,Id
test.cpp,10,error,nullPointer"""

MALFORMED_LINE_CSV = """File,Line,Severity,Id,Summary
test.cpp,invalid,error,nullPointer,Null pointer dereference"""

EMPTY_CSV = ""

def test_parse_cppcheck_csv_from_file(tmp_path):
    """Test parsing a CSV file from disk."""
    # Create a temporary CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(VALID_CSV_CONTENT)
    
    # Parse the file
    issues = parse_cppcheck_csv(str(csv_file))
    
    # Verify results
    assert len(issues) == 3
    assert issues[0]['File'] == 'test.cpp'
    assert issues[0]['Line'] == 10
    assert issues[0]['Severity'] == 'error'
    assert issues[0]['Id'] == 'nullPointer'
    assert issues[0]['Summary'] == 'Null pointer dereference'

def test_parse_cppcheck_csv_from_buffer():
    """Test parsing a CSV file from a BytesIO buffer."""
    # Create a BytesIO buffer with CSV content
    buffer = io.BytesIO(VALID_CSV_CONTENT.encode('utf-8'))
    
    # Parse the buffer
    issues = parse_cppcheck_csv(buffer)
    
    # Verify results
    assert len(issues) == 3
    assert issues[1]['File'] == 'test.cpp'
    assert issues[1]['Line'] == 20
    assert issues[1]['Severity'] == 'warning'
    assert issues[1]['Id'] == 'unusedFunction'
    assert issues[1]['Summary'] == "Function 'foo' is never used"

def test_parse_cppcheck_csv_missing_columns(tmp_path):
    """Test parsing a CSV file with missing required columns."""
    # Create a temporary CSV file with missing columns
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(MISSING_COLUMN_CSV)
    
    # Verify that parsing raises ValueError
    with pytest.raises(ValueError) as exc_info:
        parse_cppcheck_csv(str(csv_file))
    assert "Missing required columns" in str(exc_info.value)

def test_parse_cppcheck_csv_malformed_line(tmp_path):
    """Test parsing a CSV file with malformed line numbers."""
    # Create a temporary CSV file with invalid line number
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(MALFORMED_LINE_CSV)
    
    # Parse the file - should skip the invalid row
    issues = parse_cppcheck_csv(str(csv_file))
    
    # Verify that the invalid row was skipped
    assert len(issues) == 0

def test_parse_cppcheck_csv_empty_file(tmp_path):
    """Test parsing an empty CSV file."""
    # Create an empty temporary CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(EMPTY_CSV)
    
    # Verify that parsing raises ValueError
    with pytest.raises(ValueError) as exc_info:
        parse_cppcheck_csv(str(csv_file))
    assert "CSV file appears to be empty" in str(exc_info.value)

def test_validate_columns():
    """Test the _validate_columns helper function."""
    # Test with valid columns
    valid_columns = ['File', 'Line', 'Severity', 'Id', 'Summary']
    required_columns = {'File', 'Line', 'Severity', 'Id', 'Summary'}
    _validate_columns(valid_columns, required_columns)  # Should not raise
    
    # Test with missing columns
    missing_columns = ['File', 'Line', 'Severity']
    with pytest.raises(ValueError) as exc_info:
        _validate_columns(missing_columns, required_columns)
    assert "Missing required columns" in str(exc_info.value)
    
    # Test with empty columns
    with pytest.raises(ValueError) as exc_info:
        _validate_columns(None, required_columns)
    assert "CSV file appears to be empty" in str(exc_info.value)

def test_process_rows():
    """Test the _process_rows helper function."""
    import csv
    
    # Create a CSV reader with test data
    reader = csv.DictReader(io.StringIO(VALID_CSV_CONTENT))
    
    # Process the rows
    issues = _process_rows(reader)
    
    # Verify results
    assert len(issues) == 3
    assert all(isinstance(issue['Line'], int) for issue in issues)
    assert all(required in issue for issue in issues for required in ['File', 'Line', 'Severity', 'Id', 'Summary']) 