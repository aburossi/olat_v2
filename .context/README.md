# OLAT Workflow V2

An intelligent pipeline for generating OpenOLAT-compatible educational content using LLMs and Bloom's Taxonomy.

## Quick Start
1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   # Ensure poppler-utils and ghostscript are installed on your system
Configure Secrets:
Add your openai api_key to .streamlit/secrets.toml.

Run App:

Bash
streamlit run v2_app/app.py
🤖 For AI Agents (Antigravity Context)
ATTENTION: Before modifying this codebase, you must ingest the governing rules and logic located in:

.antigravity/rules.md: Operational constraints.

.context/tech-stack.md: Permitted libraries and formatting rules.

.context/architecture.md: Understanding the JSON-to-OLAT transformation pipeline.

Features
Multi-format Support: PDF, DOCX, and Images.

Pedagogical Alignment: Questions mapped to Bloom’s Taxonomy.

OLAT Ready: Direct output of Tab-separated values for easy LMS import.