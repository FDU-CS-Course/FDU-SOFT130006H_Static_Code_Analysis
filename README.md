# Review Helper

## Background

- We've scanned a cpp project with a tool called cppcheck.
- Many issues were found, some were serious, some need fixing, some are false positives.
- We want to test if we can use AI to help us fix these issues.

## What we're going to do

This tool will be a web app. It can:

1. Load in the cppcheck issues (csv format)
2. Read the source code and build context for LLMs (with different strategies)
3. Use LLMs to:
   - Classify issues as `false positive`, `need fixing`, `very serious`
4. Allow users to review the issues and tell whether the LLM's classification is correct

It should support multiple LLMs and multiple context building strategies.

## Tech stack

- Frontend&Backend: streamlit
- LLM: openai SDK for Python
- Database: sqlite

## Input format

Cppcheck's output format:

`File, Line, Severity, Id, Summary`

Notice that `Summary` may contain commas.

Code input:

`File` would be the path to the related source code file.

A server-side config will specify the project root directory, use it to check if the file is within the project (for security).

## Design doc

See [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md)


