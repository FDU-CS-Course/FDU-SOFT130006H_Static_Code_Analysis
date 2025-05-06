"""Tests for the LLM service module."""

import os
import json
import pytest
from unittest.mock import patch, mock_open
import yaml
from core.llm_service import LLMService

# Test data
SAMPLE_CONFIG = """
gpt4:
  provider: openai
  model: gpt-4
  api_key: dummy_api_key_123
"""

SAMPLE_PROMPT = """You are a code review assistant. Analyze this issue: {summary}

Please provide your analysis in JSON format:
```json
{{
    "classification": "one of: false positive, need fixing, very serious",
    "explanation": "detailed explanation of your reasoning"
}}
```"""

SAMPLE_ISSUE = {
    "file": "src/main.cpp",
    "line": "42",
    "severity": "warning",
    "id": "nullPointer",
    "summary": "Possible null pointer dereference: ptr",
    "code_context": "void process(int* ptr) {\n    if (ptr) {\n        *ptr = 42;\n    }\n}"
}

@pytest.fixture
def llm_service():
    """Create LLMService instance with mocked config."""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(SAMPLE_CONFIG.encode("utf-8"))
        config_path = f.name
    return LLMService(config_path)

def test_load_llm_configurations(llm_service):
    """Test loading LLM configurations."""
    configs = llm_service._load_llm_configurations()
    assert "gpt4" in configs
    assert configs["gpt4"]["provider"] == "openai"
    assert configs["gpt4"]["model"] == "gpt-4"
    assert configs["gpt4"]["api_key"] == "dummy_api_key_123"

def test_load_llm_configurations_file_not_found():
    """Test handling of missing config file."""
    with pytest.raises(FileNotFoundError):
        LLMService("nonexistent.yaml")

def test_list_prompt_templates(llm_service):
    """Test listing prompt templates."""
    with patch("pathlib.Path.exists") as mock_exists, \
         patch("pathlib.Path.glob") as mock_glob:
        mock_exists.return_value = True
        mock_glob.return_value = [
            type("Path", (), {"name": "template1.txt"})(),
            type("Path", (), {"name": "template2.txt"})()
        ]
        
        templates = llm_service.list_prompt_templates()
        assert len(templates) == 2
        assert "template1.txt" in templates
        assert "template2.txt" in templates

def test_list_prompt_templates_empty_dir(llm_service):
    """Test listing prompt templates from empty directory."""
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False
        templates = llm_service.list_prompt_templates()
        assert len(templates) == 0

def test_load_prompt_template(llm_service):
    """Test loading prompt template content."""
    with patch("builtins.open", mock_open(read_data=SAMPLE_PROMPT)):
        content = llm_service.load_prompt_template("dummy_template.txt")
        assert content == SAMPLE_PROMPT

def test_load_prompt_template_not_found(llm_service):
    """Test handling of missing prompt template."""
    with pytest.raises(FileNotFoundError):
        llm_service.load_prompt_template("nonexistent.txt")

@patch("openai.ChatCompletion.create")
def test_classify_issue_openai(mock_create, llm_service):
    """Test issue classification using OpenAI."""
    # Mock OpenAI response
    mock_create.return_value.choices = [
        type("Choice", (), {
            "message": type("Message", (), {
                "content": """Here's my analysis:
```json
{
    "classification": "false positive",
    "explanation": "The pointer is checked for null before dereferencing"
}
```"""
            })()
        })()
    ]
    
    result = llm_service.classify_issue(
        SAMPLE_ISSUE,
        "gpt4",
        SAMPLE_PROMPT
    )
    
    assert result["classification"] == "false positive"
    assert "pointer is checked" in result["explanation"].lower()
    
    # Verify OpenAI API call
    mock_create.assert_called_once()
    call_args = mock_create.call_args[1]
    assert call_args["model"] == "gpt-4"
    assert len(call_args["messages"]) == 2

@patch("openai.ChatCompletion.create")
def test_classify_issue_invalid_classification(mock_create, llm_service):
    """Test handling of invalid classification value."""
    mock_create.return_value.choices = [
        type("Choice", (), {
            "message": type("Message", (), {
                "content": """Here's my analysis:
```json
{
    "classification": "invalid_value",
    "explanation": "Test explanation"
}
```"""
            })()
        })()
    ]
    
    with pytest.raises(RuntimeError) as exc_info:
        llm_service.classify_issue(
            SAMPLE_ISSUE,
            "gpt4",
            SAMPLE_PROMPT
        )
    assert "Invalid classification value" in str(exc_info.value)

def test_classify_issue_invalid_llm(llm_service):
    """Test classification with invalid LLM name."""
    with pytest.raises(KeyError):
        llm_service.classify_issue(
            SAMPLE_ISSUE,
            "invalid_llm",
            SAMPLE_PROMPT
        )

def test_classify_issue_missing_api_key(llm_service):
    """Test classification with missing API key."""
    # Modify the config to remove API key
    llm_service.llm_configs["gpt4"].pop("api_key")
    
    with pytest.raises(ValueError) as exc_info:
        llm_service.classify_issue(
            SAMPLE_ISSUE,
            "gpt4",
            SAMPLE_PROMPT
        )
    assert "API key not found" in str(exc_info.value)

@patch("openai.ChatCompletion.create")
def test_classify_issue_api_error(mock_create, llm_service):
    """Test handling of OpenAI API errors."""
    mock_create.side_effect = Exception("API Error")
    
    with pytest.raises(RuntimeError) as exc_info:
        llm_service.classify_issue(
            SAMPLE_ISSUE,
            "gpt4",
            SAMPLE_PROMPT
        )
    assert "OpenAI API error" in str(exc_info.value) 