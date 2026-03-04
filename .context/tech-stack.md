# Technology Stack & Constraints

## Core Frameworks
- **Language:** Python 3.12+
- **Frontend/UI:** Streamlit (1.38.0)
- **AI Integration:** OpenAI API (v2.24.0+)
- **Models:** `gpt-5.2`, `gpt-5-mini`

## Critical Libraries
- **Document Processing:** PyPDF2 (PDF text), pdf2image & Pillow (PDF/Image OCR), python-docx (Word).
- **Networking:** httpx (Remote prompt fetching).
- **Environment:** Streamlit Cloud Secrets for API keys.

## Strict Constraints
- **Encoding:** All file reads/writes must use `UTF-8`.
- **Formatting:** Maintain the specific tab-delimited structure required by the OLAT import engine.
- **No Heavy OCR:** Use `pdf2image` only as a fallback if `PyPDF2` fails to extract text.
- **Dependencies:** System-level dependencies (`poppler-utils`, `ghostscript`) must be defined in `packages.txt`.