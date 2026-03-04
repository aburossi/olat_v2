# Design System & Vibe

## The "Vibe"
- **Aesthetic:** Clean, Academic, and Functional.
- **Emotional Feel:** Trustworthy and efficient. It should feel like a professional tool for educators.
- **Motion:** Instant feedback via Streamlit status containers and progress indicators.

## Visual Rules
- **Layout:** Wide mode (`layout="wide"`) with an expanded sidebar for workflow controls.
- **Components:**
    - **Status Bars:** Use `st.status` to show the multi-step execution of LLM calls.
    - **Code Blocks:** Use `st.code` for the final OLAT output to allow easy copying.
    - **Download Action:** Primary visibility for the `.txt` download button after generation.

## Language Support
- **Multilingual:** The UI must adapt based on the detected language (English, German, French, Italian, Spanish).