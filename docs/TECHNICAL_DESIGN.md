# Technical Design: Review Helper

## 1. Introduction

This document outlines the technical design for the **Review Helper** application. The purpose of this application is to assist developers in processing and classifying issues identified by the cppcheck static analysis tool for C++ projects, leveraging Large Language Models (LLMs) for automated classification.

The primary goals are to:
- Load cppcheck issues from a CSV file.
- Read source code and build relevant context for LLM analysis.
- Utilize LLMs to classify issues as `false positive`, `need fixing`, or `very serious`.
- Provide an interface for users to review LLM classifications and provide feedback.
- Support multiple LLM providers and context-building strategies.

## 2. System Architecture

The application will be a web-based tool with the following architecture:

-   **Frontend**: Streamlit will be used for building the user interface.
-   **Backend**: Streamlit will also serve as the backend framework. Python will be used for all backend logic, including LLM interactions (via the OpenAI SDK and potentially others) and database operations.
-   **Database**: SQLite will be used for data persistence, storing cppcheck issues, LLM classifications, and user reviews.

### Tech Stack
-   **Web Framework**: Streamlit
-   **LLM Interaction**: OpenAI Python SDK (initially), designed for extension.
-   **Database ORM/Driver**: Python's built-in `sqlite3` module.
-   **Programming Language**: Python

## 3. Project File Structure

```
review_helper/
├── app.py                   # Main Streamlit application entry point, navigation
├── core/
│   ├── __init__.py
│   ├── llm_service.py       # Handles LLM interactions (OpenAI, other models)
│   ├── context_builder.py   # Strategies for building context for LLMs
│   ├── issue_parser.py      # Parses cppcheck CSV output
│   └── data_manager.py      # Handles database interactions (SQLite)
├── db/
│   └── issues.db            # SQLite database file (gitignored)
├── pages/                   # Streamlit pages for multi-page app structure
│   ├── __init__.py
│   ├── 01_Load_Issues.py    # Page for loading/viewing cppcheck issues
│   ├── 02_Run_LLM.py        # Page for selecting LLM, prompt, and running processing
│   ├── 03_Review_Issues.py  # Page for reviewing LLM classifications
│   └── 04_Statistics.py     # Page for comparing LLM and context strategy performance
├── prompts/                 # Directory for LLM prompt templates
│   ├── classification_default.txt # Example prompt template
│   └── ...                  # Other prompt templates
├── tests/                   # Unit and integration tests
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_llm_service.py
│   │   ├── test_context_builder.py
│   │   └── test_issue_parser.py
│   └── test_app.py
├── utils/                   # Utility functions
│   ├── __init__.py
│   └── file_utils.py        # File system utilities, security checks
├── .env.example             # Example environment variables
├── .gitignore
├── config.py                # Application configuration (e.g., project root path, default selections)
├── models.yaml              # LLM provider and model configurations (NEW)
├── requirements.txt         # Python dependencies
├── README.md                # Project overview
└── docs/
    └── TECHNICAL_DESIGN.md  # This document
```

## 4. Detailed Component Design

### 4.1. Frontend (Streamlit)

-   **`app.py`**:
    -   Main entry point for the Streamlit application.
    -   Handles global configurations, session state initialization, and navigation structure.
-   **`pages/`**:
    -   **`01_Load_Issues.py`**:
        -   Provides a UI for users to upload a cppcheck CSV file or specify its path.
        -   Displays a summary of loaded issues.
        -   Triggers the parsing and storage of issues.
    -   **`02_Run_LLM.py`**:
        -   Displays a list of LLM configurations and prompt templates.
        -   Allows users to select an LLM configuration and prompt template.
        -   Triggers the LLM processing of issues.
    -   **`03_Review_Issues.py`**:
        -   Displays a list of issues with their details, LLM-generated classifications, and code context.
        -   Provides an interface for users to validate or correct LLM classifications and add comments.
    -   **`04_Statistics.py`**:
        -   Displays statistics related to LLM performance and context strategy effectiveness.

### 4.2. Backend Logic (`core/`)

-   **`issue_parser.py`**:
    -   **`parse_cppcheck_csv(file_path_or_buffer: Union[str, io.BytesIO]) -> List[Dict[str, Any]]`**:
        -   Takes a file path or an in-memory file buffer.
        -   Parses the cppcheck CSV data, correctly handling potential commas within the `Summary` field.
        -   Expected CSV columns: `File`, `Line`, `Severity`, `Id`, `Summary`.
        -   Returns a list of dictionaries, each representing an issue.
-   **`context_builder.py`**:
    -   **`build_context(file_path: str, line_number: int, strategy: str = "fixed_lines", project_root: str, **kwargs) -> str`**:
        -   Reads the content of the specified `file_path` (validated to be within `project_root`).
        -   Extracts a code snippet around the `line_number` based on the chosen `strategy`.
        -   Possible strategies:
            -   `fixed_lines`: N lines before and after the issue line.
            -   `function_scope`: (Future enhancement) Tries to extract the entire function containing the issue.
        -   Returns the extracted code context as a string. Requires `file_utils.is_path_safe` check.
-   **`llm_service.py`**:
    -   Defines an interface or base class for LLM interactions to support multiple providers.
    -   **`load_llm_configurations(config_path: str = "models.yaml") -> Dict[str, Any]`**:
        -   Loads LLM configurations from the specified YAML file (e.g., `models.yaml`).
        -   Parses details like API endpoint, model name, API key environment variable name for each uniquely named model.
        -   Returns a dictionary of model configurations.
    -   **`list_prompt_templates(prompts_dir: str = "prompts") -> List[str]`**:
        -   Scans the `prompts/` directory for available `.txt` prompt templates.
        -   Returns a list of template file names.
    -   **`load_prompt_template(template_path: str) -> str`**:
        -   Reads the content of a specified prompt template file.
        -   Returns the prompt template string.
    -   **`classify_issue(issue_summary: str, code_context: str, llm_config: Dict[str, Any], prompt_template: str) -> Dict[str, str]`**:
        -   Takes `llm_config` (a specific model's configuration loaded from `models.yaml`) and a `prompt_template` string.
        -   Formats the `prompt_template` with `issue_summary` and `code_context`.
        -   Interacts with the LLM provider specified in `llm_config` (e.g., OpenAI, Ollama, other API).
        -   Retrieves the API key using the environment variable name specified in `llm_config`.
        -   Sends the request to the configured LLM.
        -   Parses the LLM response to extract the classification (e.g., `false positive`, `need fixing`, `very serious`) and any explanation.
        -   Returns a dictionary with `classification` and `explanation`.
-   **`data_manager.py`**:
    -   Manages all interactions with the SQLite database (`db/issues.db`).
    -   **`init_db()`**: Creates database tables if they don't exist.
    -   **`add_issues(issues: List[Dict[str, Any]])`**: Adds new issues parsed from cppcheck CSV to the database.
    -   **`get_issue_by_id(issue_id: int) -> Optional[Dict[str, Any]]`**: Retrieves a specific issue with all its LLM classifications.
    -   **`get_all_issues(filters: Optional[Dict] = None) -> List[Dict[str, Any]]`**: Retrieves all issues, optionally applying filters (e.g., unclassified, specific severity).
    -   **`add_llm_classification(issue_id: int, llm_model_name: str, context_strategy: str, prompt_template: str, source_code_context: str, classification: str, explanation: Optional[str] = None) -> int`**: Adds a new LLM classification attempt to the database. Returns the ID of the new classification.
    -   **`update_llm_classification_review(classification_id: int, user_agrees: bool, user_comment: Optional[str] = None)`**: Updates user feedback for a specific LLM classification attempt.
    -   **`set_issue_true_classification(issue_id: int, classification: str, comment: Optional[str] = None)`**: Sets the final verified classification for an issue.
    -   **`get_llm_statistics(filters: Optional[Dict] = None) -> Dict[str, Any]`**: Retrieves statistics about LLM performance, context strategies, and prompt templates, optionally filtered by various criteria.

### 4.3. Configuration (`config.py`)

-   **`PROJECT_ROOT_DIR: Optional[str]`**: Server-side configuration specifying the absolute path to the root directory of the C++ project being analyzed. This is crucial for security and for `context_builder.py` to locate source files. This should be configurable by the user, perhaps through an initial setup screen or a config file not checked into VCS.
-   **`DEFAULT_LLM_UNIQUE_NAME: Optional[str]`**: (Updated) Unique name of the default LLM configuration to use from `models.yaml`.
-   **`DEFAULT_PROMPT_TEMPLATE_FILENAME: Optional[str]`**: (NEW) Filename of the default prompt template from the `prompts/` directory (e.g., "classification_default.txt").
-   **`DEFAULT_CONTEXT_STRATEGY: str`**: Default strategy for context building (e.g., "fixed_lines").
-   **`CONTEXT_LINES_COUNT: int`**: Number of lines to include before and after the issue line for the "fixed_lines" strategy.
-   **`MODELS_CONFIG_PATH: str = "models.yaml"`**: (NEW) Path to the LLM configurations file.
-   **`PROMPTS_DIR_PATH: str = "prompts"`**: (NEW) Path to the directory containing prompt templates.

### 4.4. Utilities (`utils/file_utils.py`)

-   **`is_path_safe(file_path: str, project_root: str) -> bool`**:
    -   Validates if the `file_path` (obtained from cppcheck output) is a sub-path of the configured `project_root`.
    -   Normalizes paths to prevent directory traversal attacks (e.g., `../../`).
    -   Returns `True` if safe, `False` otherwise.
-   **`read_file_lines(file_path: str, start_line: int, end_line: int) -> str`**:
    -   Reads specific lines from a file. Used by `context_builder.py`. Ensures `file_path` is safe before reading.

## 5. Data Models (SQLite)

The primary database will be `db/issues.db`.

**Table: `issues`**

| Column                | Type                      | Constraints                       | Description                                                                 |
| --------------------- | ------------------------- | --------------------------------- | --------------------------------------------------------------------------- |
| `id`                  | INTEGER                   | PRIMARY KEY AUTOINCREMENT         | Unique identifier for the issue in this system.                             |
| `cppcheck_file`       | TEXT                      | NOT NULL                          | File path from cppcheck output.                                             |
| `cppcheck_line`       | INTEGER                   | NOT NULL                          | Line number from cppcheck output.                                           |
| `cppcheck_severity`   | TEXT                      | NOT NULL                          | Severity from cppcheck (e.g., `error`, `warning`, `style`).                 |
| `cppcheck_id`         | TEXT                      | NOT NULL                          | Issue ID from cppcheck (e.g., `nullPointer`).                               |
| `cppcheck_summary`    | TEXT                      | NOT NULL                          | Summary message from cppcheck.                                              |
| `true_classification` | TEXT                      |                                   | Final verified classification (e.g., `false positive`, `need fixing`, `very serious`). |
| `true_classification_comment` | TEXT               |                                   | Optional comment explaining the true classification.                        |
| `status`              | TEXT                      | NOT NULL DEFAULT 'pending_llm'    | e.g., 'pending_llm', 'pending_review', 'reviewed'.                          |
| `created_at`          | TIMESTAMP                 | NOT NULL DEFAULT CURRENT_TIMESTAMP | Timestamp when the issue was first added to the DB.                         |
| `updated_at`          | TIMESTAMP                 | NOT NULL DEFAULT CURRENT_TIMESTAMP | Timestamp when the issue was last updated.                                  |

**Table: `llm_classifications`**

| Column                | Type                      | Constraints                       | Description                                                                 |
| --------------------- | ------------------------- | --------------------------------- | --------------------------------------------------------------------------- |
| `id`                  | INTEGER                   | PRIMARY KEY AUTOINCREMENT         | Unique identifier for this classification attempt.                          |
| `issue_id`            | INTEGER                   | NOT NULL, FOREIGN KEY             | References `issues.id`.                                                     |
| `llm_model_name`      | TEXT                      | NOT NULL                          | Name of the LLM model used (from models.yaml).                              |
| `context_strategy`    | TEXT                      | NOT NULL                          | Strategy used to build context (e.g., 'fixed_lines', 'function_scope').     |
| `prompt_template`     | TEXT                      | NOT NULL                          | Name of the prompt template used.                                           |
| `source_code_context` | TEXT                      | NOT NULL                          | Code context provided to the LLM.                                           |
| `classification`      | TEXT                      | NOT NULL                          | Classification by LLM (e.g., `false positive`, `need fixing`, `very serious`). |
| `explanation`         | TEXT                      |                                   | Optional explanation or reasoning from the LLM.                             |
| `processing_timestamp`| TIMESTAMP                 | NOT NULL DEFAULT CURRENT_TIMESTAMP | When the LLM processing was completed.                                      |
| `user_agrees`         | BOOLEAN                   |                                   | User's feedback: `True` if LLM was correct, `False` if incorrect.           |
| `user_comment`        | TEXT                      |                                   | Optional comment from the user during review.                               |

*An SQLite trigger can be used to automatically update `updated_at` in the `issues` table.*

## 6. Workflow

1.  **Configuration**:
    *   Admin/User sets `PROJECT_ROOT_DIR` in `config.py` or via an environment variable. This is the root directory of the C++ project to be analyzed.
    *   LLM configurations are defined in `models.yaml`. API keys referenced in `models.yaml` are set as environment variables.
    *   Prompt templates are placed in the `prompts/` directory.
    *   Default LLM and prompt template can be set in `config.py`.

2.  **Load Issues (`pages/01_Load_Issues.py`)**:
    *   User uploads a cppcheck CSV output file.
    *   `issue_parser.py` parses the CSV into a list of issue dictionaries.
    *   For each issue, `data_manager.py` saves it to the `issues` table in SQLite with an initial `status` of `pending_llm`. The `cppcheck_file` path is stored as is.

3.  **LLM Processing (`pages/02_Run_LLM.py`)**:
    *   User navigates to the "Run LLM" page.
    *   The page lists available LLM configurations (from `models.yaml` via `llm_service.py`) and prompt templates (from `prompts/` via `llm_service.py`).
    *   User selects the desired LLM configuration, prompt template, and context building strategy.
    *   User can filter issues to be processed (e.g., those with `status = 'pending_llm'`).
    *   User clicks "Start Processing".
    *   For each selected issue:
        *   The absolute path to the source file is constructed: `os.path.join(config.PROJECT_ROOT_DIR, issue.cppcheck_file)`.
        *   `utils.file_utils.is_path_safe()` validates this path against `config.PROJECT_ROOT_DIR`. **If unsafe, the issue is flagged, and LLM processing is skipped for it.**
        *   If safe, `context_builder.py` reads the source file and extracts the `source_code_context` based on the selected strategy.
        *   `llm_service.py` loads the selected prompt template content.
        *   `llm_service.py` uses the selected `llm_config` and `prompt_template` to call `classify_issue()`.
        *   The LLM's `classification` and `explanation` are received.
        *   `data_manager.py` adds a new record to the `llm_classifications` table with the classification details.
        *   If this is the first classification for the issue, its `status` is updated to `pending_review`.
    *   The page displays progress (e.g., number of issues processed/remaining, errors).
    *   User has an option to "Stop Processing". This will require the backend processing loop to check a flag (e.g., in Streamlit session state or a temporary marker) between issues and halt if the flag is set.

4.  **Review Issues (`pages/03_Review_Issues.py`)**:
    *   The user navigates to the review page.
    *   `data_manager.py` fetches issues, typically those with `status = 'pending_review'` or all issues with filters.
    *   For each issue, the UI displays:
        *   Issue details from cppcheck
        *   All LLM classification attempts from the `llm_classifications` table
        *   The current `true_classification` if set
    *   The user can:
        *   Review each LLM classification attempt and mark if they agree with it (`user_agrees`)
        *   Add comments to individual LLM attempts (`user_comment`)
        *   Set the final `true_classification` for the issue and add a `true_classification_comment`
    *   `data_manager.py` saves this feedback to the database and updates the issue's `status` to `reviewed` when a `true_classification` is set.

5.  **Statistics (`pages/04_Statistics.py`)**:
    *   The user navigates to the statistics page.
    *   The page provides various metrics and visualizations:
        *   Overall accuracy of each LLM model
        *   Performance comparison of different context building strategies
        *   Success rate of different prompt templates
        *   Distribution of classifications (false positives vs. need fixing vs. very serious)
        *   Time-based analysis of LLM performance
    *   Users can filter statistics by:
        *   Date range
        *   Issue severity
        *   Specific LLM models
        *   Context strategies
        *   Prompt templates
    *   The page allows exporting statistics in various formats (CSV, JSON) for further analysis.

## 7. Extensibility

-   **Multiple LLMs**:
    -   `llm_service.py` will load configurations from `models.yaml`, allowing easy addition of new LLM providers or models by updating this YAML file (and ensuring corresponding API key environment variables are set).
    -   The core `classify_issue` function in `llm_service.py` will be designed to work with different provider details specified in the configuration.
    -   The choice of LLM is made by the user on the `02_Run_LLM.py` page.
-   **Context Building Strategies**:
    -   `context_builder.py` will allow for different strategies to be implemented and selected.
    -   New strategies (e.g., AST-based context extraction) can be added as new functions or classes.
    -   The choice of strategy can be made configurable.
-   **Prompt Templating**: (NEW)
    -   Users can create and manage multiple prompt templates in `.txt` files within the `prompts/` directory.
    -   The `02_Run_LLM.py` page allows users to select which prompt template to use for a processing run, enabling experimentation with different prompting techniques.

## 8. Security Considerations

-   **File Path Validation**:
    -   This is paramount. All file paths derived from cppcheck output (`cppcheck_file`) **must** be rigorously validated by `utils.file_utils.is_path_safe()` to ensure they resolve to a location within the configured `PROJECT_ROOT_DIR` before any file system access (read operations by `context_builder.py`). This prevents directory traversal attacks.
    -   The application should clearly log or mark issues where file paths are outside the allowed project root.
-   **API Key Management**:
    -   API keys (e.g., `OPENAI_API_KEY`) must not be hardcoded in the source code or in `models.yaml` directly if they are sensitive.
    -   `models.yaml` should specify the *name of the environment variable* that holds the API key. These environment variables should be loaded (e.g., using `python-dotenv` from a `.env` file which is gitignored) or set in the deployment environment.
    -   `.env.example` should be provided to guide users on setting up these environment variables.
-   **Input Sanitization**:
    -   While Streamlit handles much of the HTML escaping, be cautious with any data that might be rendered directly or used in constructing file paths or database queries if not already handled by parameterized queries.
    -   The cppcheck `Summary` field, as it can contain commas, should be handled carefully during parsing but is generally safe for display.
-   **Database Security**:
    -   Use parameterized queries for all database interactions (standard practice with `sqlite3` placeholders) to prevent SQL injection.
-   **Error Handling**:
    -   Gracefully handle errors such as missing files, incorrect LLM API responses, or database connection issues. Do not expose sensitive error details to the frontend.

## 9. Deployment Considerations (Brief)

-   The application can be run locally using `streamlit run app.py`.
-   For wider access, it can be deployed using Streamlit Sharing, Docker, or other common Python web app deployment methods.
-   Ensure `PROJECT_ROOT_DIR` and API keys are configured correctly in the deployment environment.

## 10. Future Enhancements (Optional)

-   **Batch Processing**: Option to trigger LLM classification for all pending issues in a batch.
-   **Advanced Context Building**: Implement context strategies based on Abstract Syntax Tree (AST) parsing for more precise code snippets.
-   **Direct Cppcheck Integration**: Explore running cppcheck from within the tool or monitoring its output directory.
-   **User Authentication**: If multiple users need to access the tool with distinct roles or data.
-   **Reporting & Analytics**: Dashboards to show LLM accuracy, types of issues found, review progress, etc.
-   **Configuration UI**: Allow setting `PROJECT_ROOT_DIR` and LLM settings through the UI instead of just config files/env vars, especially for initial setup.
