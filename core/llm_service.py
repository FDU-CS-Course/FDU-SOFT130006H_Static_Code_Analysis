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
from typing import Dict, List, Optional, Any, Tuple
import yaml
from pathlib import Path
import openai
from dotenv import load_dotenv
import time

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
                      prompt_template: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Classify an issue using specified LLM.
        
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
        if llm_name not in self.llm_configs:
            raise KeyError(f"LLM configuration not found: {llm_name}")
            
        config = self.llm_configs[llm_name]
        
        # Validate configuration
        if 'provider' not in config or 'model' not in config:
            raise ValueError(f"Invalid LLM configuration for {llm_name}. Missing provider or model.")
            
        # Load the prompt template
        try:
            prompt_template_path = os.path.join("prompts", prompt_template)
            prompt_content = self.load_prompt_template(prompt_template_path)
        except FileNotFoundError:
            raise ValueError(f"Prompt template not found: {prompt_template}")
        
        # Format prompt with issue content
        formatted_prompt = prompt_content.format(**issue_content)
        
        # Dispatch to appropriate provider
        if config['provider'] == 'openai':
            return self._classify_with_openai(
                formatted_prompt,
                config
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {config['provider']}")
            
    def _classify_with_openai(self, 
                            prompt: str, 
                            config: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """Classify using OpenAI API.
        
        Args:
            prompt: Formatted prompt
            config: OpenAI configuration dictionary
            
        Returns:
            Tuple containing:
              - Dictionary with classification and explanation
              - Dictionary with response metrics (tokens, time, etc.)
            
        Raises:
            RuntimeError: If API call fails or response is invalid
            json.JSONDecodeError: If response is not valid JSON
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
            'top_p': config.get('top_p', 1.0)
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
            
            # Get token usage from response
            usage = {}
            if hasattr(response, 'usage'):
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            
            # Extract JSON from response
            json_str = content.split("```json")[1].split("```")[0].strip()
            
            try:
                result = json.loads(json_str)
                if not isinstance(result, dict) or "classification" not in result or "explanation" not in result:
                    raise ValueError("Invalid JSON structure")
                    
                # Validate classification value
                valid_classifications = ["false positive", "need fixing", "very serious"]
                if result["classification"] not in valid_classifications:
                    raise ValueError(f"Invalid classification value: {result['classification']}")
                
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
                
                return result, response_metrics
                
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSON response from LLM: {str(e)}")
            except ValueError as e:
                raise RuntimeError(f"Invalid response structure: {str(e)}")
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
            
    def format_prompt(self, 
                    prompt_template: str, 
                    issue_content: Dict[str, str]) -> str:
        """Format a prompt template with issue content.
        
        Args:
            prompt_template: Filename of the prompt template
            issue_content: Dictionary containing issue details
            
        Returns:
            Formatted prompt string
            
        Raises:
            ValueError: If prompt template not found
        """
        try:
            prompt_template_path = os.path.join("prompts", prompt_template)
            prompt_content = self.load_prompt_template(prompt_template_path)
            return prompt_content.format(**issue_content)
        except FileNotFoundError:
            raise ValueError(f"Prompt template not found: {prompt_template}")
            
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