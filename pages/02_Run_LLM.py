"""
Run LLM Page - Allows users to run LLM analysis on cppcheck issues.
"""

import os
import streamlit as st
import time
import pandas as pd
import yaml
from typing import List, Dict, Any, Optional

import config
from core.data_manager import get_all_issues, get_issue_by_id, add_llm_classification
from core.llm_service import LLMService
from core.context_builder import ContextBuilder
from utils.file_utils import is_path_safe

# Page configuration
st.set_page_config(
    page_title="Run LLM - Review Helper",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state for progress tracking if not exists
if 'processing_issues' not in st.session_state:
    st.session_state.processing_issues = False
if 'current_issue_index' not in st.session_state:
    st.session_state.current_issue_index = 0
if 'total_issues' not in st.session_state:
    st.session_state.total_issues = 0
if 'processed_issues' not in st.session_state:
    st.session_state.processed_issues = []
if 'failed_issues' not in st.session_state:
    st.session_state.failed_issues = []

# Initialize LLM service
try:
    llm_service = LLMService()
except Exception as e:
    st.error(f"Error initializing LLM service: {str(e)}")
    llm_service = None

# Page title
st.title("Run LLM Analysis")
st.markdown("Select LLM model, prompt template, and context strategy to classify issues.")

# Function to load available LLM configurations
def load_llm_configs() -> Dict[str, Dict[str, Any]]:
    """
    Load LLM configurations from models.yaml file.
    
    Returns:
        Dict[str, Dict[str, Any]]: Dictionary of LLM configurations.
    """
    try:
        with open(config.MODELS_CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Error loading LLM configurations: {str(e)}")
        return {}

# Function to get prompt templates
def get_prompt_templates() -> List[str]:
    """
    Get list of available prompt templates from the prompts directory.
    
    Returns:
        List[str]: List of prompt template filenames.
    """
    try:
        if llm_service:
            return llm_service.list_prompt_templates(config.PROMPTS_DIR_PATH)
        else:
            # Fallback to manual file listing if llm_service is not available
            if os.path.exists(config.PROMPTS_DIR_PATH):
                return [f for f in os.listdir(config.PROMPTS_DIR_PATH) 
                        if os.path.isfile(os.path.join(config.PROMPTS_DIR_PATH, f)) and f.endswith('.txt')]
            else:
                return []
    except Exception as e:
        st.error(f"Error loading prompt templates: {str(e)}")
        return []

# Function to process issues with LLM
def process_issues(issues: List[Dict[str, Any]], 
                  llm_config_name: str, 
                  prompt_template: str,
                  context_strategy: str,
                  stop_event) -> None:
    """
    Process a list of issues with the selected LLM configuration.
    
    Args:
        issues: List of issues to process
        llm_config_name: Name of the LLM configuration to use
        prompt_template: Filename of the prompt template to use
        context_strategy: Strategy for building code context
        stop_event: Flag to stop processing
    """
    print(f"Processing {len(issues)} issues with {llm_config_name} and {prompt_template}")
    
    # Initialize context builder once
    context_builder = ContextBuilder(config.PROJECT_ROOT_DIR)
    
    st.session_state.total_issues = len(issues)
    st.session_state.current_issue_index = 0
    st.session_state.processed_issues = []
    st.session_state.failed_issues = []
    
    for i, issue in enumerate(issues):
        if stop_event():
            st.warning("Processing stopped by user.")
            break
            
        st.session_state.current_issue_index = i + 1
        
        try:
            # Check if PROJECT_ROOT_DIR is set
            if not config.PROJECT_ROOT_DIR:
                raise ValueError("Project root directory not set. Please set the REVIEW_HELPER_PROJECT_ROOT environment variable.")
            
            # Get file path and line number
            file_path = issue['cppcheck_file']
            line_number = int(issue['cppcheck_line'])  # Ensure line_number is an integer
            
            # Build absolute path to source file
            abs_file_path = os.path.join(config.PROJECT_ROOT_DIR, file_path)
            
            # Validate path is safe (will be checked again in context_builder)
            if not is_path_safe(abs_file_path, config.PROJECT_ROOT_DIR):
                raise ValueError(f"File path is outside the project root: {file_path}")
            
            # Build code context using the selected strategy
            code_context = context_builder.build_context(
                abs_file_path, 
                line_number, 
                strategy=context_strategy,
                lines_before=config.CONTEXT_LINES_COUNT,
                lines_after=config.CONTEXT_LINES_COUNT
            )
            
            if code_context is None:
                raise ValueError(f"Could not build code context for {file_path}:{line_number}. File may not exist or is not accessible.")
            
            # Prepare issue content for LLM
            issue_content = {
                'file': file_path,
                'line': str(line_number),  # Ensure line is a string for formatting
                'severity': issue['cppcheck_severity'],
                'id': issue['cppcheck_id'],
                'summary': issue['cppcheck_summary'],
                'code_context': code_context
            }
            
            # Call LLM for classification
            llm_result = llm_service.classify_issue(
                issue_content=issue_content,
                llm_name=llm_config_name,
                prompt_template=prompt_template
            )
            
            # Validate classification before saving to database
            valid_classifications = ["false positive", "need fixing", "very serious"]
            classification = llm_result.get('classification', 'unknown')
            if classification not in valid_classifications:
                print(f"Warning: Invalid classification '{classification}' from LLM. Using 'unknown' instead.")
                classification = "unknown"
            
            # Save classification to database
            add_llm_classification(
                issue_id=issue['id'],
                llm_model_name=llm_config_name,
                context_strategy=context_strategy,
                prompt_template=prompt_template,
                source_code_context=code_context,
                classification=classification,
                explanation=llm_result.get('explanation', '')
            )
            
            # Add to processed issues
            st.session_state.processed_issues.append({
                'id': issue['id'],
                'file': file_path,
                'line': line_number,
                'classification': classification
            })
            
            # Small delay to prevent API rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            # Add to failed issues
            st.session_state.failed_issues.append({
                'id': issue.get('id', 'Unknown'),
                'file': issue.get('cppcheck_file', 'Unknown'),
                'line': issue.get('cppcheck_line', 'Unknown'),
                'error': str(e)
            })
            import traceback
            traceback.print_exc()
            print(f"Failed to process issue {issue.get('id', 'Unknown')}: {str(e)}")
    
    print(f"Processed {len(st.session_state.processed_issues)} issues")
    print(f"Failed {len(st.session_state.failed_issues)} issues")
            
    st.session_state.processing_issues = False

def on_start_processing_click():
    """Callback for starting processing"""
    st.session_state.processing_issues = True
    # Create stop event flag
    stop_requested = lambda: not st.session_state.processing_issues
    
    # Start processing in a separate thread
    st.session_state.total_issues = len(selected_issues)
    process_issues(
        selected_issues,
        selected_llm,
        selected_prompt,
        selected_strategy,
        stop_requested
    )


# Main UI layout
if not config.PROJECT_ROOT_DIR:
    st.error("⚠️ Project root directory not set. Please set the REVIEW_HELPER_PROJECT_ROOT environment variable.")
    st.stop()

# Load configurations
llm_configs = load_llm_configs()
prompt_templates = get_prompt_templates()

if not llm_configs:
    st.error("No LLM configurations found. Please check models.yaml file.")
    st.stop()

if not prompt_templates:
    st.error("No prompt templates found. Please add prompt templates to the prompts directory.")
    st.stop()

# Configuration section
st.subheader("Configuration")

col1, col2, col3 = st.columns(3)

with col1:
    # LLM configuration selection
    selected_llm = st.selectbox(
        "Select LLM Model",
        options=list(llm_configs.keys()),
        index=list(llm_configs.keys()).index(config.DEFAULT_LLM_UNIQUE_NAME) if config.DEFAULT_LLM_UNIQUE_NAME in llm_configs else 0
    )
    
    # Show selected LLM details
    if selected_llm in llm_configs:
        llm_details = llm_configs[selected_llm]
        st.info(f"Provider: {llm_details.get('provider', 'Unknown')}\n"
                f"Model: {llm_details.get('model', 'Unknown')}")

with col2:
    # Prompt template selection
    selected_prompt = st.selectbox(
        "Select Prompt Template",
        options=prompt_templates,
        index=prompt_templates.index(config.DEFAULT_PROMPT_TEMPLATE_FILENAME) if config.DEFAULT_PROMPT_TEMPLATE_FILENAME in prompt_templates else 0
    )
    
    # Show preview button for prompt
    if st.button("Preview Prompt Template"):
        try:
            prompt_path = os.path.join(config.PROMPTS_DIR_PATH, selected_prompt)
            with open(prompt_path, 'r') as f:
                prompt_content = f.read()
            st.code(prompt_content, language="text")
        except Exception as e:
            st.error(f"Error reading prompt template: {str(e)}")

with col3:
    # Context strategy selection
    selected_strategy = st.selectbox(
        "Select Context Strategy",
        options=["fixed_lines", "function_scope"],
        index=0 if config.DEFAULT_CONTEXT_STRATEGY == "fixed_lines" else 1
    )
    
    # If fixed_lines is selected, show context lines count input
    if selected_strategy == "fixed_lines":
        context_lines = st.number_input(
            "Context Lines (before/after)",
            min_value=1,
            max_value=20,
            value=config.CONTEXT_LINES_COUNT
        )
    else:
        context_lines = config.CONTEXT_LINES_COUNT

# Issues selection section
st.subheader("Select Issues to Process")

# Load issues
try:
    all_issues = get_all_issues()
    
    # Filter issues based on status
    status_filter = st.multiselect(
        "Filter by Status",
        options=["pending_llm", "pending_review", "reviewed"],
        default=["pending_llm"]
    )
    
    filtered_issues = [issue for issue in all_issues if issue['status'] in status_filter]
    
    # Create DataFrame for display
    if filtered_issues:
        issues_df = pd.DataFrame([{
            'ID': issue['id'],
            'File': issue['cppcheck_file'],
            'Line': issue['cppcheck_line'],
            'Severity': issue['cppcheck_severity'],
            'Issue ID': issue['cppcheck_id'],
            'Status': issue['status']
        } for issue in filtered_issues])
        
        # Display issues and allow selection
        st.dataframe(issues_df)
        
        # Allow selecting all or specific issues
        selection_type = st.radio(
            "Issue Selection",
            options=["All Issues", "By Severity", "Specific Issues"],
            index=0
        )
        
        selected_issues = []
        
        if selection_type == "All Issues":
            selected_issues = filtered_issues
            st.info(f"Selected {len(selected_issues)} issues for processing.")
            
        elif selection_type == "By Severity":
            severity_options = list(set(issue['cppcheck_severity'] for issue in filtered_issues))
            selected_severities = st.multiselect(
                "Select Severities",
                options=severity_options,
                default=severity_options
            )
            
            selected_issues = [issue for issue in filtered_issues 
                              if issue['cppcheck_severity'] in selected_severities]
            st.info(f"Selected {len(selected_issues)} issues with severity: {', '.join(selected_severities)}")
            
        elif selection_type == "Specific Issues":
            issue_ids = st.multiselect(
                "Select Specific Issues",
                options=[f"ID {issue['id']}: {issue['cppcheck_file']}:{issue['cppcheck_line']}" 
                         for issue in filtered_issues],
                default=[]
            )
            
            selected_issue_ids = [int(id_str.split(':')[0].replace('ID ', '')) for id_str in issue_ids]
            selected_issues = [issue for issue in filtered_issues if issue['id'] in selected_issue_ids]
            st.info(f"Selected {len(selected_issues)} specific issues.")
        
        # Process button
        if st.session_state.processing_issues:
            progress_bar = st.progress(0)
            
            # Display progress
            if st.session_state.total_issues > 0:
                progress = st.session_state.current_issue_index / st.session_state.total_issues
                progress_bar.progress(progress)
                
                st.text(f"Processing issue {st.session_state.current_issue_index} of {st.session_state.total_issues}")
                
                # Stop button
                if st.button("Stop Processing"):
                    st.session_state.processing_issues = False
                    st.warning("Stopping after current issue completes...")
            
            # Display processed issues in real-time
            if st.session_state.processed_issues:
                with st.expander(f"Processed Issues ({len(st.session_state.processed_issues)})"):
                    processed_df = pd.DataFrame(st.session_state.processed_issues)
                    st.dataframe(processed_df)
            
            # Display failed issues in real-time
            if st.session_state.failed_issues:
                with st.expander(f"Failed Issues ({len(st.session_state.failed_issues)})"):
                    failed_df = pd.DataFrame(st.session_state.failed_issues)
                    st.dataframe(failed_df)
        
        elif selected_issues:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.button("Start Processing", key="start_processing", on_click=on_start_processing_click)
            
            with col2:
                st.info("Click 'Start Processing' to begin LLM analysis of the selected issues.")
                st.warning("This may take some time depending on the number of issues and LLM response time.")
        
        # If processing has completed, show summary and navigation button
        if (not st.session_state.processing_issues and 
            st.session_state.processed_issues and 
            st.session_state.current_issue_index > 0):
            
            st.success(f"Completed processing {len(st.session_state.processed_issues)} issues.")
            
            if st.session_state.failed_issues:
                st.error(f"Failed to process {len(st.session_state.failed_issues)} issues. See details in the 'Failed Issues' section.")
            
            if st.button("Proceed to Review Issues"):
                st.switch_page("pages/03_Review_Issues.py")
    else:
        st.warning("No issues found matching the selected filters.")
        
except Exception as e:
    st.error(f"Error loading issues: {str(e)}") 