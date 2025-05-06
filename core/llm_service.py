"""LLM service module for handling interactions with various LLM providers.

This module provides functionality to:
- Load LLM configurations from YAML
- Manage prompt templates
- Classify issues using configured LLMs

Example prompt template (prompts/classification_default.txt):
```text
You are a code review assistant. Analyze the following cppcheck issue and classify it as either:
- "false positive": The issue is not a real problem
- "need fixing": The issue should be fixed but is not critical
- "very serious": The issue is critical and must be fixed immediately

Issue details:
File: {file}
Line: {line}
Severity: {severity}
ID: {id}
Summary: {summary}
Code Context:
{code_context}

Please provide your analysis in JSON format:
```json
{
    "classification": "one of: false positive, need fixing, very serious",
    "explanation": "detailed explanation of your reasoning"
}
```

Example input dictionary:
{
    "file": "src/main.cpp",
    "line": "42",
    "severity": "warning",
    "id": "nullPointer",
    "summary": "Possible null pointer dereference: ptr",
    "code_context": "void process(int* ptr) {\n    if (ptr) {\n        *ptr = 42;  // Line 42\n    }\n}"
}
"""

import os
import json
from typing import Dict, List, Optional, Any
import yaml
from pathlib import Path
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LLMService:
    """Service class for handling LLM interactions and configurations."""
    
    def __init__(self, config_path: str = "models.yaml"):
        """Initialize LLM service with configurations.
        
        Args:
            config_path: Path to YAML file containing LLM configurations
        """
        self.config_path = config_path
        self.llm_configs = self._load_llm_configurations()
        
    def _load_llm_configurations(self) -> Dict[str, Any]:
        """Load LLM configurations from YAML file.
        
        Returns:
            Dictionary of LLM configurations
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"LLM configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in {self.config_path}: {str(e)}")
            
    def list_prompt_templates(self, prompts_dir: str = "prompts") -> List[str]:
        """List available prompt templates.
        
        Args:
            prompts_dir: Directory containing prompt templates
            
        Returns:
            List of prompt template filenames
        """
        prompt_dir = Path(prompts_dir)
        if not prompt_dir.exists():
            return []
        return [f.name for f in prompt_dir.glob("*.txt")]
    
    def load_prompt_template(self, template_path: str) -> str:
        """Load prompt template content.
        
        Args:
            template_path: Path to prompt template file
            
        Returns:
            Template content as string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        try:
            with open(template_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
            
    def classify_issue(self, 
                      issue_content: Dict[str, str], 
                      llm_name: str, 
                      prompt_template: str) -> Dict[str, str]:
        """Classify an issue using specified LLM.
        
        Args:
            issue_content: Dictionary containing issue details
            llm_name: Name of LLM configuration to use
            prompt_template: Prompt template content
            
        Returns:
            Dictionary containing classification and explanation
            
        Raises:
            KeyError: If LLM configuration not found
            ValueError: If required API key not set
        """
        if llm_name not in self.llm_configs:
            raise KeyError(f"LLM configuration not found: {llm_name}")
            
        config = self.llm_configs[llm_name]
        api_key = config.get('api_key')
        
        if not api_key:
            raise ValueError(f"API key not found in config for LLM: {llm_name}")
            
        # Format prompt with issue content
        formatted_prompt = prompt_template.format(**issue_content)
        
        # Currently only OpenAI implementation
        # TODO: Add support for other LLM providers
        if config['provider'] == 'openai':
            return self._classify_with_openai(
                formatted_prompt,
                config['model'],
                api_key
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {config['provider']}")
            
    def _classify_with_openai(self, 
                            prompt: str, 
                            model: str, 
                            api_key: str) -> Dict[str, str]:
        """Classify using OpenAI API.
        
        Args:
            prompt: Formatted prompt
            model: OpenAI model name
            api_key: OpenAI API key
            
        Returns:
            Dictionary with classification and explanation
            
        Raises:
            RuntimeError: If API call fails or response is invalid
            json.JSONDecodeError: If response is not valid JSON
        """
        openai.api_key = api_key
        
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a code review assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract JSON from response
            content = response.choices[0].message.content
            json_str = content.split("```json")[1].split("```")[0].strip()
            
            try:
                result = json.loads(json_str)
                if not isinstance(result, dict) or "classification" not in result or "explanation" not in result:
                    raise ValueError("Invalid JSON structure")
                    
                # Validate classification value
                valid_classifications = ["false positive", "need fixing", "very serious"]
                if result["classification"] not in valid_classifications:
                    raise ValueError(f"Invalid classification value: {result['classification']}")
                    
                return result
                
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSON response from LLM: {str(e)}")
            except ValueError as e:
                raise RuntimeError(f"Invalid response structure: {str(e)}")
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}") 