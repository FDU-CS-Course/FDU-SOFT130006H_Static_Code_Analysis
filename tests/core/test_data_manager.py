"""
Unit tests for the data_manager module.

This test suite verifies the functionality of the data_manager.py module,
which handles database interactions for the Review Helper application.
"""

import os
import sys
import unittest
import sqlite3
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from datetime import datetime, timedelta

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core import data_manager


class TestDataManager(unittest.TestCase):
    """Test class for data_manager module."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for the test database
        self.test_dir = tempfile.mkdtemp()
        
        # Patch the DB_DIR and DB_PATH constants to use the temporary directory
        self.db_dir_patcher = patch('core.data_manager.DB_DIR', self.test_dir)
        self.db_dir_mock = self.db_dir_patcher.start()
        
        self.db_path_patcher = patch('core.data_manager.DB_PATH', 
                                    os.path.join(self.test_dir, 'test_issues.db'))
        self.db_path_mock = self.db_path_patcher.start()
        
        # Initialize the test database
        data_manager.init_db()
        
        # Sample test data
        self.sample_issues = [
            {
                'file': 'src/main.cpp',
                'line': 42,
                'severity': 'warning',
                'id': 'nullPointer',
                'summary': 'Possible null pointer dereference: ptr'
            },
            {
                'file': 'src/utils.cpp',
                'line': 101,
                'severity': 'error',
                'id': 'arrayIndexOutOfBounds',
                'summary': 'Array index out of bounds'
            }
        ]
        
    def tearDown(self):
        """Clean up after each test."""
        # Stop the patchers
        self.db_dir_patcher.stop()
        self.db_path_patcher.stop()
        
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_init_db(self):
        """Test database initialization."""
        # The init_db method is already called in setUp
        # Verify that the database file exists
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'test_issues.db')))
        
        # Verify that the tables were created
        with data_manager.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if issues table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='issues'
            """)
            self.assertIsNotNone(cursor.fetchone())
            
            # Check if llm_classifications table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='llm_classifications'
            """)
            self.assertIsNotNone(cursor.fetchone())
            
            # Check if the trigger exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='trigger' AND name='update_issues_timestamp'
            """)
            self.assertIsNotNone(cursor.fetchone())
    
    def test_add_issues(self):
        """Test adding issues to the database."""
        # Add the sample issues
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Verify that the correct number of IDs were returned
        self.assertEqual(len(issue_ids), len(self.sample_issues))
        
        # Verify that the issues were added correctly
        with data_manager.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM issues")
            count = cursor.fetchone()[0]
            self.assertEqual(count, len(self.sample_issues))
            
            # Check the content of the first issue
            cursor.execute("SELECT * FROM issues WHERE id = ?", (issue_ids[0],))
            issue = dict(cursor.fetchone())
            self.assertEqual(issue['cppcheck_file'], self.sample_issues[0]['file'])
            self.assertEqual(issue['cppcheck_line'], self.sample_issues[0]['line'])
            self.assertEqual(issue['cppcheck_severity'], self.sample_issues[0]['severity'])
            self.assertEqual(issue['cppcheck_id'], self.sample_issues[0]['id'])
            self.assertEqual(issue['cppcheck_summary'], self.sample_issues[0]['summary'])
            self.assertEqual(issue['status'], 'pending_llm')
    
    def test_add_issues_missing_fields(self):
        """Test adding issues with missing required fields."""
        # Create an issue with missing fields
        invalid_issue = {
            'file': 'src/main.cpp',
            'line': 42,
            # Missing 'severity'
            'id': 'nullPointer',
            'summary': 'Possible null pointer dereference: ptr'
        }
        
        # Verify that ValueError is raised
        with self.assertRaises(ValueError):
            data_manager.add_issues([invalid_issue])
    
    def test_get_issue_by_id(self):
        """Test retrieving an issue by ID."""
        # Add sample issues
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Retrieve the first issue
        issue = data_manager.get_issue_by_id(issue_ids[0])
        
        # Verify the issue data
        self.assertIsNotNone(issue)
        self.assertEqual(issue['id'], issue_ids[0])
        self.assertEqual(issue['cppcheck_file'], self.sample_issues[0]['file'])
        self.assertEqual(issue['cppcheck_line'], self.sample_issues[0]['line'])
        self.assertEqual(issue['cppcheck_severity'], self.sample_issues[0]['severity'])
        self.assertEqual(issue['cppcheck_id'], self.sample_issues[0]['id'])
        self.assertEqual(issue['cppcheck_summary'], self.sample_issues[0]['summary'])
        self.assertEqual(issue['status'], 'pending_llm')
        self.assertEqual(issue['llm_classifications'], [])
    
    def test_get_nonexistent_issue(self):
        """Test retrieving an issue that doesn't exist."""
        # Attempt to retrieve a non-existent issue
        issue = data_manager.get_issue_by_id(999)
        
        # Verify that None is returned
        self.assertIsNone(issue)
    
    def test_get_all_issues(self):
        """Test retrieving all issues."""
        # Add sample issues
        data_manager.add_issues(self.sample_issues)
        
        # Retrieve all issues
        issues = data_manager.get_all_issues()
        
        # Verify the correct number of issues are returned
        self.assertEqual(len(issues), len(self.sample_issues))
    
    def test_get_filtered_issues(self):
        """Test retrieving issues with filters."""
        # Add sample issues
        data_manager.add_issues(self.sample_issues)
        
        # Filter issues by severity
        filters = {'severity': 'error'}
        issues = data_manager.get_all_issues(filters)
        
        # Verify that only error issues are returned
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['cppcheck_severity'], 'error')
    
    def test_add_llm_classification(self):
        """Test adding an LLM classification."""
        # Add sample issues
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Add an LLM classification for the first issue
        classification_id = data_manager.add_llm_classification(
            issue_id=issue_ids[0],
            llm_model_name='gpt-4',
            context_strategy='fixed_lines',
            prompt_template='classification_default.txt',
            source_code_context='void func() { int* ptr = nullptr; *ptr = 42; }',
            classification='false positive',
            explanation='This is a false positive because the code is unreachable.'
        )
        
        # Verify the classification was added
        self.assertIsNotNone(classification_id)
        
        # Verify the issue status was updated
        issue = data_manager.get_issue_by_id(issue_ids[0])
        self.assertEqual(issue['status'], 'pending_review')
        self.assertEqual(len(issue['llm_classifications']), 1)
        
        # Verify the classification data
        classification = issue['llm_classifications'][0]
        self.assertEqual(classification['llm_model_name'], 'gpt-4')
        self.assertEqual(classification['context_strategy'], 'fixed_lines')
        self.assertEqual(classification['prompt_template'], 'classification_default.txt')
        self.assertEqual(classification['classification'], 'false positive')
        self.assertEqual(classification['explanation'], 'This is a false positive because the code is unreachable.')
    
    def test_add_classification_nonexistent_issue(self):
        """Test adding a classification for a non-existent issue."""
        # Attempt to add a classification for a non-existent issue
        with self.assertRaises(ValueError):
            data_manager.add_llm_classification(
                issue_id=999,
                llm_model_name='gpt-4',
                context_strategy='fixed_lines',
                prompt_template='classification_default.txt',
                source_code_context='code sample',
                classification='false positive'
            )
    
    def test_update_llm_classification_review(self):
        """Test updating user feedback for an LLM classification."""
        # Add sample issues and a classification
        issue_ids = data_manager.add_issues(self.sample_issues)
        classification_id = data_manager.add_llm_classification(
            issue_id=issue_ids[0],
            llm_model_name='gpt-4',
            context_strategy='fixed_lines',
            prompt_template='classification_default.txt',
            source_code_context='void func() { int* ptr = nullptr; *ptr = 42; }',
            classification='false positive'
        )
        
        # Update the classification with user feedback
        success = data_manager.update_llm_classification_review(
            classification_id=classification_id,
            user_agrees=True,
            user_comment='Good analysis'
        )
        
        # Verify the update was successful
        self.assertTrue(success)
        
        # Verify the classification was updated
        issue = data_manager.get_issue_by_id(issue_ids[0])
        classification = issue['llm_classifications'][0]
        self.assertEqual(classification['user_agrees'], 1)  # SQLite stores booleans as 0/1
        self.assertEqual(classification['user_comment'], 'Good analysis')
    
    def test_update_nonexistent_classification(self):
        """Test updating a non-existent classification."""
        # Attempt to update a non-existent classification
        success = data_manager.update_llm_classification_review(
            classification_id=999,
            user_agrees=True
        )
        
        # Verify the update failed
        self.assertFalse(success)
    
    def test_set_issue_true_classification(self):
        """Test setting the final classification for an issue."""
        # Add sample issues
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Set the true classification
        success = data_manager.set_issue_true_classification(
            issue_id=issue_ids[0],
            classification='need fixing',
            comment='This should be fixed in the next sprint.'
        )
        
        # Verify the update was successful
        self.assertTrue(success)
        
        # Verify the issue was updated
        issue = data_manager.get_issue_by_id(issue_ids[0])
        self.assertEqual(issue['true_classification'], 'need fixing')
        self.assertEqual(issue['true_classification_comment'], 'This should be fixed in the next sprint.')
        self.assertEqual(issue['status'], 'reviewed')
    
    def test_set_invalid_classification(self):
        """Test setting an invalid classification."""
        # Add sample issues
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Attempt to set an invalid classification
        with self.assertRaises(ValueError):
            data_manager.set_issue_true_classification(
                issue_id=issue_ids[0],
                classification='invalid_classification'
            )
    
    def test_set_classification_nonexistent_issue(self):
        """Test setting classification for a non-existent issue."""
        # Attempt to set classification for a non-existent issue
        success = data_manager.set_issue_true_classification(
            issue_id=999,
            classification='false positive'
        )
        
        # Verify the update failed
        self.assertFalse(success)
    
    def test_get_llm_statistics(self):
        """Test retrieving LLM statistics."""
        # Add sample issues
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Add classifications with different LLMs, context strategies, and templates
        data_manager.add_llm_classification(
            issue_id=issue_ids[0],
            llm_model_name='gpt-4',
            context_strategy='fixed_lines',
            prompt_template='template1',
            source_code_context='code1',
            classification='false positive'
        )
        
        data_manager.add_llm_classification(
            issue_id=issue_ids[1],
            llm_model_name='gpt-3.5',
            context_strategy='function_scope',
            prompt_template='template2',
            source_code_context='code2',
            classification='need fixing'
        )
        
        # Set true classifications
        data_manager.set_issue_true_classification(
            issue_id=issue_ids[0],
            classification='false positive'
        )
        
        data_manager.set_issue_true_classification(
            issue_id=issue_ids[1],
            classification='very serious'
        )
        
        # Get statistics
        stats = data_manager.get_llm_statistics()
        
        # Verify the statistics structure
        self.assertIn('overall_accuracy', stats)
        self.assertIn('llm_models', stats)
        self.assertIn('context_strategies', stats)
        self.assertIn('prompt_templates', stats)
        self.assertIn('classification_distribution', stats)
        
        # Verify the overall accuracy
        self.assertEqual(stats['overall_accuracy']['total'], 2)
        self.assertEqual(stats['overall_accuracy']['correct'], 1)
        self.assertEqual(stats['overall_accuracy']['accuracy'], 0.5)
        
        # Verify LLM model statistics
        self.assertIn('gpt-4', stats['llm_models'])
        self.assertIn('gpt-3.5', stats['llm_models'])
        self.assertEqual(stats['llm_models']['gpt-4']['accuracy'], 1.0)
        self.assertEqual(stats['llm_models']['gpt-3.5']['accuracy'], 0.0)
        
        # Verify context strategy statistics
        self.assertIn('fixed_lines', stats['context_strategies'])
        self.assertIn('function_scope', stats['context_strategies'])
        
        # Verify prompt template statistics
        self.assertIn('template1', stats['prompt_templates'])
        self.assertIn('template2', stats['prompt_templates'])
        
        # Verify classification distribution
        self.assertEqual(stats['classification_distribution']['false positive'], 1)
        self.assertEqual(stats['classification_distribution']['very serious'], 1)
    
    def test_get_llm_statistics_with_filters(self):
        """Test retrieving LLM statistics with filters."""
        # Add sample issues and classifications as in the previous test
        issue_ids = data_manager.add_issues(self.sample_issues)
        
        # Add classifications
        data_manager.add_llm_classification(
            issue_id=issue_ids[0],
            llm_model_name='gpt-4',
            context_strategy='fixed_lines',
            prompt_template='template1',
            source_code_context='code1',
            classification='false positive'
        )
        
        data_manager.add_llm_classification(
            issue_id=issue_ids[1],
            llm_model_name='gpt-3.5',
            context_strategy='function_scope',
            prompt_template='template2',
            source_code_context='code2',
            classification='need fixing'
        )
        
        # Set true classifications
        data_manager.set_issue_true_classification(
            issue_id=issue_ids[0],
            classification='false positive'
        )
        
        data_manager.set_issue_true_classification(
            issue_id=issue_ids[1],
            classification='very serious'
        )
        
        # Get statistics with filters
        stats = data_manager.get_llm_statistics({
            'llm_model_name': 'gpt-4'
        })
        
        # Verify the filtered statistics
        self.assertEqual(len(stats['llm_models']), 1)
        self.assertIn('gpt-4', stats['llm_models'])
        self.assertNotIn('gpt-3.5', stats['llm_models'])
        
        # Test with multiple filters
        stats = data_manager.get_llm_statistics({
            'context_strategy': 'fixed_lines',
            'prompt_template': 'template1'
        })
        
        # Verify the filtered statistics
        self.assertEqual(len(stats['context_strategies']), 1)
        self.assertIn('fixed_lines', stats['context_strategies'])
        self.assertEqual(len(stats['prompt_templates']), 1)
        self.assertIn('template1', stats['prompt_templates'])


if __name__ == '__main__':
    unittest.main() 