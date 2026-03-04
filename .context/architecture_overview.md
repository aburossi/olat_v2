# OLAT Workflow V2 Architecture Overview

## 1. The "Control Map": What Controls What?

| Feature | Controlled By | Location |
| :--- | :--- | :--- |
| **Input Reading** | `app.py` logic | `process_uploaded_file` function handles PDF (text/images), DOCX, and manual text input. |
| **Language** | Automatic Detection | `app.py` uses a frequency-based heuristic (`detect_language`) to identify the language and sends it as a "hint" to the LLM. |
| **Workflow Steps** | `STEP_FILES` Dictionary | Defined in `app.py`. For example, Step **H** is mapped to run four specific `.txt` instruction files in sequence. |
| **Question Logic** | Instruction Files | `v2_files/step_*.txt` defines *how* the LLM selects content (Bloom’s Taxonomy) and how many questions to make. |
| **Output Format** | JSON Schema | The instruction files now tell the LLM to output ONLY JSON. `app.py` then uses `parse_json_to_olat` to turn that JSON into the final tab-separated text. |

---

## 2. The Step-by-Step Workflow

The system uses a **Sequential Multi-Step Workflow**:

1.  **Input Collection**: User uploads files or pastes text.
2.  **Step Selection**: User chooses a workflow (A, B, C, D, E, or H).
3.  **Sequential Execution** (Backend Controlled):
    *   The app reads `app.py` to see which instruction files belong to that step.
    *   It calls the LLM for **each** file individually.
    *   *Example (Step H):* Calls the LLM for Closed Questions -> then separately for Open Questions -> then for Inline Choices -> then for Fill-in-the-Blanks.
4.  **JSON Parsing**: The LLM returns a specialized JSON object for each call.
5.  **OLAT Transformation**: The Python code in `app.py` parses that JSON and builds the final `.txt` file using the exact tabs and headers OLAT requires.

---

## 3. How to Customize the Behavior

*   **To change the "Style" or "Difficulty" of questions**: Edit the `v2_files/step_*.txt` files.
*   **To change the Number of Questions**: Update the `//instructions` in the relevant `step_*.txt` file.
*   **To add a New Question Type**: 
    1.  Add a new `step_custom.txt` instruction file.
    2.  Update the `parse_json_to_olat` function in `app.py` to recognize the new JSON structure.
    3.  Add the new file to the `STEP_FILES` list in `app.py`.

---

## 4. Why JSON?
Previously, the LLM was trying to "simulate" Python code to generate the OLAT format. This was brittle. Now, the LLM provides **Data** (JSON), and the **App** handles the **Formatting**. This makes the output much more consistent and less likely to have broken tabs or weird separators.
