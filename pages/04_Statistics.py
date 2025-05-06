"""
Statistics Page - Displays statistics about LLM performance and issues.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from typing import Dict, Any, List, Optional

from core.data_manager import get_llm_statistics, get_all_issues

# Page configuration
st.set_page_config(
    page_title="Statistics - Review Helper",
    page_icon="📊",
    layout="wide"
)

# Page title
st.title("Statistics and Analysis")
st.markdown("Analyze LLM performance and issue classifications.")

# Function to format percentages
def format_percentage(value: float) -> str:
    """
    Format a decimal value as a percentage string.
    
    Args:
        value: Decimal value to format (e.g., 0.75)
        
    Returns:
        str: Formatted percentage string (e.g., "75.0%")
    """
    return f"{value * 100:.1f}%"

# Load data
try:
    # Get all issues for reference
    all_issues = get_all_issues()
    
    # Calculate basic issue stats
    total_issues = len(all_issues)
    
    if total_issues == 0:
        st.warning("No issues found in the database. Please load issues and run LLM analysis first.")
        
        # Navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Go to Load Issues"):
                st.switch_page("pages/01_Load_Issues.py")
        
        with col2:
            if st.button("Go to Run LLM"):
                st.switch_page("pages/02_Run_LLM.py")
        
        st.stop()
    
    # Filters section
    st.subheader("Filters")
    
    # Date filter
    col1, col2 = st.columns(2)
    with col1:
        # Get min and max dates from the issues
        min_date = datetime.now() - timedelta(days=30)  # Default to last 30 days
        max_date = datetime.now()
        
        if all_issues:
            try:
                # Try to parse dates from created_at
                dates = [datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')) 
                         for issue in all_issues if 'created_at' in issue]
                if dates:
                    min_date = min(dates)
                    max_date = max(dates)
            except:
                pass  # Use default dates if parsing fails
        
        date_from = st.date_input(
            "From Date",
            value=min_date.date(),
            min_value=min_date.date(),
            max_value=max_date.date()
        )
    
    with col2:
        date_to = st.date_input(
            "To Date",
            value=max_date.date(),
            min_value=min_date.date(),
            max_value=max_date.date()
        )
    
    # Model and context strategy filters
    col1, col2 = st.columns(2)
    
    # Get LLM statistics to extract model names and context strategies
    stats = get_llm_statistics()
    
    llm_models = []
    context_strategies = []
    prompt_templates = []
    
    if stats and 'models' in stats:
        llm_models = list(stats['models'].keys())
    
    if stats and 'context_strategies' in stats:
        context_strategies = list(stats['context_strategies'].keys())
    
    if stats and 'prompt_templates' in stats:
        prompt_templates = list(stats['prompt_templates'].keys())
    
    with col1:
        selected_models = st.multiselect(
            "LLM Models",
            options=llm_models,
            default=llm_models
        )
    
    with col2:
        selected_strategies = st.multiselect(
            "Context Strategies",
            options=context_strategies,
            default=context_strategies
        )
    
    selected_templates = st.multiselect(
        "Prompt Templates",
        options=prompt_templates,
        default=prompt_templates
    )
    
    # Apply filters
    filters = {
        'date_from': date_from.isoformat() if date_from else None,
        'date_to': date_to.isoformat() if date_to else None,
        'llm_model_name': selected_models if selected_models else None,
        'context_strategy': selected_strategies if selected_strategies else None,
        'prompt_template': selected_templates if selected_templates else None
    }
    
    # Get filtered statistics
    filtered_stats = get_llm_statistics(filters)
    
    # Display overall statistics
    st.subheader("Overall Statistics")
    
    if not filtered_stats:
        st.warning("No data available for the selected filters.")
        st.stop()
    
    # Create metrics for overall stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Issues", filtered_stats.get('total_issues', 0))
    
    with col2:
        st.metric("Reviewed Issues", filtered_stats.get('reviewed_issues', 0))
    
    with col3:
        st.metric("LLM Classifications", filtered_stats.get('total_classifications', 0))
    
    with col4:
        accuracy = filtered_stats.get('overall_accuracy', 0)
        st.metric("Overall Accuracy", format_percentage(accuracy))
    
    # Tabs for different statistical views
    tab1, tab2, tab3, tab4 = st.tabs([
        "LLM Performance", 
        "Classification Distribution", 
        "Context Strategies", 
        "Raw Data"
    ])
    
    with tab1:
        st.subheader("LLM Model Performance")
        
        # Model comparison chart
        if 'models' in filtered_stats and filtered_stats['models']:
            model_data = []
            
            for model_name, model_stats in filtered_stats['models'].items():
                model_data.append({
                    'Model': model_name,
                    'Accuracy': model_stats.get('accuracy', 0),
                    'Classifications': model_stats.get('classifications', 0)
                })
            
            model_df = pd.DataFrame(model_data)
            
            # Create bar chart for model accuracy
            fig = px.bar(
                model_df,
                x='Model',
                y='Accuracy',
                title='LLM Model Accuracy',
                text_auto='.1%',
                color='Model',
                hover_data=['Classifications']
            )
            
            fig.update_layout(yaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)
            
            # Model performance details table
            st.subheader("Model Performance Details")
            
            model_details = []
            for model_name, model_stats in filtered_stats['models'].items():
                model_details.append({
                    'Model': model_name,
                    'Classifications': model_stats.get('classifications', 0),
                    'Correct': model_stats.get('correct', 0),
                    'Incorrect': model_stats.get('incorrect', 0),
                    'Pending': model_stats.get('pending', 0),
                    'Accuracy': format_percentage(model_stats.get('accuracy', 0))
                })
            
            model_details_df = pd.DataFrame(model_details)
            st.dataframe(model_details_df)
        else:
            st.info("No model performance data available for the selected filters.")
    
    with tab2:
        st.subheader("Classification Distribution")
        
        # True classification distribution
        if 'classification_distribution' in filtered_stats and filtered_stats['classification_distribution']:
            dist_data = []
            
            for classification, count in filtered_stats['classification_distribution'].items():
                dist_data.append({
                    'Classification': classification,
                    'Count': count
                })
            
            dist_df = pd.DataFrame(dist_data)
            
            # Create pie chart for classification distribution
            fig = px.pie(
                dist_df,
                values='Count',
                names='Classification',
                title='Issue Classification Distribution',
                color='Classification',
                color_discrete_map={
                    'false positive': '#28a745',
                    'need fixing': '#ffc107',
                    'very serious': '#dc3545'
                }
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Classification agreement matrix
        if 'confusion_matrix' in filtered_stats and filtered_stats['confusion_matrix']:
            st.subheader("LLM vs Human Classification Agreement")
            
            matrix_data = filtered_stats['confusion_matrix']
            
            # Convert matrix to dataframe format for heatmap
            matrix_rows = []
            for llm_class, human_classes in matrix_data.items():
                for human_class, count in human_classes.items():
                    matrix_rows.append({
                        'LLM Classification': llm_class,
                        'Human Classification': human_class,
                        'Count': count
                    })
            
            matrix_df = pd.DataFrame(matrix_rows)
            
            # Create heatmap for confusion matrix
            if not matrix_df.empty:
                pivot_df = matrix_df.pivot(
                    index='LLM Classification', 
                    columns='Human Classification', 
                    values='Count'
                ).fillna(0)
                
                fig = px.imshow(
                    pivot_df,
                    text_auto=True,
                    aspect="auto",
                    title="LLM vs Human Classification Comparison",
                    color_continuous_scale='Blues'
                )
                
                fig.update_layout(
                    xaxis_title="Human Classification",
                    yaxis_title="LLM Classification"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No classification comparison data available.")
        else:
            st.info("No classification distribution data available for the selected filters.")
    
    with tab3:
        st.subheader("Context Strategies Comparison")
        
        # Context strategy performance
        if 'context_strategies' in filtered_stats and filtered_stats['context_strategies']:
            strategy_data = []
            
            for strategy_name, strategy_stats in filtered_stats['context_strategies'].items():
                strategy_data.append({
                    'Strategy': strategy_name,
                    'Accuracy': strategy_stats.get('accuracy', 0),
                    'Classifications': strategy_stats.get('classifications', 0)
                })
            
            strategy_df = pd.DataFrame(strategy_data)
            
            # Create bar chart for strategy accuracy
            fig = px.bar(
                strategy_df,
                x='Strategy',
                y='Accuracy',
                title='Context Strategy Accuracy',
                text_auto='.1%',
                color='Strategy',
                hover_data=['Classifications']
            )
            
            fig.update_layout(yaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)
            
            # Prompt template performance
            if 'prompt_templates' in filtered_stats and filtered_stats['prompt_templates']:
                st.subheader("Prompt Template Performance")
                
                template_data = []
                
                for template_name, template_stats in filtered_stats['prompt_templates'].items():
                    template_data.append({
                        'Template': template_name,
                        'Accuracy': template_stats.get('accuracy', 0),
                        'Classifications': template_stats.get('classifications', 0)
                    })
                
                template_df = pd.DataFrame(template_data)
                
                # Create bar chart for template accuracy
                fig = px.bar(
                    template_df,
                    x='Template',
                    y='Accuracy',
                    title='Prompt Template Accuracy',
                    text_auto='.1%',
                    color='Template',
                    hover_data=['Classifications']
                )
                
                fig.update_layout(yaxis_tickformat='.1%')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No context strategy data available for the selected filters.")
    
    with tab4:
        st.subheader("Raw Data")
        
        # Add export options
        export_format = st.radio("Export Format", ["JSON", "CSV"], horizontal=True)
        
        if st.button("Export Data"):
            if export_format == "JSON":
                # Convert to JSON
                json_data = json.dumps(filtered_stats, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name=f"review_helper_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            else:
                # Convert to CSV (flatten the nested structure)
                flat_data = {
                    'total_issues': filtered_stats.get('total_issues', 0),
                    'reviewed_issues': filtered_stats.get('reviewed_issues', 0),
                    'total_classifications': filtered_stats.get('total_classifications', 0),
                    'overall_accuracy': filtered_stats.get('overall_accuracy', 0)
                }
                
                # Add model data
                for model_name, model_stats in filtered_stats.get('models', {}).items():
                    for stat_key, stat_value in model_stats.items():
                        flat_data[f"model_{model_name}_{stat_key}"] = stat_value
                
                # Add context strategy data
                for strategy_name, strategy_stats in filtered_stats.get('context_strategies', {}).items():
                    for stat_key, stat_value in strategy_stats.items():
                        flat_data[f"strategy_{strategy_name}_{stat_key}"] = stat_value
                
                # Add prompt template data
                for template_name, template_stats in filtered_stats.get('prompt_templates', {}).items():
                    for stat_key, stat_value in template_stats.items():
                        flat_data[f"template_{template_name}_{stat_key}"] = stat_value
                
                # Convert to DataFrame for CSV
                flat_df = pd.DataFrame([flat_data])
                
                # Download button
                csv_data = flat_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"review_helper_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Display raw statistics in expandable sections
        with st.expander("Overall Statistics"):
            st.json({
                'total_issues': filtered_stats.get('total_issues', 0),
                'reviewed_issues': filtered_stats.get('reviewed_issues', 0),
                'total_classifications': filtered_stats.get('total_classifications', 0),
                'overall_accuracy': filtered_stats.get('overall_accuracy', 0)
            })
        
        if 'classification_distribution' in filtered_stats:
            with st.expander("Classification Distribution"):
                st.json(filtered_stats['classification_distribution'])
        
        if 'models' in filtered_stats:
            with st.expander("Model Performance"):
                st.json(filtered_stats['models'])
        
        if 'context_strategies' in filtered_stats:
            with st.expander("Context Strategies"):
                st.json(filtered_stats['context_strategies'])
        
        if 'prompt_templates' in filtered_stats:
            with st.expander("Prompt Templates"):
                st.json(filtered_stats['prompt_templates'])
        
        if 'confusion_matrix' in filtered_stats:
            with st.expander("Classification Agreement Matrix"):
                st.json(filtered_stats['confusion_matrix'])

except Exception as e:
    st.error(f"Error loading statistics: {str(e)}")
    
    # If there's an error, offer navigation options
    st.markdown("### Troubleshooting")
    st.markdown("""
    If you're seeing this error, it might be because:
    
    1. No issues have been loaded yet
    2. No LLM classifications have been generated
    3. There's a database connection issue
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Go to Load Issues"):
            st.switch_page("pages/01_Load_Issues.py")
    
    with col2:
        if st.button("Go to Run LLM"):
            st.switch_page("pages/02_Run_LLM.py")
    
    with col3:
        if st.button("Go to Review Issues"):
            st.switch_page("pages/03_Review_Issues.py") 