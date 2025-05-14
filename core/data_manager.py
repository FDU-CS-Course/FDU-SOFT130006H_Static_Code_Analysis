"""
Database management module for the Review Helper application.

This module handles all interactions with the SQLite database, including:
- Database initialization
- Issue management (adding, retrieving, updating)
- LLM classification management
- Statistical data retrieval

The module uses SQLite for data persistence, storing cppcheck issues,
LLM classifications, and user reviews.
"""

DB_INITIALIZED:bool = False

import os
import sqlite3
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import json
import logging
from contextlib import contextmanager
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database constants
DB_DIR = "db"
DB_FILE = "issues.db"
DB_PATH = os.path.join(DB_DIR, DB_FILE)

# SQL statements for table creation
CREATE_ISSUES_TABLE = """
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cppcheck_file TEXT NOT NULL,
    cppcheck_line INTEGER NOT NULL,
    cppcheck_severity TEXT NOT NULL,
    cppcheck_id TEXT NOT NULL,
    cppcheck_summary TEXT NOT NULL,
    true_classification TEXT,
    true_classification_comment TEXT,
    status TEXT NOT NULL DEFAULT 'pending_llm',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_LLM_CLASSIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS llm_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL,
    llm_model_name TEXT NOT NULL,
    context_strategy TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    source_code_context TEXT NOT NULL,
    classification TEXT NOT NULL,
    explanation TEXT,
    processing_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_agrees BOOLEAN,
    user_comment TEXT,
    FOREIGN KEY (issue_id) REFERENCES issues(id)
)
"""

CREATE_LLM_RESPONSES_TABLE = """
CREATE TABLE IF NOT EXISTS llm_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classification_id INTEGER NOT NULL,
    full_prompt TEXT NOT NULL,
    full_response TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    response_time_ms INTEGER,
    model_parameters TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (classification_id) REFERENCES llm_classifications(id)
)
"""

# Trigger to update the 'updated_at' field in issues table
CREATE_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_issues_timestamp
AFTER UPDATE ON issues
BEGIN
    UPDATE issues SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""

@contextmanager
def get_db_connection() -> sqlite3.Connection:
    """
    Context manager for database connections.
    
    Returns:
        sqlite3.Connection: A connection to the SQLite database.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    # Ensure the database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db() -> None:
    """
    Initialize the database by creating necessary tables if they don't exist.
    
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_ISSUES_TABLE)
            cursor.execute(CREATE_LLM_CLASSIFICATIONS_TABLE)
            cursor.execute(CREATE_LLM_RESPONSES_TABLE)
            cursor.execute(CREATE_UPDATE_TRIGGER)
            conn.commit()
            logger.info("Database initialized successfully.")
            DB_INITIALIZED = True
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def add_issues(issues: List[Dict[str, Any]]) -> List[int]:
    """
    Add new issues parsed from cppcheck CSV to the database.
    
    Args:
        issues (List[Dict[str, Any]]): List of dictionaries representing cppcheck issues.
            Each dictionary should have keys: 'file', 'line', 'severity', 'id', 'summary'.
            
    Returns:
        List[int]: List of issue IDs that were added to the database.
        
    Raises:
        sqlite3.Error: If a database error occurs.
        ValueError: If any issue is missing required fields.
    """
    issue_ids = []
    required_fields = ['cppcheck_file', 'cppcheck_line', 'cppcheck_severity', 'cppcheck_id', 'cppcheck_summary']
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for issue in issues:
                # Validate issue has all required fields
                if not all(field in issue for field in required_fields):
                    missing = [f for f in required_fields if f not in issue]
                    raise ValueError(f"Issue missing required fields: {missing}")
                
                cursor.execute("""
                    INSERT INTO issues (
                        cppcheck_file, cppcheck_line, cppcheck_severity, 
                        cppcheck_id, cppcheck_summary, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    issue['cppcheck_file'], 
                    issue['cppcheck_line'], 
                    issue['cppcheck_severity'], 
                    issue['cppcheck_id'], 
                    issue['cppcheck_summary'],
                    'pending_llm'
                ))
                issue_ids.append(cursor.lastrowid)
            conn.commit()
            logger.info(f"Added {len(issue_ids)} issues to the database.")
            return issue_ids
    except sqlite3.Error as e:
        logger.error(f"Failed to add issues: {e}")
        raise

def get_issue_by_id(issue_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific issue with all its LLM classifications.
    
    Args:
        issue_id (int): The ID of the issue to retrieve.
        
    Returns:
        Optional[Dict[str, Any]]: Dictionary with issue details and classifications or None if not found.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get issue
            cursor.execute("""
                SELECT * FROM issues WHERE id = ?
            """, (issue_id,))
            issue = cursor.fetchone()
            
            if not issue:
                return None
            
            # Convert to dict
            issue_dict = dict(issue)
            
            # Get classifications
            cursor.execute("""
                SELECT * FROM llm_classifications WHERE issue_id = ?
                ORDER BY processing_timestamp DESC
            """, (issue_id,))
            classifications = [dict(row) for row in cursor.fetchall()]
            
            issue_dict['llm_classifications'] = classifications
            return issue_dict
    except sqlite3.Error as e:
        logger.error(f"Failed to get issue {issue_id}: {e}")
        raise

def get_all_issues(filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    Retrieve all issues, optionally applying filters.
    
    Args:
        filters (Optional[Dict]): Dictionary of filter conditions. 
            Supported filters: 'status', 'severity', 'true_classification'.
            
    Returns:
        List[Dict[str, Any]]: List of issue dictionaries.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    query = "SELECT * FROM issues"
    params = []
    
    if filters:
        conditions = []
        
        if 'status' in filters:
            conditions.append("status = ?")
            params.append(filters['status'])
            
        if 'severity' in filters:
            conditions.append("cppcheck_severity = ?")
            params.append(filters['severity'])
            
        if 'true_classification' in filters:
            conditions.append("true_classification = ?")
            params.append(filters['true_classification'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY id DESC"
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            issues = [dict(row) for row in cursor.fetchall()]
            
            # Get classifications for each issue
            for issue in issues:
                cursor.execute("""
                    SELECT * FROM llm_classifications WHERE issue_id = ?
                    ORDER BY processing_timestamp DESC
                """, (issue['id'],))
                issue['llm_classifications'] = [dict(row) for row in cursor.fetchall()]
                
            return issues
    except sqlite3.Error as e:
        logger.error(f"Failed to get issues: {e}")
        raise

def get_issue_count() -> int:
    """
    Retrieve the total count of issues in the database.
    
    Returns:
        int: The total number of issues.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM issues")
            result = cursor.fetchone()
            return result['count']
    except sqlite3.Error as e:
        logger.error(f"Failed to get issue count: {e}")
        raise

def get_issue_counts_by_status() -> Dict[str, int]:
    """
    Retrieve the count of issues grouped by status.
    
    Returns:
        Dict[str, int]: Dictionary with status as key and count as value.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM issues 
                GROUP BY status
            """)
            results = cursor.fetchall()
            return {row['status']: row['count'] for row in results}
    except sqlite3.Error as e:
        logger.error(f"Failed to get issue counts by status: {e}")
        raise

def get_issue_counts_by_severity() -> Dict[str, int]:
    """
    Retrieve the count of issues grouped by severity.
    
    Returns:
        Dict[str, int]: Dictionary with severity as key and count as value.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cppcheck_severity, COUNT(*) as count 
                FROM issues 
                GROUP BY cppcheck_severity
            """)
            results = cursor.fetchall()
            return {row['cppcheck_severity']: row['count'] for row in results}
    except sqlite3.Error as e:
        logger.error(f"Failed to get issue counts by severity: {e}")
        raise

def get_issues_summary() -> Dict[str, Any]:
    """
    Retrieve a complete summary of issue counts by status and severity.
    
    Returns:
        Dict[str, Any]: Dictionary with:
            - 'total': Total issue count
            - 'by_status': Dictionary with status counts
            - 'by_severity': Dictionary with severity counts
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) as count FROM issues")
            total = cursor.fetchone()['count']
            
            # Get counts by status
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM issues 
                GROUP BY status
            """)
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Get counts by severity
            cursor.execute("""
                SELECT cppcheck_severity, COUNT(*) as count 
                FROM issues 
                GROUP BY cppcheck_severity
            """)
            severity_counts = {row['cppcheck_severity']: row['count'] for row in cursor.fetchall()}
            
            return {
                'total': total,
                'by_status': status_counts,
                'by_severity': severity_counts
            }
    except sqlite3.Error as e:
        logger.error(f"Failed to get issues summary: {e}")
        raise

def add_llm_classification(
    issue_id: int, 
    llm_model_name: str, 
    context_strategy: str, 
    prompt_template: str, 
    source_code_context: str, 
    classification: str, 
    explanation: Optional[str] = None,
    full_prompt: Optional[str] = None,
    full_response: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    response_time_ms: Optional[int] = None,
    model_parameters: Optional[Dict] = None
) -> Union[int, Tuple[int, int]]:
    """
    Add a new LLM classification attempt to the database.
    
    Args:
        issue_id (int): ID of the issue being classified.
        llm_model_name (str): Name of the LLM model used.
        context_strategy (str): Strategy used to build context.
        prompt_template (str): Name of the prompt template used.
        source_code_context (str): Code context provided to the LLM.
        classification (str): Classification by LLM.
        explanation (Optional[str]): Optional explanation from the LLM.
        full_prompt (Optional[str]): The complete prompt sent to the LLM. If provided, a record will be added to llm_responses.
        full_response (Optional[str]): The complete raw response from the LLM. If provided, a record will be added to llm_responses.
        prompt_tokens (Optional[int]): Number of tokens in the prompt.
        completion_tokens (Optional[int]): Number of tokens in the completion/response.
        total_tokens (Optional[int]): Total number of tokens used in the interaction.
        response_time_ms (Optional[int]): Response time in milliseconds.
        model_parameters (Optional[Dict]): Dictionary of model parameters used (temperature, etc.).
        
    Returns:
        Union[int, Tuple[int, int]]: If full_prompt and full_response are provided, returns a tuple of
                                     (classification_id, response_id), otherwise just classification_id.
        
    Raises:
        sqlite3.Error: If a database error occurs.
        ValueError: If issue_id does not exist.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if issue exists
            cursor.execute("SELECT id FROM issues WHERE id = ?", (issue_id,))
            if not cursor.fetchone():
                raise ValueError(f"Issue with ID {issue_id} does not exist")
            
            # Insert classification
            cursor.execute("""
                INSERT INTO llm_classifications (
                    issue_id, llm_model_name, context_strategy, prompt_template,
                    source_code_context, classification, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                issue_id, llm_model_name, context_strategy, prompt_template,
                source_code_context, classification, explanation
            ))
            
            classification_id = cursor.lastrowid
            
            # Update issue status if this is the first classification
            cursor.execute("""
                UPDATE issues SET status = 'pending_review'
                WHERE id = ? AND status = 'pending_llm'
            """, (issue_id,))
            
            conn.commit()
            
            # If full prompt and response are provided, add a record to llm_responses
            response_id = None
            if full_prompt and full_response:
                try:
                    response_id = add_llm_response(
                        classification_id=classification_id,
                        full_prompt=full_prompt,
                        full_response=full_response,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        response_time_ms=response_time_ms,
                        model_parameters=model_parameters
                    )
                    return (classification_id, response_id)
                except Exception as e:
                    logger.error(f"Failed to add LLM response for classification {classification_id}: {e}")
                    # Still return the classification_id even if adding the response fails
            
            return classification_id
    except sqlite3.Error as e:
        logger.error(f"Failed to add classification: {e}")
        raise

def update_llm_classification_review(
    classification_id: int, 
    user_agrees: bool, 
    user_comment: Optional[str] = None
) -> bool:
    """
    Update user feedback for a specific LLM classification attempt.
    
    Args:
        classification_id (int): ID of the classification to update.
        user_agrees (bool): User's feedback - True if LLM was correct, False if incorrect.
        user_comment (Optional[str]): Optional comment from the user.
        
    Returns:
        bool: True if successful, False if classification not found.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if classification exists
            cursor.execute("SELECT id FROM llm_classifications WHERE id = ?", (classification_id,))
            if not cursor.fetchone():
                return False
            
            cursor.execute("""
                UPDATE llm_classifications SET
                    user_agrees = ?,
                    user_comment = ?
                WHERE id = ?
            """, (user_agrees, user_comment, classification_id))
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"Failed to update classification review: {e}")
        raise

def set_issue_true_classification(
    issue_id: int, 
    classification: str, 
    comment: Optional[str] = None
) -> bool:
    """
    Set the final verified classification for an issue.
    
    Args:
        issue_id (int): ID of the issue to update.
        classification (str): Final classification (e.g., 'false positive', 'need fixing', 'very serious').
        comment (Optional[str]): Optional comment explaining the true classification.
        
    Returns:
        bool: True if successful, False if issue not found.
        
    Raises:
        sqlite3.Error: If a database error occurs.
        ValueError: If classification is not valid.
    """
    valid_classifications = ['false positive', 'need fixing', 'very serious']
    
    if classification not in valid_classifications:
        raise ValueError(f"Invalid classification. Must be one of: {valid_classifications}")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if issue exists
            cursor.execute("SELECT id FROM issues WHERE id = ?", (issue_id,))
            if not cursor.fetchone():
                return False
            
            cursor.execute("""
                UPDATE issues SET
                    true_classification = ?,
                    true_classification_comment = ?,
                    status = 'reviewed'
                WHERE id = ?
            """, (classification, comment, issue_id))
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"Failed to set true classification: {e}")
        raise

def get_llm_statistics(filters: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Retrieve statistics about LLM performance, context strategies, and prompt templates.
    
    Args:
        filters (Optional[Dict]): Dictionary of filter conditions.
            Supported filters: 'llm_model_name', 'context_strategy', 'prompt_template',
            'date_from', 'date_to'.
            
    Returns:
        Dict[str, Any]: Dictionary containing various statistics.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Base query parts
            select_base = """
                SELECT lc.llm_model_name, lc.context_strategy, lc.prompt_template,
                       lc.classification, i.true_classification, 
                       CASE WHEN lc.classification = i.true_classification THEN 1 ELSE 0 END as is_correct
            """
            
            from_base = """
                FROM llm_classifications lc
                JOIN issues i ON lc.issue_id = i.id
                WHERE i.true_classification IS NOT NULL
            """
            
            # Add filters
            params = []
            if filters:
                conditions = []
                
                if 'llm_model_name' in filters:
                    conditions.append("lc.llm_model_name = ?")
                    params.append(filters['llm_model_name'])
                
                if 'context_strategy' in filters:
                    conditions.append("lc.context_strategy = ?")
                    params.append(filters['context_strategy'])
                
                if 'prompt_template' in filters:
                    conditions.append("lc.prompt_template = ?")
                    params.append(filters['prompt_template'])
                
                if 'date_from' in filters:
                    conditions.append("lc.processing_timestamp >= ?")
                    params.append(filters['date_from'])
                
                if 'date_to' in filters:
                    conditions.append("lc.processing_timestamp <= ?")
                    params.append(filters['date_to'])
                
                if conditions:
                    from_base += " AND " + " AND ".join(conditions)
            
            # Overall accuracy
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN lc.classification = i.true_classification THEN 1 ELSE 0 END) as correct
                {from_base}
            """, params)
            
            overall = cursor.fetchone()
            total = overall['total'] if overall else 0
            correct = overall['correct'] if overall else 0
            
            # LLM model performance
            cursor.execute(f"""
                {select_base}
                {from_base}
                GROUP BY lc.llm_model_name
            """, params)
            
            llm_models = {}
            for row in cursor.fetchall():
                model_name = row['llm_model_name']
                if model_name not in llm_models:
                    llm_models[model_name] = {
                        'total': 0,
                        'correct': 0
                    }
                llm_models[model_name]['total'] += 1
                llm_models[model_name]['correct'] += row['is_correct']
            
            # Context strategy performance
            cursor.execute(f"""
                {select_base}
                {from_base}
                GROUP BY lc.context_strategy
            """, params)
            
            context_strategies = {}
            for row in cursor.fetchall():
                strategy = row['context_strategy']
                if strategy not in context_strategies:
                    context_strategies[strategy] = {
                        'total': 0,
                        'correct': 0
                    }
                context_strategies[strategy]['total'] += 1
                context_strategies[strategy]['correct'] += row['is_correct']
            
            # Prompt template performance
            cursor.execute(f"""
                {select_base}
                {from_base}
                GROUP BY lc.prompt_template
            """, params)
            
            prompt_templates = {}
            for row in cursor.fetchall():
                template = row['prompt_template']
                if template not in prompt_templates:
                    prompt_templates[template] = {
                        'total': 0,
                        'correct': 0
                    }
                prompt_templates[template]['total'] += 1
                prompt_templates[template]['correct'] += row['is_correct']
            
            # Classification distribution
            cursor.execute("""
                SELECT 
                    true_classification,
                    COUNT(*) as count
                FROM issues
                WHERE true_classification IS NOT NULL
                GROUP BY true_classification
            """)
            
            classification_dist = {}
            for row in cursor.fetchall():
                classification_dist[row['true_classification']] = row['count']
            
            return {
                'overall_accuracy': {
                    'total': total,
                    'correct': correct,
                    'accuracy': round(correct / total, 4) if total > 0 else 0
                },
                'llm_models': {
                    model: {
                        'total': stats['total'],
                        'correct': stats['correct'],
                        'accuracy': round(stats['correct'] / stats['total'], 4) if stats['total'] > 0 else 0
                    } for model, stats in llm_models.items()
                },
                'context_strategies': {
                    strategy: {
                        'total': stats['total'],
                        'correct': stats['correct'],
                        'accuracy': round(stats['correct'] / stats['total'], 4) if stats['total'] > 0 else 0
                    } for strategy, stats in context_strategies.items()
                },
                'prompt_templates': {
                    template: {
                        'total': stats['total'],
                        'correct': stats['correct'],
                        'accuracy': round(stats['correct'] / stats['total'], 4) if stats['total'] > 0 else 0
                    } for template, stats in prompt_templates.items()
                },
                'classification_distribution': classification_dist
            }
    except sqlite3.Error as e:
        logger.error(f"Failed to get statistics: {e}")
        import traceback
        traceback.print_exc()
        raise

def add_llm_response(
    classification_id: int, 
    full_prompt: str, 
    full_response: str, 
    prompt_tokens: Optional[int] = None, 
    completion_tokens: Optional[int] = None, 
    total_tokens: Optional[int] = None, 
    response_time_ms: Optional[int] = None, 
    model_parameters: Optional[Dict] = None
) -> int:
    """
    Add a record of an LLM interaction to the database.
    
    Args:
        classification_id (int): The ID of the llm_classification this response is linked to.
        full_prompt (str): The complete prompt sent to the LLM.
        full_response (str): The complete raw response received from the LLM.
        prompt_tokens (Optional[int]): Number of tokens in the prompt.
        completion_tokens (Optional[int]): Number of tokens in the completion/response.
        total_tokens (Optional[int]): Total number of tokens used in the interaction.
        response_time_ms (Optional[int]): Response time in milliseconds.
        model_parameters (Optional[Dict]): Dictionary of model parameters used (temperature, etc.).
        
    Returns:
        int: The ID of the new llm_response record.
        
    Raises:
        sqlite3.Error: If a database error occurs.
        ValueError: If the classification_id is invalid.
    """
    # Convert model_parameters dict to JSON string if provided
    model_parameters_json = None
    if model_parameters:
        try:
            model_parameters_json = json.dumps(model_parameters)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize model parameters: {e}")
            # Still continue with the rest of the data
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if the classification_id exists
            cursor.execute("SELECT id FROM llm_classifications WHERE id = ?", (classification_id,))
            if not cursor.fetchone():
                raise ValueError(f"Invalid classification_id: {classification_id}")
            
            cursor.execute("""
                INSERT INTO llm_responses (
                    classification_id, full_prompt, full_response, 
                    prompt_tokens, completion_tokens, total_tokens,
                    response_time_ms, model_parameters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                classification_id,
                full_prompt,
                full_response,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                response_time_ms,
                model_parameters_json
            ))
            
            response_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Added LLM response record {response_id} for classification {classification_id}")
            return response_id
    except sqlite3.Error as e:
        logger.error(f"Failed to add LLM response: {e}")
        raise

def get_llm_responses(filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    Retrieve detailed records of LLM interactions.
    
    Args:
        filters (Optional[Dict]): Dictionary of filter conditions.
            Supported filters: 'classification_id', 'issue_id', 'llm_model_name',
            'date_from', 'date_to', 'min_total_tokens', 'max_total_tokens'.
            
    Returns:
        List[Dict[str, Any]]: List of LLM response records.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    # Start with a base query that joins llm_responses with llm_classifications
    # to get access to issue_id and llm_model_name
    query = """
        SELECT 
            r.id, r.classification_id, r.full_prompt, r.full_response,
            r.prompt_tokens, r.completion_tokens, r.total_tokens,
            r.response_time_ms, r.model_parameters, r.timestamp,
            c.issue_id, c.llm_model_name
        FROM 
            llm_responses r
        JOIN 
            llm_classifications c ON r.classification_id = c.id
    """
    
    conditions = []
    params = []
    
    if filters:
        if 'classification_id' in filters:
            conditions.append("r.classification_id = ?")
            params.append(filters['classification_id'])
        
        if 'issue_id' in filters:
            conditions.append("c.issue_id = ?")
            params.append(filters['issue_id'])
        
        if 'llm_model_name' in filters:
            conditions.append("c.llm_model_name = ?")
            params.append(filters['llm_model_name'])
        
        if 'date_from' in filters:
            if isinstance(filters['date_from'], datetime):
                date_from = filters['date_from']
            else:
                # Assume it's a date object, convert to datetime at start of day
                date_from = datetime.combine(filters['date_from'], datetime.min.time())
            conditions.append("r.timestamp >= ?")
            params.append(date_from)
        
        if 'date_to' in filters:
            if isinstance(filters['date_to'], datetime):
                date_to = filters['date_to']
            else:
                # Assume it's a date object, convert to datetime at end of day
                date_to = datetime.combine(filters['date_to'], datetime.max.time())
            conditions.append("r.timestamp <= ?")
            params.append(date_to)
        
        if 'min_total_tokens' in filters and filters['min_total_tokens'] > 0:
            conditions.append("r.total_tokens >= ?")
            params.append(filters['min_total_tokens'])
        
        if 'max_total_tokens' in filters and filters['max_total_tokens'] < 10000:  # Arbitrary high limit
            conditions.append("r.total_tokens <= ?")
            params.append(filters['max_total_tokens'])
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY r.timestamp DESC"
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            responses = [dict(row) for row in cursor.fetchall()]
            return responses
    except sqlite3.Error as e:
        logger.error(f"Failed to get LLM responses: {e}")
        raise

def get_token_usage_statistics(filters: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Retrieve statistics about token usage across different LLM models and prompt templates.
    
    Args:
        filters (Optional[Dict]): Dictionary of filter conditions.
            Supported filters: Same as get_llm_responses().
            
    Returns:
        Dict[str, Any]: Dictionary with token usage statistics.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        # Get all responses based on filters
        responses = get_llm_responses(filters)
        
        if not responses:
            return {
                'total_interactions': 0,
                'total_tokens': 0,
                'avg_tokens_per_request': 0,
                'avg_response_time_ms': 0
            }
        
        # Calculate overall statistics
        valid_token_responses = [r for r in responses if r.get('total_tokens') is not None]
        valid_time_responses = [r for r in responses if r.get('response_time_ms') is not None]
        
        total_tokens = sum(r.get('total_tokens', 0) for r in valid_token_responses)
        avg_tokens = total_tokens / len(valid_token_responses) if valid_token_responses else 0
        
        avg_response_time = (
            sum(r.get('response_time_ms', 0) for r in valid_time_responses) / len(valid_time_responses)
            if valid_time_responses else 0
        )
        
        # Organize token usage by model
        model_usage = {}
        for r in responses:
            model = r.get('llm_model_name', 'Unknown')
            if model not in model_usage:
                model_usage[model] = {
                    'model': model,
                    'count': 0,
                    'total_tokens': 0,
                    'avg_tokens': 0
                }
            
            model_usage[model]['count'] += 1
            if r.get('total_tokens') is not None:
                model_usage[model]['total_tokens'] += r.get('total_tokens', 0)
        
        # Calculate averages for each model
        for model in model_usage:
            if model_usage[model]['count'] > 0:
                model_usage[model]['avg_tokens'] = (
                    model_usage[model]['total_tokens'] / model_usage[model]['count']
                )
        
        # Get prompt template usage data
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Construct a query to get token usage by prompt template
            query = """
                SELECT 
                    c.prompt_template,
                    COUNT(r.id) as count,
                    AVG(r.total_tokens) as avg_tokens,
                    SUM(r.total_tokens) as total_tokens
                FROM 
                    llm_responses r
                JOIN 
                    llm_classifications c ON r.classification_id = c.id
                WHERE 
                    r.total_tokens IS NOT NULL
            """
            
            conditions = []
            params = []
            
            if filters:
                if 'llm_model_name' in filters:
                    conditions.append("c.llm_model_name = ?")
                    params.append(filters['llm_model_name'])
                
                if 'date_from' in filters:
                    if isinstance(filters['date_from'], datetime):
                        date_from = filters['date_from']
                    else:
                        date_from = datetime.combine(filters['date_from'], datetime.min.time())
                    conditions.append("r.timestamp >= ?")
                    params.append(date_from)
                
                if 'date_to' in filters:
                    if isinstance(filters['date_to'], datetime):
                        date_to = filters['date_to']
                    else:
                        date_to = datetime.combine(filters['date_to'], datetime.max.time())
                    conditions.append("r.timestamp <= ?")
                    params.append(date_to)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " GROUP BY c.prompt_template"
            
            cursor.execute(query, params)
            prompt_template_usage = [dict(row) for row in cursor.fetchall()]
        
        return {
            'total_interactions': len(responses),
            'total_tokens': total_tokens,
            'avg_tokens_per_request': avg_tokens,
            'avg_response_time_ms': avg_response_time,
            'model_token_usage': list(model_usage.values()),
            'prompt_template_token_usage': prompt_template_usage
        }
    except sqlite3.Error as e:
        logger.error(f"Failed to get token usage statistics: {e}")
        raise

def get_all_issue_statuses() -> set:
    """
    Retrieve all unique issue statuses from the database.
    
    Returns:
        set: A set of unique status values.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT status FROM issues")
            statuses = {row['status'] for row in cursor.fetchall()}
            return statuses
    except sqlite3.Error as e:
        logger.error(f"Failed to get issue statuses: {e}")
        raise

def get_all_issue_severities() -> set:
    """
    Retrieve all unique issue severities from the database.
    
    Returns:
        set: A set of unique severity values.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT cppcheck_severity FROM issues")
            severities = {row['cppcheck_severity'] for row in cursor.fetchall()}
            return severities
    except sqlite3.Error as e:
        logger.error(f"Failed to get issue severities: {e}")
        raise

def get_all_issue_cppcheck_ids() -> set:
    """
    Retrieve all unique cppcheck issue IDs from the database.
    
    Returns:
        set: A set of unique cppcheck_id values.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT cppcheck_id FROM issues")
            cppcheck_ids = {row['cppcheck_id'] for row in cursor.fetchall()}
            return cppcheck_ids
    except sqlite3.Error as e:
        logger.error(f"Failed to get cppcheck IDs: {e}")
        raise

def get_issues_by_filters(
    statuses: Optional[set] = None, 
    severities: Optional[set] = None, 
    cppcheck_ids: Optional[set] = None,
    contradictory_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Retrieve issues based on multiple filter criteria.
    
    Args:
        statuses (Optional[set]): Set of status values to filter by.
        severities (Optional[set]): Set of severity values to filter by.
        cppcheck_ids (Optional[set]): Set of cppcheck_id values to filter by.
        contradictory_only (bool): If True, only return issues with contradictory LLM classifications.
            Contradictory means there are multiple classifications with different results.
            
    Returns:
        List[Dict[str, Any]]: List of issue dictionaries matching the criteria.
        
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    query = "SELECT * FROM issues"
    conditions = []
    params = []
    
    # Add filter conditions
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        conditions.append(f"status IN ({placeholders})")
        params.extend(statuses)
        
    if severities:
        placeholders = ", ".join("?" for _ in severities)
        conditions.append(f"cppcheck_severity IN ({placeholders})")
        params.extend(severities)
        
    if cppcheck_ids:
        placeholders = ", ".join("?" for _ in cppcheck_ids)
        conditions.append(f"cppcheck_id IN ({placeholders})")
        params.extend(cppcheck_ids)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY id DESC"
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            issues = [dict(row) for row in cursor.fetchall()]
            
            # Get classifications for each issue
            for issue in issues:
                cursor.execute("""
                    SELECT * FROM llm_classifications WHERE issue_id = ?
                    ORDER BY processing_timestamp DESC
                """, (issue['id'],))
                issue['llm_classifications'] = [dict(row) for row in cursor.fetchall()]
            
            # Filter for contradictory classifications if requested
            if contradictory_only:
                filtered_issues = []
                for issue in issues:
                    classifications = issue.get('llm_classifications', [])
                    
                    # Only include issues with multiple classifications
                    if len(classifications) > 1:
                        # Check if classifications are contradictory
                        unique_classifications = {c['classification'] for c in classifications}
                        if len(unique_classifications) > 1:
                            filtered_issues.append(issue)
                
                return filtered_issues
            
            return issues
    except sqlite3.Error as e:
        logger.error(f"Failed to get issues by filters: {e}")
        raise 