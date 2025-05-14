"""
Load Issues Page - Allows users to upload a cppcheck CSV file and load issues into the database.

This page provides two methods for loading cppcheck issues:
1. Upload a CSV file directly through the browser
2. Specify a path to a CSV file on the server

The page also displays statistics about existing issues in the database.
"""

import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional

from core.issue_parser import parse_cppcheck_csv
from core.data_manager import add_issues, get_all_issues, get_issue_count, get_issue_counts_by_status, get_issue_counts_by_severity

# Configure logger
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Load Issues - Review Helper",
    page_icon="📂",
    layout="wide"
)

# Page title
st.title("Load cppcheck Issues")
st.markdown("Upload a cppcheck CSV file or provide a path to load issues into the database.")

# Define file upload tab and file path tab
tab1, tab2 = st.tabs(["Upload CSV File", "Specify CSV Path"])

# Get existing issues for reference
try:
    logger.debug("Fetching existing issues count from database")
    existing_count = get_issue_count()
    logger.info(f"Found {existing_count} existing issues in database")
except Exception as e:
    logger.error(f"Failed to load existing issues count: {str(e)}", exc_info=True)
    st.error(f"Error loading existing issues count: {str(e)}")
    existing_count = 0

def parse_and_preview_issues(source: Any, is_file_path: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Parse issues from source and display a preview.
    
    Args:
        source: Either a file-like object or a file path
        is_file_path: Whether the source is a file path
        
    Returns:
        List of parsed issues or None if parsing failed
    """
    try:
        with st.spinner("Parsing issues..."):
            logger.debug(f"Parsing issues from {'file path' if is_file_path else 'uploaded file'}")
            issues = parse_cppcheck_csv(source)
            
        if not issues:
            logger.warning("No issues found in the source")
            st.warning("No issues found in the source file.")
            return None
            
        logger.info(f"Successfully parsed {len(issues)} issues")
        st.success(f"Successfully parsed {len(issues)} issues.")
        
        # Create DataFrame for display
        preview_count = min(10, len(issues))
        preview_data = issues[:preview_count] if preview_count < len(issues) else issues
        
        preview_df = pd.DataFrame([{
            'File': issue['cppcheck_file'],
            'Line': issue['cppcheck_line'],
            'Severity': issue['cppcheck_severity'],
            'ID': issue['cppcheck_id'],
            'Summary': issue['cppcheck_summary'][:100] + ('...' if len(issue['cppcheck_summary']) > 100 else '')
        } for issue in preview_data])
        
        st.subheader(f"Preview (first {preview_count} of {len(issues)} issues)")
        st.dataframe(preview_df)
        
        return issues
        
    except Exception as e:
        logger.error(f"Error parsing CSV: {str(e)}", exc_info=True)
        st.error(f"Error parsing CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def load_issues_to_database(issues: List[Dict[str, Any]]) -> None:
    """Load parsed issues into the database.
    
    Args:
        issues: List of parsed issues to add to the database
    """
    try:
        with st.spinner("Adding issues to database..."):
            logger.debug(f"Adding {len(issues)} issues to database")
            new_ids = add_issues(issues)
            logger.info(f"Successfully added {len(new_ids)} issues to database")
            st.success(f"Successfully added {len(new_ids)} issues to the database.")
            st.session_state['issues_loaded'] = True
            
            # Create button to navigate to Run LLM page
            if st.button("Proceed to Run LLM"):
                logger.debug("Navigating to Run LLM page")
                st.switch_page("pages/02_Run_LLM.py")
    except Exception as e:
        logger.error(f"Error adding issues to database: {str(e)}", exc_info=True)
        st.error(f"Error adding issues to database: {str(e)}")
        import traceback
        traceback.print_exc()

def on_parse_upload_click():
    """Callback for parsing uploaded file"""
    logger.debug("Parse and load button clicked for uploaded file")
    if uploaded_file is not None:
        issues = parse_and_preview_issues(uploaded_file)
        if issues:
            st.session_state['upload_issues'] = issues
            st.button("Confirm and Load into Database", key="confirm_upload", on_click=on_confirm_upload_click)

def on_confirm_upload_click():
    """Callback for confirming upload to database"""
    logger.debug("Confirm and load button clicked for uploaded file")
    if 'upload_issues' in st.session_state:
        load_issues_to_database(st.session_state['upload_issues'])

def on_parse_path_click():
    """Callback for parsing file from path"""
    logger.debug(f"Parse and load button clicked for file path: {csv_path}")
    if os.path.isfile(csv_path):
        issues = parse_and_preview_issues(csv_path, is_file_path=True)
        if issues:
            st.session_state['path_issues'] = issues
            st.button("Confirm and Load into Database", key="confirm_path", on_click=on_confirm_path_click)

def on_confirm_path_click():
    """Callback for confirming path-based issues to database"""
    logger.debug("Confirm and load button clicked for file path")
    if 'path_issues' in st.session_state:
        load_issues_to_database(st.session_state['path_issues'])

# Tab 1: Upload CSV File
with tab1:
    # File uploader for CSV
    uploaded_file = st.file_uploader("Upload cppcheck CSV file", type=['csv'])
    
    if uploaded_file is not None:
        # Display uploaded file info
        file_size_kb = round(uploaded_file.size / 1024, 2)
        logger.debug(f"File uploaded: {uploaded_file.name} ({file_size_kb} KB)")
        st.info(f"File uploaded: {uploaded_file.name} ({file_size_kb} KB)")
        
        # Parse button with callback
        st.button("Parse and Load Issues", key="parse_upload", on_click=on_parse_upload_click)

# Tab 2: Specify CSV Path
with tab2:
    # Text input for file path
    csv_path = st.text_input("Enter path to cppcheck CSV file", 
                             help="Enter the absolute or relative path to the cppcheck CSV file")
    
    if csv_path:
        # Verify file exists
        if os.path.isfile(csv_path):
            file_size_kb = round(os.path.getsize(csv_path) / 1024, 2)
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(csv_path))
            
            logger.debug(f"File found: {os.path.basename(csv_path)} ({file_size_kb} KB, last modified: {file_mod_time})")
            st.info(f"File found: {os.path.basename(csv_path)} ({file_size_kb} KB, last modified: {file_mod_time})")
            
            # Parse button with callback
            st.button("Parse and Load Issues", key="parse_path", on_click=on_parse_path_click)
        else:
            logger.warning(f"File not found: {csv_path}")
            st.error(f"File not found: {csv_path}")

# Display existing issues if any
if existing_count > 0:
    st.subheader("Existing Issues")
    logger.debug("Preparing to display existing issues summary")
    
    # Get status and severity counts directly from the database
    status_counts_dict = get_issue_counts_by_status()
    severity_counts_dict = get_issue_counts_by_severity()
    
    # Convert to DataFrame for display
    status_counts_df = pd.DataFrame([
        {"Status": status, "Count": count} 
        for status, count in status_counts_dict.items()
    ])
    
    severity_counts_df = pd.DataFrame([
        {"Severity": severity, "Count": count} 
        for severity, count in severity_counts_dict.items()
    ])
    
    logger.debug(f"Status counts: {status_counts_dict}")
    logger.debug(f"Severity counts: {severity_counts_dict}")
    
    # Display summary metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Issues by Status")
        st.dataframe(status_counts_df)
    
    with col2:
        st.subheader("Issues by Severity")
        st.dataframe(severity_counts_df)
    
    # Display the full dataframe with filters
    with st.expander("Show All Issues"):
        # Get issues data for the dataframe
        all_issues = get_all_issues()
        
        # Create a DataFrame for display
        existing_df = pd.DataFrame([{
            'ID': issue['id'],
            'File': issue['cppcheck_file'],
            'Line': issue['cppcheck_line'],
            'Severity': issue['cppcheck_severity'],
            'Status': issue['status'],
            'Added': issue['created_at']
        } for issue in all_issues])
        
        # Add filters
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect("Filter by Status", 
                                          options=sorted(status_counts_dict.keys()),
                                          default=[])
        with col2:
            severity_filter = st.multiselect("Filter by Severity", 
                                            options=sorted(severity_counts_dict.keys()),
                                            default=[])
        
        # Apply filters
        filtered_df = existing_df
        if status_filter:
            logger.debug(f"Filtering by status: {status_filter}")
            filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
        if severity_filter:
            logger.debug(f"Filtering by severity: {severity_filter}")
            filtered_df = filtered_df[filtered_df['Severity'].isin(severity_filter)]
        
        logger.debug(f"Displaying {len(filtered_df)} issues after filtering")
        # Show dataframe
        st.dataframe(filtered_df)