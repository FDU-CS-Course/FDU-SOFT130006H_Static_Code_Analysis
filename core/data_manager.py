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

import os
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
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
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_ISSUES_TABLE)
            cursor.execute(CREATE_LLM_CLASSIFICATIONS_TABLE)
            cursor.execute(CREATE_UPDATE_TRIGGER)
            conn.commit()
            logger.info("Database initialized successfully.")
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
    required_fields = ['file', 'line', 'severity', 'id', 'summary']
    
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
                    issue['file'], 
                    issue['line'], 
                    issue['severity'], 
                    issue['id'], 
                    issue['summary'],
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

def add_llm_classification(
    issue_id: int, 
    llm_model_name: str, 
    context_strategy: str, 
    prompt_template: str, 
    source_code_context: str, 
    classification: str, 
    explanation: Optional[str] = None
) -> int:
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
        
    Returns:
        int: ID of the newly created classification.
        
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
                FROM llm_classifications lc
                JOIN issues i ON lc.issue_id = i.id
                WHERE i.true_classification IS NOT NULL
                {' AND ' + ' AND '.join(f"lc.{k} = ?" for k in filters.keys()) if filters else ''}
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
        raise 