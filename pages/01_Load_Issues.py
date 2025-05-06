"""
Load Issues Page - Allows users to upload a cppcheck CSV file and load issues into the database.
"""

import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime

from core.issue_parser import parse_cppcheck_csv
from core.data_manager import add_issues, get_all_issues

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
    existing_issues = get_all_issues()
    existing_count = len(existing_issues)
except Exception as e:
    st.error(f"Error loading existing issues: {str(e)}")
    existing_count = 0

with tab1:
    # File uploader for CSV
    uploaded_file = st.file_uploader("Upload cppcheck CSV file", type=['csv'])
    
    if uploaded_file is not None:
        # Display uploaded file info
        file_size_kb = round(uploaded_file.size / 1024, 2)
        st.info(f"File uploaded: {uploaded_file.name} ({file_size_kb} KB)")
        
        # Parse button
        if st.button("Parse and Load Issues", key="parse_upload"):
            try:
                # Parse CSV data
                with st.spinner("Parsing issues..."):
                    issues = parse_cppcheck_csv(uploaded_file)
                
                # Show preview of parsed issues
                if issues:
                    st.success(f"Successfully parsed {len(issues)} issues.")
                    
                    # Create DataFrame for display
                    preview_df = pd.DataFrame([{
                        'File': issue['cppcheck_file'],
                        'Line': issue['cppcheck_line'],
                        'Severity': issue['cppcheck_severity'],
                        'ID': issue['cppcheck_id'],
                        'Summary': issue['cppcheck_summary'][:100] + ('...' if len(issue['cppcheck_summary']) > 100 else '')
                    } for issue in issues[:10]])  # Show first 10 for preview
                    
                    st.subheader(f"Preview (first {min(10, len(issues))} of {len(issues)} issues)")
                    st.dataframe(preview_df)
                    
                    # Confirm loading into database
                    if st.button("Confirm and Load into Database", key="confirm_upload"):
                        with st.spinner("Adding issues to database..."):
                            new_ids = add_issues(issues)
                            st.success(f"Successfully added {len(new_ids)} issues to the database.")
                            st.session_state['issues_loaded'] = True
                            
                            # Offer navigation to Run LLM page
                            if st.button("Proceed to Run LLM"):
                                st.switch_page("pages/02_Run_LLM.py")
                else:
                    st.warning("No issues found in the uploaded file.")
            
            except Exception as e:
                st.error(f"Error parsing CSV: {str(e)}")
                import traceback
                traceback.print_exc()

with tab2:
    # Text input for file path
    csv_path = st.text_input("Enter path to cppcheck CSV file", 
                             help="Enter the absolute or relative path to the cppcheck CSV file")
    
    if csv_path:
        # Verify file exists
        if os.path.isfile(csv_path):
            file_size_kb = round(os.path.getsize(csv_path) / 1024, 2)
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(csv_path))
            
            st.info(f"File found: {os.path.basename(csv_path)} ({file_size_kb} KB, last modified: {file_mod_time})")
            
            # Parse button
            if st.button("Parse and Load Issues", key="parse_path"):
                try:
                    # Parse CSV file
                    with st.spinner("Parsing issues..."):
                        issues = parse_cppcheck_csv(csv_path)
                    
                    # Show preview of parsed issues
                    if issues:
                        st.success(f"Successfully parsed {len(issues)} issues.")
                        
                        # Create DataFrame for display
                        preview_df = pd.DataFrame([{
                            'File': issue['cppcheck_file'],
                            'Line': issue['cppcheck_line'],
                            'Severity': issue['cppcheck_severity'],
                            'ID': issue['cppcheck_id'],
                            'Summary': issue['cppcheck_summary'][:100] + ('...' if len(issue['cppcheck_summary']) > 100 else '')
                        } for issue in issues[:10]])  # Show first 10 for preview
                        
                        st.subheader(f"Preview (first {min(10, len(issues))} of {len(issues)} issues)")
                        st.dataframe(preview_df)
                        
                        # Confirm loading into database
                        if st.button("Confirm and Load into Database", key="confirm_path"):
                            with st.spinner("Adding issues to database..."):
                                new_ids = add_issues(issues)
                                st.success(f"Successfully added {len(new_ids)} issues to the database.")
                                st.session_state['issues_loaded'] = True
                                
                                # Offer navigation to Run LLM page
                                if st.button("Proceed to Run LLM"):
                                    st.switch_page("pages/02_Run_LLM.py")
                    else:
                        st.warning("No issues found in the specified file.")
                
                except Exception as e:
                    st.error(f"Error parsing CSV: {str(e)}")
        else:
            st.error(f"File not found: {csv_path}")

# Display existing issues if any
if existing_count > 0:
    st.subheader("Existing Issues")
    
    # Create a DataFrame for display
    existing_df = pd.DataFrame([{
        'ID': issue['id'],
        'File': issue['cppcheck_file'],
        'Line': issue['cppcheck_line'],
        'Severity': issue['cppcheck_severity'],
        'Status': issue['status'],
        'Added': issue['created_at']
    } for issue in existing_issues])
    
    # Group by status and severity for summary
    status_counts = existing_df['Status'].value_counts().reset_index()
    severity_counts = existing_df['Severity'].value_counts().reset_index()
    
    # Display summary metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Issues by Status")
        st.dataframe(status_counts.rename(columns={'index': 'Status', 'Status': 'Count'}))
    
    with col2:
        st.subheader("Issues by Severity")
        st.dataframe(severity_counts.rename(columns={'index': 'Severity', 'Severity': 'Count'}))
    
    # Display the full dataframe with filters
    with st.expander("Show All Issues"):
        # Add filters
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect("Filter by Status", 
                                          options=sorted(existing_df['Status'].unique()),
                                          default=[])
        with col2:
            severity_filter = st.multiselect("Filter by Severity", 
                                            options=sorted(existing_df['Severity'].unique()),
                                            default=[])
        
        # Apply filters
        filtered_df = existing_df
        if status_filter:
            filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
        if severity_filter:
            filtered_df = filtered_df[filtered_df['Severity'].isin(severity_filter)]
        
        # Show dataframe
        st.dataframe(filtered_df) 