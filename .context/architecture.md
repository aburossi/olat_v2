# System Architecture

## High-Level Overview
The application is a stateless Streamlit wrapper that orchestrates communication between the user's local files, remote GitHub-hosted prompts, and the OpenAI API.

## Data Flow
1. **Input Layer:** User uploads files or enters text -> Language detection determines the UI locale.
2. **Instruction Layer:** App checks `v2_files/` locally, then falls back to GitHub `RAW_BASE_URL` to fetch `.txt` prompts.
3. **Inference Layer:** Content + Prompt + Images are sent to OpenAI (`gpt-4o`).
4. **Parsing Layer:** Raw LLM JSON is sanitized and transformed via `parse_json_to_olat` into the proprietary OLAT Tab-delimited format.
5. **Output Layer:** Streamlit renders the text and provides a download link.

## Directory Structure Logic
- `/v2_app`: Main application logic (`app.py`).
- `/v2_files`: Instructional "Context" files (Prompts, Schemas, Bloom definitions).
- `/root`: Dependency management (`requirements.txt`, `packages.txt`).