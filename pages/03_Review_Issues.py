"""
Review Issues Page - Allows users to review LLM classifications and provide feedback.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional

from core.data_manager import (
    get_issue_by_id,
    update_llm_classification_review,
    set_issue_true_classification,
    get_all_issue_statuses,
    get_all_issue_severities,
    get_all_issue_cppcheck_ids,
    get_issues_by_filters
)

# Page configuration
st.set_page_config(
    page_title="Review Issues - Review Helper",
    page_icon="✓",
    layout="wide"
)

# Page title
st.title("Review Issues")
st.markdown("Review LLM classifications and provide feedback.")

# Session state for issue navigation
if 'current_issue_index' not in st.session_state:
    st.session_state.current_issue_index = 0
if 'filter_settings' not in st.session_state:
    st.session_state.filter_settings = {
        'status': ['pending_review'],
        'severity': [],
        'id': None,
        'cppcheck_id': [],
        'show_contradictory': False
    }

# Filter sidebar
with st.sidebar:
    st.subheader("Filter Issues")
    
    try:
        # Get all the unique values for filter dropdowns from the database
        status_options = list(get_all_issue_statuses())
        
        # Status filter
        selected_status = st.multiselect(
            "Issue Status",
            options=status_options,
            default=st.session_state.filter_settings['status']
        )
        
        # Get all severity values directly from the database
        severity_options = list(get_all_issue_severities())
        
        # Severity filter
        selected_severity = st.multiselect(
            "Issue Severity",
            options=severity_options,
            default=st.session_state.filter_settings['severity']
        )
        
        # Specific issue ID filter
        specific_issue = st.text_input(
            "Specific Issue ID",
            value=st.session_state.filter_settings['id'] if st.session_state.filter_settings['id'] else "",
            help="Enter an issue ID to view only that issue"
        )
        
        specific_issue_id = int(specific_issue) if specific_issue and specific_issue.isdigit() else None
        
        # Get all cppcheck IDs directly from the database
        cppcheck_ids = list(get_all_issue_cppcheck_ids())
        
        # Select cppcheck IDs filter
        selected_cppcheck_ids = st.multiselect(
            "Select cppcheck IDs",
            options=cppcheck_ids,
            default=st.session_state.filter_settings['cppcheck_id'] if isinstance(st.session_state.filter_settings['cppcheck_id'], list) else [],
            help="Select one or more cppcheck IDs (e.g., 'zerodiv', 'nullPointer') to filter issues"
        )
        
        specific_cppcheck_id_value = selected_cppcheck_ids if selected_cppcheck_ids else None
        
        # Contradictory classifications filter
        show_contradictory = st.checkbox(
            "Show Issues with Contradictory Classifications",
            value=st.session_state.filter_settings.get('show_contradictory', False),
            help="Show only issues that have contradicting LLM classifications"
        )
        
        # Update filter settings
        st.session_state.filter_settings = {
            'status': selected_status,
            'severity': selected_severity,
            'id': specific_issue_id,
            'cppcheck_id': specific_cppcheck_id_value,
            'show_contradictory': show_contradictory
        }
        
        # Filter issues using the database-level filtering API
        if specific_issue_id is not None:
            # If specific issue ID is provided, get that issue directly
            specific_issue_data = get_issue_by_id(specific_issue_id)
            filtered_issues = [specific_issue_data] if specific_issue_data else []
        else:
            # Otherwise, use the filtering API
            filtered_issues = get_issues_by_filters(
                statuses=set(selected_status) if selected_status else None,
                severities=set(selected_severity) if selected_severity else None,
                cppcheck_ids={specific_cppcheck_id_value} if specific_cppcheck_id_value else None,
                contradictory_only=show_contradictory
            )
        
        # Display filtered count
        st.info(f"Found {len(filtered_issues)} issues matching filters")
        
        # Issue navigation
        if filtered_issues:
            st.subheader("Issue Navigation")
            
            # Previous/Next buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Previous Issue", key="prev_issue", disabled=st.session_state.current_issue_index <= 0):
                    st.session_state.current_issue_index = max(0, st.session_state.current_issue_index - 1)
            
            with col2:
                if st.button("Next Issue", key="next_issue", disabled=st.session_state.current_issue_index >= len(filtered_issues) - 1):
                    st.session_state.current_issue_index = min(len(filtered_issues) - 1, st.session_state.current_issue_index + 1)
            
            # Current issue indicator
            st.text(f"Viewing issue {st.session_state.current_issue_index + 1} of {len(filtered_issues)}")
            
            # Jump to issue selector
            jump_to = st.selectbox(
                "Jump to Issue",
                options=[f"ID {issue['id']}: {issue['cppcheck_file']}:{issue['cppcheck_line']}" 
                         for issue in filtered_issues],
                index=st.session_state.current_issue_index
            )
            
            # Update current issue index when jumping
            if jump_to:
                issue_index = [f"ID {issue['id']}: {issue['cppcheck_file']}:{issue['cppcheck_line']}" 
                              for issue in filtered_issues].index(jump_to)
                st.session_state.current_issue_index = issue_index
    
    except Exception as e:
        st.error(f"Error loading issues: {str(e)}")
        filtered_issues = []

# Main content - Display current issue
if filtered_issues:
    # Adjust current_issue_index if out of bounds
    if st.session_state.current_issue_index >= len(filtered_issues):
        st.session_state.current_issue_index = 0

    # Get current issue
    current_issue = filtered_issues[st.session_state.current_issue_index]
    
    # Get complete issue details with classifications if not already loaded
    # (This ensures we have full details when using filtered_issues from get_issues_by_filters)
    if 'llm_classifications' not in current_issue:
        detailed_issue = get_issue_by_id(current_issue['id'])
    else:
        detailed_issue = current_issue
    
    if not detailed_issue:
        st.error(f"Error retrieving detailed information for issue {current_issue['id']}")
    else:
        # Display issue details
        st.subheader("Issue Details")
        
        # Issue info in columns
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**ID:** {detailed_issue['id']}")
            st.markdown(f"**File:** {detailed_issue['cppcheck_file']}")
            st.markdown(f"**Line:** {detailed_issue['cppcheck_line']}")
        
        with col2:
            st.markdown(f"**Severity:** {detailed_issue['cppcheck_severity']}")
            st.markdown(f"**Issue ID:** {detailed_issue['cppcheck_id']}")
            st.markdown(f"**Status:** {detailed_issue['status']}")
        
        with col3:
            st.markdown(f"**Created:** {detailed_issue['created_at']}")
            st.markdown(f"**Last Updated:** {detailed_issue['updated_at']}")
            if detailed_issue['true_classification']:
                st.markdown(f"**True Classification:** {detailed_issue['true_classification']}")
        
        # Full issue summary
        st.subheader("Issue Summary")
        st.markdown(f"**{detailed_issue['cppcheck_summary']}**")
        
        # Display code context from the most recent LLM classification
        if 'llm_classifications' in detailed_issue and detailed_issue['llm_classifications']:
            latest_classification = detailed_issue['llm_classifications'][0]  # Assume the first is the most recent
            
            st.subheader("Code Context")
            st.code(latest_classification['source_code_context'], language="cpp")
            
            # If there are contradictory classifications, highlight this
            if st.session_state.filter_settings.get('show_contradictory', False):
                classifications = [cls['classification'] for cls in detailed_issue['llm_classifications']]
                if len(set(classifications)) > 1:
                    st.warning("⚠️ This issue has contradictory classifications from different LLM models")
                    
                    # Show a summary of the contradictions
                    classification_counts = {}
                    for cls in classifications:
                        if cls in classification_counts:
                            classification_counts[cls] += 1
                        else:
                            classification_counts[cls] = 1
                    
                    st.markdown("**Classification Distribution:**")
                    for cls, count in classification_counts.items():
                        st.markdown(f"- {cls}: {count} model(s)")
        
        # Display LLM classifications
        st.subheader("LLM Classifications")
        
        if 'llm_classifications' in detailed_issue and detailed_issue['llm_classifications']:
            for i, classification in enumerate(detailed_issue['llm_classifications']):
                with st.expander(f"Classification #{i+1} - {classification['llm_model_name']} - {classification['processing_timestamp']}"):
                    # Classification details
                    st.markdown(f"**Model:** {classification['llm_model_name']}")
                    st.markdown(f"**Prompt Template:** {classification['prompt_template']}")
                    st.markdown(f"**Context Strategy:** {classification['context_strategy']}")
                    st.markdown(f"**Classification:** {classification['classification']}")
                    
                    # Explanation collapsible
                    if classification['explanation']:
                        st.markdown("**Explanation:**")
                        st.markdown(classification['explanation'])
                    
                    # User feedback section
                    st.markdown("---")
                    st.markdown("**Your Feedback:**")
                    
                    # Check if user already provided feedback
                    has_feedback = classification['user_agrees'] is not None
                    
                    if has_feedback:
                        # Display existing feedback
                        agrees_text = "Agree ✓" if classification['user_agrees'] else "Disagree ✗"
                        st.info(f"You marked this classification as: {agrees_text}")
                        
                        if classification['user_comment']:
                            st.markdown(f"Your comment: {classification['user_comment']}")
                        
                        # Allow updating feedback
                        if st.button("Update Feedback", key=f"update_fb_{classification['id']}"):
                            st.session_state[f"edit_fb_{classification['id']}"] = True
                    
                    # Show feedback form if new or update requested
                    if not has_feedback or st.session_state.get(f"edit_fb_{classification['id']}", False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            agrees = st.radio(
                                "Do you agree with this classification?",
                                options=["Agree", "Disagree"],
                                index=0 if classification.get('user_agrees', True) else 1,
                                key=f"agrees_{classification['id']}"
                            )
                        
                        user_comment = st.text_area(
                            "Comments (optional)",
                            value=classification.get('user_comment', ''),
                            key=f"comment_{classification['id']}"
                        )
                        
                        if st.button("Submit Feedback", key=f"submit_{classification['id']}"):
                            try:
                                user_agrees = agrees == "Agree"
                                update_successful = update_llm_classification_review(
                                    classification_id=classification['id'],
                                    user_agrees=user_agrees,
                                    user_comment=user_comment if user_comment else None
                                )
                                
                                if update_successful:
                                    st.success("Feedback submitted successfully!")
                                    # Remove edit state if it exists
                                    if f"edit_fb_{classification['id']}" in st.session_state:
                                        del st.session_state[f"edit_fb_{classification['id']}"]
                                    
                                    # Refresh the page to show the updated feedback
                                    st.experimental_rerun()
                                else:
                                    st.error("Failed to submit feedback. Please try again.")
                            except Exception as e:
                                st.error(f"Error submitting feedback: {str(e)}")
        else:
            st.info("No LLM classifications found for this issue. Run LLM analysis first.")
        
        # True classification section
        st.subheader("Final Classification")
        
        # Show current true classification if exists
        if detailed_issue['true_classification']:
            st.info(f"Current classification: **{detailed_issue['true_classification']}**")
            
            if detailed_issue['true_classification_comment']:
                st.markdown(f"Comment: {detailed_issue['true_classification_comment']}")
            
            # Option to update
            if st.button("Update Final Classification"):
                st.session_state['editing_final_classification'] = True
        
        # Show classification form if not set or update requested
        if not detailed_issue['true_classification'] or st.session_state.get('editing_final_classification', False):
            with st.form(key="true_classification_form"):
                true_class = st.radio(
                    "Select Final Classification",
                    options=["false positive", "need fixing", "very serious"],
                    index=0
                )
                
                comment = st.text_area(
                    "Comments (optional)",
                    value=detailed_issue.get('true_classification_comment', '')
                )
                
                submit_button = st.form_submit_button("Submit Final Classification")
                
                if submit_button:
                    try:
                        update_successful = set_issue_true_classification(
                            issue_id=detailed_issue['id'],
                            classification=true_class,
                            comment=comment if comment else None
                        )
                        
                        if update_successful:
                            st.success("Final classification submitted successfully!")
                            
                            # Reset editing state
                            if 'editing_final_classification' in st.session_state:
                                del st.session_state['editing_final_classification']
                            
                            # Refresh the page to show the updated classification
                            st.experimental_rerun()
                        else:
                            st.error("Failed to submit classification. Please try again.")
                    except Exception as e:
                        st.error(f"Error submitting classification: {str(e)}")
        
        # Navigation buttons at the bottom
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if st.button("Previous", disabled=st.session_state.current_issue_index <= 0):
                st.session_state.current_issue_index = max(0, st.session_state.current_issue_index - 1)
                st.experimental_rerun()
        
        with col3:
            if st.button("Next", disabled=st.session_state.current_issue_index >= len(filtered_issues) - 1):
                st.session_state.current_issue_index = min(len(filtered_issues) - 1, st.session_state.current_issue_index + 1)
                st.experimental_rerun()
else:
    st.warning("No issues found matching the selected filters.")
    
