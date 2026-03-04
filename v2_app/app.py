import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docx
import httpx
import PyPDF2
import streamlit as st
from openai import OpenAI
from pdf2image import convert_from_bytes
from PIL import Image


st.set_page_config(
    page_title="OLAT Workflow V2",
    page_icon="[v2]",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)

for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(env_var, None)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_V2_DIR = REPO_ROOT / "v2_files"
RAW_BASE_URL = "https://raw.githubusercontent.com/aburossi/prompts/main/olatimport"
MODEL_CANDIDATES = ["gpt-4o", "gpt-4-turbo"]
MAX_IMAGE_ATTACHMENTS = 12

STEP_FILES: Dict[str, List[str]] = {
    "A": ["step_closed_questions.txt"],
    "B": ["step_open_questions.txt"],
    "C": ["step_closed_questions.txt", "step_open_questions.txt"],
    "D": ["step_dragthewords.txt"],
    "E": ["step_filltheblanks.txt"],
    "H": [
        "step_closed_questions.txt",
        "step_open_questions.txt",
        "step_dragthewords.txt",
        "step_filltheblanks.txt",
    ],
}

STEP_LABELS = {
    "en": {
        "A": "A) Closed questions",
        "B": "B) Open questions",
        "C": "C) Mixed closed and open questions",
        "D": "D) Inline choice questions",
        "E": "E) Fill in the blanks",
        "H": "H) Full course workflow",
    },
    "de": {
        "A": "A) Geschlossene Fragen",
        "B": "B) Offene Fragen",
        "C": "C) Mischung aus geschlossenen und offenen Fragen",
        "D": "D) Inline-Choice Fragen",
        "E": "E) Lueckentexte",
        "H": "H) Vollstaendiger Kursablauf",
    },
}

LANG_HINT = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "es": "Spanish",
}


def parse_json_to_olat(json_str: str) -> str:
    """Converts the generated JSON format to the OLAT import text format."""
    try:
        # Extract JSON from markdown code block if present
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        data = json.loads(json_str)
        questions = data.get("questions", [])
        output_blocks = []

        for q in questions:
            q_type = q.get("type", "SC")
            title = q.get("title", "Question")
            text = q.get("question") or q.get("text") or q.get("instructions")
            points = q.get("points", 1)

            if q_type == "SC":
                block = [f"Typ\tSC", f"Title\t{title}", f"Question\t{text}", f"Points\t{points}"]
                for ans in q.get("answers", []):
                    block.append(f"{ans.get('points')}\t{ans.get('text')}")
                output_blocks.append("\n".join(block))

            elif q_type == "MC":
                max_ans = q.get("max_answers", 4)
                min_ans = q.get("min_answers", 0)
                block = [f"Typ\tMC", f"Title\t{title}", f"Question\t{text}", f"Max answers\t{max_ans}", f"Min answers\t{min_ans}", f"Points\t{points}"]
                for ans in q.get("answers", []):
                    block.append(f"{ans.get('points')}\t{ans.get('text')}")
                output_blocks.append("\n".join(block))

            elif q_type == "KPRIM":
                block = [f"Typ\tKPRIM", f"Title\t{title}", f"Question\t{text}", f"Points\t{points}"]
                for ans in q.get("answers", []):
                    prefix = "+" if ans.get("correct") else "-"
                    block.append(f"{prefix}\t{ans.get('text')}")
                output_blocks.append("\n".join(block))

            elif q_type == "Truefalse":
                block = [f"Typ\tTruefalse", f"Title\t{title}", f"Question\t{text}", f"Points\t{points}", "\tUnanswered\tRight\tWrong"]
                for stmt in q.get("statements", []):
                    r, w = (1, -0.5) if stmt.get("correct") else (-0.5, 1)
                    block.append(f"{stmt.get('text')}\t0\t{r}\t{w}")
                output_blocks.append("\n".join(block))

            elif q_type == "FIB":
                ans = q.get("answer")
                length = q.get("length", 150)
                block = [f"Typ\tFIB", f"Title\t{title}", f"Points\t{points}", f"Text\t{text}", f"{points}\t{ans}\t{length}"]
                output_blocks.append("\n".join(block))

            elif q_type == "ESSAY":
                min_c = q.get("min_chars", 200)
                max_c = q.get("max_chars", 2000)
                block = [f"Typ\tESSAY", f"Title\t{title}", f"Question\t{text}", f"Points\t{points}", f"Min\t{min_c}", f"Max\t{max_c}"]
                output_blocks.append("\n".join(block))

            elif q_type == "Inlinechoice":
                segments = q.get("text_segments", [])
                instructions = q.get("instructions", "Vervollständigen Sie den Text.")
                all_correct_options = [s.get("blank") for s in segments if "blank" in s]
                
                output = [
                    "Typ\tInlinechoice",
                    f"Title\t{title}",
                    f"Question\t{instructions}",
                    f"Points\t{len(all_correct_options)}",
                    "Text\t✏"
                ]
                
                for seg in segments:
                    if "text" in seg:
                        output.append(f"Text\t{seg['text'].strip()}")
                    if "blank" in seg:
                        correct = seg["blank"]
                        options = seg.get("all_options", [correct])
                        options_str = ";".join(options)
                        output.append(f"1\t{options_str}\t{correct}")
                
                output_blocks.append("\n".join(output))

        return "\n\n".join(output_blocks)
    except Exception as e:
        logging.error(f"JSON parsing failed: {e}")
        return json_str # Fallback to raw output


@st.cache_data(show_spinner=False)
def read_text_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace").strip()


def detect_language(text: str) -> str:
    lowered = text.lower()
    if not lowered.strip():
        return "en"
    scores = {
        "de": sum(token in lowered for token in [" und ", " der ", " die ", " das ", "nicht", "frage"]),
        "fr": sum(token in lowered for token in [" le ", " la ", " les ", "des", "et", "question"]),
        "it": sum(token in lowered for token in [" il ", " lo ", " gli ", "che", "domanda", "testo"]),
        "es": sum(token in lowered for token in [" el ", " la ", " los ", "las", "que", "pregunta"]),
        "en": sum(token in lowered for token in [" the ", " and ", "what", "question", "text"]),
    }
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "en"


def encode_image_for_openai(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    chunks: List[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            chunks.append(page_text)
    return "\n".join(chunks).strip()


def process_uploaded_file(uploaded_file) -> Tuple[str, List[Image.Image], List[str]]:
    warnings: List[str] = []
    file_bytes = uploaded_file.getvalue()
    file_name = getattr(uploaded_file, "name", "uploaded_file")

    if uploaded_file.type == "application/pdf":
        text = extract_text_from_pdf_bytes(file_bytes)
        if text:
            labeled_text = f"[Source: {file_name}]\n{text}"
            return labeled_text, [], warnings
        try:
            images = convert_from_bytes(file_bytes)
            if images:
                warnings.append(f"No OCR text found in {file_name}. Using PDF pages as images.")
                return "", images, warnings
        except Exception as exc:
            warnings.append(f"PDF conversion failed: {exc}")
        return "", [], warnings

    if uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs).strip()
        labeled_text = f"[Source: {file_name}]\n{text}" if text else ""
        return labeled_text, [], warnings

    if uploaded_file.type.startswith("image/"):
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        return "", [image], warnings

    return "", [], ["Unsupported file type."]


def process_uploaded_files(uploaded_files) -> Tuple[str, List[Image.Image], List[str]]:
    text_chunks, images, warnings = [], [], []
    for f in uploaded_files:
        t, i, w = process_uploaded_file(f)
        if t: text_chunks.append(t)
        if i: images.extend(i)
        if w: warnings.extend(w)
    return "\n\n".join(text_chunks).strip(), images, warnings


def fetch_remote_text(path_name: str) -> Optional[str]:
    url = f"{RAW_BASE_URL}/{path_name}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            if response.status_code == 200:
                return response.text.strip()
    except Exception:
        pass
    return None


def load_instruction_file(filename: str) -> Tuple[Optional[str], str]:
    local_path = LOCAL_V2_DIR / filename
    content = read_text_file(local_path)
    if content: return content, f"local:{filename}"
    remote = fetch_remote_text(filename)
    if remote: return remote, f"remote:{filename}"
    return None, "missing"


def get_openai_client() -> Optional[OpenAI]:
    try:
        api_key = st.secrets["openai"]["api_key"]
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"API Key error: {e}")
        return None


def call_model(
    client: OpenAI,
    instruction_payload: str,
    user_input: str,
    language_hint: str,
    step_filename: str,
    images: List[Image.Image],
) -> str:
    system_prompt = (
        "You are an educational content generator for OpenOLAT imports. "
        "Strictly follow the provided JSON instructions. "
        "Output ONLY the JSON in a code box. "
        "Do not ask questions or provide explanations."
    )
    
    content_items = [{"type": "text", "text": f"Instruction File: {step_filename}\nLanguage: {language_hint}\n\nContent:\n{user_input}\n\n{instruction_payload}"}]
    for img in images[:MAX_IMAGE_ATTACHMENTS]:
        content_items.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image_for_openai(img)}", "detail": "low"}})

    for model in MODEL_CANDIDATES:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": content_items}],
                temperature=0.3,
                max_completion_tokens=4000
            )
            return resp.choices[0].message.content or ""
        except Exception:
            continue
    return "Error: All model attempts failed."


def main():
    st.title("OLAT Workflow V2 [Enhanced]")
    st.caption("Backend-controlled Multi-step Workflow with JSON Parsing.")

    uploaded_files = st.file_uploader("Upload materials", type=["pdf", "docx", "jpg", "png"], accept_multiple_files=True)
    extracted_text, images, warnings = process_uploaded_files(uploaded_files) if uploaded_files else ("", [], [])
    
    for w in warnings: st.warning(w)
    user_input = st.text_area("Input Text or Topic", value=extracted_text, height=200)
    
    lang = detect_language(user_input)
    labels = STEP_LABELS.get(lang, STEP_LABELS["en"])
    selected_step = st.radio("Step", options=list(STEP_FILES.keys()), format_func=lambda k: labels.get(k, k))

    if st.button("Generate", type="primary"):
        if not user_input.strip() and not images:
            st.warning("Please provide input.")
            st.stop()
            
        client = get_openai_client()
        if not client: st.stop()
        
        steps = STEP_FILES[selected_step]
        final_output = []
        
        with st.status("Executing Workflow...") as status:
            for step_file in steps:
                status.write(f"Processing {step_file}...")
                content, source = load_instruction_file(step_file)
                if content:
                    raw_json = call_model(client, content, user_input, LANG_HINT.get(lang, "English"), step_file, images)
                    olat_format = parse_json_to_olat(raw_json)
                    final_output.append(olat_format)
                else:
                    st.error(f"Missing instructions: {step_file}")
            status.update(label="Complete!", state="complete")

        st.subheader("Generated OLAT Content")
        combined_text = "\n\n".join(final_output)
        st.code(combined_text, language="text")
        st.download_button("Download .txt", combined_text, file_name="olat_import.txt")


if __name__ == "__main__":
    main()
