"""
LLM Response Details Page

This page allows users to inspect detailed records of LLM interactions,
including full prompts, responses, token usage statistics, and performance metrics.
"""

import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

# Add the root directory to the path so we can import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.data_manager import get_llm_responses, get_token_usage_statistics

# Page title and description
st.title("LLM Response Details")
st.markdown("""
This page allows you to inspect detailed records of LLM interactions, 
including the full prompts sent to the LLM, raw responses received, token usage statistics, 
and response time measurements.
""")

# Filters sidebar
st.sidebar.header("Filters")

# Date range filter
st.sidebar.subheader("Date Range")
today = datetime.now().date()
date_from = st.sidebar.date_input(
    "From", 
    value=today - timedelta(days=30),
    max_value=today
)
date_to = st.sidebar.date_input(
    "To", 
    value=today,
    max_value=today
)

# LLM model filter
st.sidebar.subheader("LLM Model")
# We'll get the list of models from the responses themselves
# This requires a call to get_llm_responses without model filter first
all_responses = get_llm_responses()
models = sorted(list(set([resp.get('llm_model_name', 'Unknown') for resp in all_responses])))
selected_model = st.sidebar.selectbox(
    "Select LLM Model",
    options=["All"] + models,
    index=0
)

# Issue/Classification ID filter
st.sidebar.subheader("Issue Details")
issue_id = st.sidebar.text_input("Issue ID (optional)", value="")
classification_id = st.sidebar.text_input("Classification ID (optional)", value="")

# Token usage thresholds
st.sidebar.subheader("Token Usage")
min_tokens = st.sidebar.slider("Minimum Total Tokens", 0, 10000, 0)
max_tokens = st.sidebar.slider("Maximum Total Tokens", 0, 10000, 10000)

# Apply filters
filters = {}
if date_from and date_to:
    filters['date_from'] = date_from
    filters['date_to'] = date_to
if selected_model != "All":
    filters['llm_model_name'] = selected_model
if issue_id:
    try:
        filters['issue_id'] = int(issue_id)
    except ValueError:
        st.sidebar.error("Issue ID must be a number")
if classification_id:
    try:
        filters['classification_id'] = int(classification_id)
    except ValueError:
        st.sidebar.error("Classification ID must be a number")
filters['min_total_tokens'] = min_tokens
filters['max_total_tokens'] = max_tokens

# Get filtered responses
responses = get_llm_responses(filters)

# Display token usage statistics
st.header("Token Usage Statistics")
token_stats = get_token_usage_statistics(filters)

if not token_stats or token_stats.get('total_interactions', 0) == 0:
    st.info("No data available for the selected filters.")
else:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Interactions", token_stats.get('total_interactions', 0))
    
    with col2:
        st.metric("Total Tokens Used", token_stats.get('total_tokens', 0))
    
    with col3:
        st.metric("Avg Tokens per Request", round(token_stats.get('avg_tokens_per_request', 0), 1))
    
    with col4:
        st.metric("Avg Response Time (ms)", round(token_stats.get('avg_response_time_ms', 0), 1))
    
    # Create charts for token usage
    if 'model_token_usage' in token_stats and token_stats['model_token_usage']:
        model_data = pd.DataFrame(token_stats['model_token_usage'])
        fig1 = px.bar(
            model_data, 
            x='model', 
            y='total_tokens',
            title="Token Usage by Model",
            labels={'model': 'LLM Model', 'total_tokens': 'Total Tokens Used'}
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    if 'prompt_template_token_usage' in token_stats and token_stats['prompt_template_token_usage']:
        template_data = pd.DataFrame(token_stats['prompt_template_token_usage'])
        fig2 = px.bar(
            template_data, 
            x='prompt_template', 
            y='avg_tokens',
            title="Average Tokens per Request by Prompt Template",
            labels={'prompt_template': 'Prompt Template', 'avg_tokens': 'Avg Tokens per Request'}
        )
        st.plotly_chart(fig2, use_container_width=True)

# Display LLM response records
st.header(f"LLM Response Records ({len(responses)})")

if not responses:
    st.info("No LLM response records found matching the selected filters.")
else:
    # Create a DataFrame for easier display
    responses_df = pd.DataFrame([
        {
            'ID': r.get('id', 'N/A'),
            'Classification ID': r.get('classification_id', 'N/A'),
            'Issue ID': r.get('issue_id', 'N/A'),
            'LLM Model': r.get('llm_model_name', 'Unknown'),
            'Timestamp': r.get('timestamp', 'Unknown'),
            'Prompt Tokens': r.get('prompt_tokens', 'N/A'),
            'Completion Tokens': r.get('completion_tokens', 'N/A'),
            'Total Tokens': r.get('total_tokens', 'N/A'),
            'Response Time (ms)': r.get('response_time_ms', 'N/A')
        }
        for r in responses
    ])
    
    st.dataframe(responses_df, use_container_width=True)
    
    # Option to download as CSV
    csv = responses_df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name=f"llm_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # Detailed view of individual responses
    st.header("Detailed Response View")
    response_id = st.selectbox(
        "Select Response ID to View Details",
        options=[r.get('id') for r in responses]
    )
    
    if response_id:
        selected_response = next((r for r in responses if r.get('id') == response_id), None)
        
        if selected_response:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Metadata")
                st.json({
                    'Classification ID': selected_response.get('classification_id'),
                    'Issue ID': selected_response.get('issue_id'),
                    'LLM Model': selected_response.get('llm_model_name'),
                    'Timestamp': selected_response.get('timestamp'),
                    'Prompt Tokens': selected_response.get('prompt_tokens'),
                    'Completion Tokens': selected_response.get('completion_tokens'),
                    'Total Tokens': selected_response.get('total_tokens'),
                    'Response Time (ms)': selected_response.get('response_time_ms')
                })
                
                # Parse and display model parameters if available
                if 'model_parameters' in selected_response and selected_response['model_parameters']:
                    try:
                        model_params = json.loads(selected_response['model_parameters'])
                        st.subheader("Model Parameters")
                        st.json(model_params)
                    except (json.JSONDecodeError, TypeError):
                        st.subheader("Model Parameters")
                        st.text(selected_response['model_parameters'])
            
            with col2:
                st.subheader("Full Prompt")
                st.text_area("", selected_response.get('full_prompt', ''), height=300)
                
                st.subheader("Full Response")
                st.text_area("", selected_response.get('full_response', ''), height=300) 