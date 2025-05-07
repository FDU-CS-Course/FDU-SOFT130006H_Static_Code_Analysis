# Data Manager Module Documentation

## Overview

The `data_manager.py` module is a core component of the Review Helper application, responsible for all interactions with the SQLite database. It provides a clean API for storing, retrieving, and analyzing cppcheck issues and their LLM-generated classifications.

## Database Schema

The module manages two primary tables:

### `issues` Table

Stores information about cppcheck issues:

| Column                     | Type     | Description                                               |
|----------------------------|----------|-----------------------------------------------------------|
| `id`                       | INTEGER  | Primary key, auto-incremented                             |
| `cppcheck_file`            | TEXT     | File path from cppcheck                                   |
| `cppcheck_line`            | INTEGER  | Line number in the file                                   |
| `cppcheck_severity`        | TEXT     | Severity level (error, warning, style, etc.)              |
| `cppcheck_id`              | TEXT     | Issue type ID (nullPointer, arrayIndexOutOfBounds, etc.)  |
| `cppcheck_summary`         | TEXT     | Description of the issue                                  |
| `true_classification`      | TEXT     | Final verified classification (may be null)               |
| `true_classification_comment` | TEXT  | Comment explaining true classification (may be null)      |
| `status`                   | TEXT     | Current status: 'pending_llm', 'pending_review', 'reviewed' |
| `created_at`               | TIMESTAMP| When the issue was added to the database                  |
| `updated_at`               | TIMESTAMP| When the issue was last updated                           |

### `llm_classifications` Table

Stores LLM-generated classifications for issues:

| Column                | Type     | Description                                                  |
|-----------------------|----------|--------------------------------------------------------------|
| `id`                  | INTEGER  | Primary key, auto-incremented                                |
| `issue_id`            | INTEGER  | Foreign key to issues.id                                     |
| `llm_model_name`      | TEXT     | Name of the LLM model used                                   |
| `context_strategy`    | TEXT     | Strategy used to build code context                          |
| `prompt_template`     | TEXT     | Name of the prompt template used                             |
| `source_code_context` | TEXT     | Code context provided to the LLM                             |
| `classification`      | TEXT     | LLM's classification (false positive, need fixing, very serious) |
| `explanation`         | TEXT     | Explanation for the classification (may be null)             |
| `processing_timestamp`| TIMESTAMP| When the LLM processing was completed                        |
| `user_agrees`         | BOOLEAN  | User feedback on LLM classification (may be null)            |
| `user_comment`        | TEXT     | User comment on LLM classification (may be null)             |

## API Reference

### Database Setup

#### `init_db() -> None`

Initializes the database by creating necessary tables and triggers if they don't exist.

```python
from core.data_manager import init_db

# Initialize the database
init_db()
```

### Issue Management

#### `add_issues(issues: List[Dict[str, Any]]) -> List[int]`

Adds new issues parsed from cppcheck CSV to the database.

**Parameters:**
- `issues`: A list of dictionaries, each representing a cppcheck issue with the following keys:
  - `file`: File path
  - `line`: Line number
  - `severity`: Issue severity
  - `id`: Issue ID
  - `summary`: Issue description

**Returns:**
- A list of issue IDs that were added to the database.

**Raises:**
- `ValueError`: If any issue is missing required fields.
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import add_issues

# Sample issues
issues = [
    {
        'file': 'src/main.cpp',
        'line': 42,
        'severity': 'warning',
        'id': 'nullPointer',
        'summary': 'Possible null pointer dereference: ptr'
    }
]

# Add issues to the database
issue_ids = add_issues(issues)
print(f"Added issues with IDs: {issue_ids}")
```

#### `get_issue_by_id(issue_id: int) -> Optional[Dict[str, Any]]`

Retrieves a specific issue with all its LLM classifications.

**Parameters:**
- `issue_id`: The ID of the issue to retrieve.

**Returns:**
- A dictionary with issue details and a nested list of classifications, or None if not found.

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_issue_by_id

# Get issue with ID 1
issue = get_issue_by_id(1)
if issue:
    print(f"Issue: {issue['cppcheck_file']}:{issue['cppcheck_line']} - {issue['cppcheck_summary']}")
    print(f"LLM Classifications: {len(issue['llm_classifications'])}")
else:
    print("Issue not found")
```

#### `get_all_issues(filters: Optional[Dict] = None) -> List[Dict[str, Any]]`

Retrieves all issues, optionally applying filters.

**Parameters:**
- `filters`: A dictionary of filter conditions. Supported filters:
  - `status`: Issue status (e.g., 'pending_llm', 'pending_review', 'reviewed')
  - `severity`: Issue severity (e.g., 'error', 'warning')
  - `true_classification`: Final classification (e.g., 'false positive')

**Returns:**
- A list of issue dictionaries, each with a nested list of LLM classifications.

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_all_issues

# Get all issues
all_issues = get_all_issues()
print(f"Total issues: {len(all_issues)}")

# Get only pending review issues
pending_review = get_all_issues({'status': 'pending_review'})
print(f"Pending review: {len(pending_review)}")

# Get all error severity issues
errors = get_all_issues({'severity': 'error'})
print(f"Error issues: {len(errors)}")
```

### LLM Classification Management

#### `add_llm_classification(issue_id: int, llm_model_name: str, context_strategy: str, prompt_template: str, source_code_context: str, classification: str, explanation: Optional[str] = None) -> int`

Adds a new LLM classification attempt to the database.

**Parameters:**
- `issue_id`: ID of the issue being classified.
- `llm_model_name`: Name of the LLM model used.
- `context_strategy`: Strategy used to build context.
- `prompt_template`: Name of the prompt template used.
- `source_code_context`: Code context provided to the LLM.
- `classification`: Classification by LLM (one of: 'false positive', 'need fixing', 'very serious')
- `explanation`: Optional explanation from the LLM.

**Returns:**
- The ID of the newly created classification.

**Side Effects:**
- Updates the issue's status from 'pending_llm' to 'pending_review' if this is the first classification.

**Raises:**
- `ValueError`: If issue_id does not exist.
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import add_llm_classification

# Add a classification for issue with ID 1
classification_id = add_llm_classification(
    issue_id=1,
    llm_model_name='gpt-4',
    context_strategy='fixed_lines',
    prompt_template='classification_default.txt',
    source_code_context='void func() { int* ptr = nullptr; *ptr = 42; }',
    classification='false positive',
    explanation='This is a false positive because the code is unreachable.'
)
print(f"Added classification with ID: {classification_id}")
```

#### `update_llm_classification_review(classification_id: int, user_agrees: bool, user_comment: Optional[str] = None) -> bool`

Updates user feedback for a specific LLM classification attempt.

**Parameters:**
- `classification_id`: ID of the classification to update.
- `user_agrees`: User's feedback - True if LLM was correct, False if incorrect.
- `user_comment`: Optional comment from the user.

**Returns:**
- True if successful, False if classification not found.

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import update_llm_classification_review

# Update classification with ID 1
success = update_llm_classification_review(
    classification_id=1,
    user_agrees=True,
    user_comment='Good analysis, this is indeed a false positive.'
)
if success:
    print("Classification review updated successfully")
else:
    print("Classification not found")
```

#### `set_issue_true_classification(issue_id: int, classification: str, comment: Optional[str] = None) -> bool`

Sets the final verified classification for an issue.

**Parameters:**
- `issue_id`: ID of the issue to update.
- `classification`: Final classification (one of: 'false positive', 'need fixing', 'very serious')
- `comment`: Optional comment explaining the true classification.

**Returns:**
- True if successful, False if issue not found.

**Side Effects:**
- Updates the issue's status to 'reviewed'.

**Raises:**
- `ValueError`: If classification is not valid.
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import set_issue_true_classification

# Set the true classification for issue with ID 1
success = set_issue_true_classification(
    issue_id=1,
    classification='need fixing',
    comment='This is a real issue that should be fixed in the next sprint.'
)
if success:
    print("Issue classification set successfully")
else:
    print("Issue not found")
```

### Statistics and Analysis

#### `get_llm_statistics(filters: Optional[Dict] = None) -> Dict[str, Any]`

Retrieves statistics about LLM performance, context strategies, and prompt templates.

**Parameters:**
- `filters`: Dictionary of filter conditions. Supported filters:
  - `llm_model_name`: Filter by specific LLM model
  - `context_strategy`: Filter by context building strategy
  - `prompt_template`: Filter by prompt template
  - `date_from`: Filter by classification date (start)
  - `date_to`: Filter by classification date (end)

**Returns:**
- Dictionary containing:
  - `overall_accuracy`: Overall accuracy statistics
  - `llm_models`: Performance statistics by LLM model
  - `context_strategies`: Performance statistics by context strategy
  - `prompt_templates`: Performance statistics by prompt template
  - `classification_distribution`: Distribution of true classifications

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_llm_statistics
from datetime import datetime, timedelta

# Get overall statistics
stats = get_llm_statistics()
print(f"Overall accuracy: {stats['overall_accuracy']['accuracy'] * 100:.2f}%")

# Get statistics for a specific LLM model
gpt4_stats = get_llm_statistics({'llm_model_name': 'gpt-4'})
print(f"GPT-4 accuracy: {gpt4_stats['overall_accuracy']['accuracy'] * 100:.2f}%")

# Get statistics for the last 7 days
one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
recent_stats = get_llm_statistics({'date_from': one_week_ago})
print(f"Recent accuracy: {recent_stats['overall_accuracy']['accuracy'] * 100:.2f}%")
```

### Advanced Issue Filtering

#### `get_all_issue_statuses() -> set`

Retrieves all unique issue statuses from the database.

**Returns:**
- A set of unique status values (e.g., 'pending_llm', 'pending_review', 'reviewed').

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_all_issue_statuses

# Get all possible issue statuses
statuses = get_all_issue_statuses()
print(f"Available statuses: {statuses}")
```

#### `get_all_issue_severities() -> set`

Retrieves all unique issue severities from the database.

**Returns:**
- A set of unique severity values (e.g., 'error', 'warning', 'style').

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_all_issue_severities

# Get all possible issue severities
severities = get_all_issue_severities()
print(f"Available severities: {severities}")
```

#### `get_all_issue_cppcheck_ids() -> set`

Retrieves all unique cppcheck issue IDs from the database.

**Returns:**
- A set of unique cppcheck_id values (e.g., 'nullPointer', 'arrayIndexOutOfBounds').

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_all_issue_cppcheck_ids

# Get all possible cppcheck IDs
cppcheck_ids = get_all_issue_cppcheck_ids()
print(f"Available cppcheck IDs: {cppcheck_ids}")
```

#### `get_issues_by_filters(statuses: Optional[set] = None, severities: Optional[set] = None, cppcheck_ids: Optional[set] = None, contradictory_only: bool = False) -> List[Dict[str, Any]]`

Retrieves issues based on multiple filter criteria.

**Parameters:**
- `statuses`: Optional set of status values to filter by.
- `severities`: Optional set of severity values to filter by.
- `cppcheck_ids`: Optional set of cppcheck_id values to filter by.
- `contradictory_only`: If True, only return issues with contradictory LLM classifications.

**Returns:**
- A list of issue dictionaries matching the criteria.

**Raises:**
- `sqlite3.Error`: If a database error occurs.

```python
from core.data_manager import get_issues_by_filters

# Get all error-level issues that are pending review
issues = get_issues_by_filters(
    statuses={'pending_review'},
    severities={'error'}
)
print(f"Found {len(issues)} error-level issues pending review")

# Get issues with contradictory LLM classifications
contradictory_issues = get_issues_by_filters(contradictory_only=True)
print(f"Found {len(contradictory_issues)} issues with contradictory classifications")

# Get issues with specific cppcheck IDs
specific_issues = get_issues_by_filters(
    cppcheck_ids={'nullPointer', 'uninitvar'}
)
print(f"Found {len(specific_issues)} null pointer or uninitialized variable issues")
```

## Security Considerations

The `data_manager.py` module implements several security best practices:

1. **SQL Injection Prevention**:
   - All database queries use parameterized statements with placeholders (?, ?)
   - User input is never directly concatenated into SQL strings

2. **Input Validation**:
   - Required fields are validated before database operations
   - Classification values are validated against a predefined set of valid options
   - Issue existence is verified before adding related records

3. **Error Handling**:
   - Comprehensive try-except blocks with specific error logging
   - Errors are captured and logged, but generic responses are returned to users
   - Database errors are properly propagated while maintaining clean exception hierarchies

4. **Resource Management**:
   - Database connections are managed using a context manager pattern
   - Connections are properly closed even when exceptions occur
   - Database directory is created with appropriate permissions if it doesn't exist

## Performance Considerations

For large datasets, consider the following:

1. **Batch Operations**:
   - When adding many issues, consider breaking them into smaller batches
   - Use transactions for bulk operations

2. **Query Optimization**:
   - The module includes proper indexing for foreign keys
   - Filters are applied at the database level rather than in Python code

3. **Memory Management**:
   - Large result sets are processed as iterators where possible
   - We use SQLite's row factory to avoid unnecessary dictionary creation

## Extensibility

The `data_manager.py` module is designed for extensibility:

1. **New Classifications**:
   - To add a new classification type, update the validation list in `set_issue_true_classification`
   
2. **Additional Filters**:
   - To add new filters to `get_all_issues` or `get_llm_statistics`, extend the conditions list

3. **Schema Updates**:
   - When extending the schema, update the `CREATE_*` constants and provide migration scripts

## Troubleshooting

Common issues and their solutions:

1. **Database Not Found**:
   - Ensure `DB_DIR` exists or the module has permission to create it
   - Check that `DB_PATH` is correctly set

2. **"issue_id does not exist" Error**:
   - Verify that the issue was correctly added to the database
   - Check that you're using the correct issue ID

3. **Statistics Return Zero Results**:
   - Ensure issues have true classifications set
   - Check that filter conditions aren't too restrictive 