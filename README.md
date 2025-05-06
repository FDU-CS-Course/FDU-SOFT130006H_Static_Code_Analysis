# Review Helper

A tool for classifying and reviewing cppcheck issues using Large Language Models (LLMs).

## Overview

Review Helper is designed to assist developers in processing and classifying issues identified by the cppcheck static analysis tool for C++ projects. It leverages Large Language Models (LLMs) to automatically classify issues as:

- **False positive**: The issue is not a real problem
- **Need fixing**: The issue should be fixed but is not critical
- **Very serious**: The issue is critical and must be fixed immediately

The application provides a user interface for reviewing LLM classifications and providing feedback, which helps improve the accuracy of future classifications.

## Features

- Load cppcheck issues from a CSV file
- Read source code and build context for LLM analysis
- Utilize LLMs to classify issues
- Review LLM classifications and provide feedback
- View statistics about LLM performance and issue distribution
- Support for multiple LLM providers and context-building strategies

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/review-helper.git
   cd review-helper
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on the `.env.example` template:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file to set your OpenAI API key and project root directory:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   REVIEW_HELPER_PROJECT_ROOT=/absolute/path/to/your/cpp/project
   ```

## Usage

1. Start the application:
   ```
   streamlit run app.py
   ```

2. Navigate to the application in your web browser (typically at http://localhost:8501)

3. Follow the workflow:
   - **Load Issues**: Upload a cppcheck CSV file or specify its path
   - **Run LLM**: Select an LLM and prompt template to classify issues
   - **Review Issues**: Review LLM classifications and provide feedback
   - **Statistics**: View statistics about LLM performance and issue distribution

## Configuration

### LLM Models

LLM models are configured in the `models.yaml` file. Example configuration:

```yaml
gpt4:
  provider: openai
  model: gpt-4
  api_key_env: OPENAI_API_KEY

gpt35turbo:
  provider: openai
  model: gpt-3.5-turbo
  api_key_env: OPENAI_API_KEY
  
deepseek-v3:
  provider: openai
  model: deepseek-chat
  api_key_env: DEEPSEEK_API_KEY
  base_url: https://api.deepseek.com
```

The `api_key_env` field specifies the environment variable that contains the API key for the corresponding LLM provider. Make sure to set these environment variables in your `.env` file or system environment.

### Context Building Strategies

The application supports different strategies for extracting code context around issues:

- **Fixed Lines**: Extracts a fixed number of lines before and after the issue line.
- **Function Scope**: Intelligently extracts the entire function containing the issue by analyzing code structure.

These strategies can be selected in the "Run LLM" page when processing issues.

### Prompt Templates

Prompt templates are stored in the `prompts/` directory as `.txt` files. The default template is `classification_default.txt`.

### Application Settings

The main application settings are in `config.py`:

- `PROJECT_ROOT_DIR`: Absolute path to the C++ project being analyzed
- `DEFAULT_LLM_UNIQUE_NAME`: Default LLM model to use
- `DEFAULT_PROMPT_TEMPLATE_FILENAME`: Default prompt template
- `DEFAULT_CONTEXT_STRATEGY`: Default strategy for context building
- `CONTEXT_LINES_COUNT`: Number of lines to include before and after the issue line

## CSV Format

The cppcheck CSV file should have the following columns:
- `File`: The path to the file with the issue
- `Line`: The line number where the issue was found
- `Severity`: The severity level (e.g., error, warning, style)
- `Id`: The cppcheck issue ID (e.g., nullPointer, divByZero)
- `Summary`: Description of the issue

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.


