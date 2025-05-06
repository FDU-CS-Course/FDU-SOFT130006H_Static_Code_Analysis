"""
Configuration settings for the Review Helper application.
"""

import os
from typing import Optional

# Project root directory - absolute path to the C++ project being analyzed
PROJECT_ROOT_DIR: Optional[str] = os.environ.get("REVIEW_HELPER_PROJECT_ROOT", default="C:/CMS42/OpenSource/llama.cpp/")

# Default LLM configuration
DEFAULT_LLM_UNIQUE_NAME: Optional[str] = "gpt4"

# Default prompt template
DEFAULT_PROMPT_TEMPLATE_FILENAME: Optional[str] = "classification_default.txt"

# Context building settings
DEFAULT_CONTEXT_STRATEGY: str = "fixed_lines"
CONTEXT_LINES_COUNT: int = 5
CONTENT_LINES_MAX_COUNT: int = 1000  # Maximum lines to include in file-scope context
FILE_SCOPE_MAX_LINES: int = 1000  # Maximum lines to include in file-scope context

# Paths to configuration files
MODELS_CONFIG_PATH: str = "models.yaml"
PROMPTS_DIR_PATH: str = "prompts"

# Database path
DATABASE_PATH: str = "db/issues.db" 