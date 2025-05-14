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
import re
from typing import Dict, List, Optional, Any, Tuple, Union
import yaml
from pathlib import Path
import openai
from dotenv import load_dotenv
import time
import jsonschema

# Load environment variables
load_dotenv()

class LLMService:
    """Service class for handling LLM interactions and configurations.
    
    This class provides a layered API for LLM interactions:
    1. Low-level text generation API (generate_text)
    2. JSON extraction and validation API (extract_json)
    3. High-level domain-specific API (classify_issue)
    """
    
    def __init__(self, config_path: str = "models.yaml"):
        """Initialize LLM service with configurations.
        
        Args:
            config_path: Path to YAML file containing LLM configurations
        """
        self.config_path = config_path
        self.llm_configs = self._load_llm_configurations()
        
        # Schema for classification results
        self.classification_schema = {
            "type": "object",
            "required": ["classification", "explanation"],
            "properties": {
                "classification": {
                    "type": "string",
                    "enum": ["false positive", "need fixing", "very serious"]
                },
                "explanation": {
                    "type": "string"
                }
            }
        }
        
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
            
    def format_prompt(self, template_path: str, issue_content: Dict[str, str]) -> str:
        """Format a prompt template with issue content.
        
        Args:
            template_path: Path or filename of the prompt template
            issue_content: Dictionary containing issue details
            
        Returns:
            Formatted prompt string
            
        Raises:
            ValueError: If prompt template not found
        """
        try:
            # If just a filename is provided, assume it's in the prompts directory
            if not os.path.dirname(template_path):
                template_path = os.path.join("prompts", template_path)
                
            prompt_content = self.load_prompt_template(template_path)
            return prompt_content.format(**issue_content)
        except FileNotFoundError:
            raise ValueError(f"Prompt template not found: {template_path}")
        except KeyError as e:
            raise ValueError(f"Missing required field in issue_content: {e}")
            
    # Layer 1: Low-level text generation API
    def generate_text(self, prompt: str, llm_name: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate text using the specified LLM.
        
        This is a low-level API that wraps around LLM providers like OpenAI.
        
        Args:
            prompt: The formatted prompt to send to the LLM
            llm_name: Name of the LLM configuration to use
            **kwargs: Additional parameters to pass to the LLM
            
        Returns:
            Tuple containing:
              - Generated text response
              - Dictionary with response metrics (tokens, time, etc.)
            
        Raises:
            KeyError: If LLM configuration not found
            ValueError: If required API key not set
            RuntimeError: If LLM processing fails
        """
        if llm_name not in self.llm_configs:
            raise KeyError(f"LLM configuration not found: {llm_name}")
            
        config = self.llm_configs[llm_name]
        
        # Validate configuration
        if 'provider' not in config or 'model' not in config:
            raise ValueError(f"Invalid LLM configuration for {llm_name}. Missing provider or model.")
            
        # Dispatch to appropriate provider
        if config['provider'] == 'openai':
            return self._generate_with_openai(prompt, config, **kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {config['provider']}")
            
    def _generate_with_openai(self, 
                            prompt: str, 
                            config: Dict[str, Any],
                            **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Generate text using OpenAI API.
        
        Args:
            prompt: Formatted prompt
            config: OpenAI configuration dictionary
            **kwargs: Additional parameters to pass to the OpenAI API
            
        Returns:
            Tuple containing:
              - Generated text response
              - Dictionary with response metrics (tokens, time, etc.)
            
        Raises:
            RuntimeError: If API call fails
        """
        # Get API key from config or environment variable
        api_key = config.get('api_key')
        api_key_env = config.get('api_key_env')
        
        if api_key_env:
            api_key = os.environ.get(api_key_env)
            
        if not api_key:
            raise ValueError(f"API key not found for LLM configuration. Please check your models.yaml file or environment variables.")
        
        openai.api_key = api_key
        openai.base_url = config.get('base_url', "https://api.openai.com/v1")
        
        # Model parameters
        model_params = {
            'model': config['model'],
            'temperature': config.get('temperature', 0.0),
            'max_tokens': config.get('max_tokens', 2000),
            'top_p': config.get('top_p', 1.0),
            **kwargs  # Allow overriding with additional parameters
        }
        
        try:
            # Measure response time
            start_time = time.time()
            
            response = openai.chat.completions.create(
                model=model_params['model'],
                messages=[
                    {"role": "system", "content": "You are a code review assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=model_params['temperature'],
                max_tokens=model_params['max_tokens'],
                top_p=model_params['top_p']
            )
            
            # Calculate response time in milliseconds
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract content
            content = response.choices[0].message.content
            
            # Get token usage
            usage = {}
            if hasattr(response, 'usage'):
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            
            # Prepare response metrics
            response_metrics = {
                'full_prompt': prompt,
                'full_response': content,
                'prompt_tokens': usage.get('prompt_tokens'),
                'completion_tokens': usage.get('completion_tokens'),
                'total_tokens': usage.get('total_tokens'),
                'response_time_ms': response_time_ms,
                'model_parameters': model_params
            }
            
            return content, response_metrics
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
            
    # Layer 2: JSON extraction and validation API
    def extract_json(self, text: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract and validate JSON from LLM response text.
        
        Args:
            text: The text response from an LLM
            schema: JSON schema for validation (optional)
            
        Returns:
            Parsed and validated JSON object
            
        Raises:
            ValueError: If JSON cannot be extracted or fails validation
            json.JSONDecodeError: If text is not valid JSON
        """
        # Try to extract JSON from code blocks first
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # If no code blocks, try to find JSON-like content with braces
            brace_match = re.search(r'\{[\s\S]*\}', text)
            if brace_match:
                json_str = brace_match.group(0).strip()
            else:
                # If we still can't find JSON, use the entire response
                json_str = text.strip()
        
        try:
            result = json.loads(json_str)
            
            # Validate against schema if provided
            if schema:
                try:
                    jsonschema.validate(instance=result, schema=schema)
                except jsonschema.exceptions.ValidationError as e:
                    raise ValueError(f"JSON validation failed: {str(e)}")
                    
            return result
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {str(e)}")
            
    # Layer 3: High-level domain-specific API
    def classify_issue(self, 
                      issue_content: Dict[str, str], 
                      llm_name: str, 
                      prompt_template: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Classify an issue using specified LLM.
        
        This is a high-level API that composes the lower-level functions.
        
        Args:
            issue_content: Dictionary containing issue details
            llm_name: Name of LLM configuration to use
            prompt_template: Filename of the prompt template
            
        Returns:
            Tuple containing:
              - Dictionary with classification and explanation
              - Dictionary with response metrics (tokens, time, etc.)
            
        Raises:
            KeyError: If LLM configuration not found
            ValueError: If required API key not set or prompt template not found
            RuntimeError: If LLM processing fails
        """
        # Format prompt with issue content
        formatted_prompt = self.format_prompt(prompt_template, issue_content)
        
        # Generate text using the LLM
        response_text, response_metrics = self.generate_text(formatted_prompt, llm_name)
        
        # Extract and validate JSON from the response
        try:
            result = self.extract_json(response_text, self.classification_schema)
            return result, response_metrics
        except (ValueError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to extract valid classification from LLM response: {str(e)}")
            
    def get_token_counts(self, text: str, model: str) -> Dict[str, int]:
        """Estimate token counts for a given text and model.
        
        This is a fallback method when the API doesn't return token counts.
        For OpenAI, a rough estimate is 1 token ~= 4 chars for English text.
        
        Args:
            text: Text to count tokens for
            model: Model name (used to select appropriate tokenizer)
            
        Returns:
            Dictionary with estimated token count
        """
        # Very rough estimate for English text
        estimated_tokens = len(text) // 4
        
        return {
            'estimated_tokens': estimated_tokens
        } 