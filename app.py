"""
Review Helper - A tool for classifying and reviewing cppcheck issues using LLMs.

This is the main application entry point.
"""

import os
import streamlit as st
from core.data_manager import init_db, get_issues_summary, get_all_issues, get_issue_count
import config

# Page configuration
st.set_page_config(
    page_title="Review Helper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure database is initialized
init_db()

# Sidebar content
with st.sidebar:
    st.title("Review Helper")
    st.markdown("A tool for classifying cppcheck issues using LLMs.")
    
    # Project root directory configuration
    st.subheader("Project Configuration")
    if not config.PROJECT_ROOT_DIR:
        st.warning("⚠️ Project root directory not set. Please set the REVIEW_HELPER_PROJECT_ROOT environment variable.")
    else:
        st.success(f"✅ Project root directory: {config.PROJECT_ROOT_DIR}")
    
    # Display issue counts
    st.subheader("Issue Summary")
    try:
        # Get issue summary from database - more efficient than loading all issues
        summary = get_issues_summary()
        
        # Display metrics using database-computed values
        st.metric("Total Issues", summary['total'])
        st.metric("Pending LLM", summary['by_status'].get('pending_llm', 0))
        st.metric("Pending Review", summary['by_status'].get('pending_review', 0))
        st.metric("Reviewed", summary['by_status'].get('reviewed', 0))
    except Exception as e:
        st.error(f"Error loading issue statistics: {str(e)}")

# Main page content
st.title("Welcome to Review Helper")
st.markdown("""
Review Helper is a tool designed to help developers classify and review cppcheck issues
by leveraging Large Language Models (LLMs).

### How to use:
1. **Load Issues**: Upload a cppcheck CSV file or specify its path
2. **Run LLM**: Select an LLM and prompt template to classify issues
3. **Review Issues**: Review LLM classifications and provide feedback
4. **Statistics**: View statistics about LLM performance and issue distribution

Use the sidebar navigation to access these pages.
""")

# Display info if no project root is set
if not config.PROJECT_ROOT_DIR:
    st.info("Before starting, set the REVIEW_HELPER_PROJECT_ROOT environment variable to the root directory of your C++ project.")
    
    # Example for setting environment variable
    st.markdown("### Example:")
    st.code("export REVIEW_HELPER_PROJECT_ROOT=/path/to/your/cpp/project", language="bash")
    
# Check if database exists but has no issues
try:
    issue_count = get_issue_count()
    if issue_count == 0:
        st.info("No issues found in the database. Start by loading issues from a cppcheck CSV file.")
        
        # Add a button to navigate to the load issues page
        if st.button("Go to Load Issues"):
            st.switch_page("pages/01_Load_Issues.py")
except Exception as e:
    st.error(f"Error checking database: {str(e)}") 