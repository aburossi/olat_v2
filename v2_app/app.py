import base64
import io
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
MODEL_NAME = "gpt-4o"

STEP_FILES: Dict[str, List[str]] = {
    "A": ["step_closed_questions.txt"],
    "B": ["step_open_questions.txt"],
    "C": ["step_closed_questions.txt", "step_open_questions.txt"],
    "D": ["step_dragthewords.txt"],
    "E": ["step_filltheblanks.txt"],
    "F": ["step_html_page.txt"],
    "G": ["step_mindmap.txt"],
    "H": [
        "step_full_course.txt",
        "step_mindmap.txt",
        "step_html_page.txt",
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
        "D": "D) Drag the words",
        "E": "E) Fill in the blanks",
        "F": "F) Educational HTML page",
        "G": "G) Mindmap in HTML",
        "H": "H) Full course workflow",
    },
    "de": {
        "A": "A) Geschlossene Fragen",
        "B": "B) Offene Fragen",
        "C": "C) Mischung aus geschlossenen und offenen Fragen",
        "D": "D) Drag the words",
        "E": "E) Lueckentexte",
        "F": "F) HTML-Lernseite",
        "G": "G) Mindmap in HTML",
        "H": "H) Vollstaendiger Kursablauf",
    },
    "fr": {
        "A": "A) Questions fermees",
        "B": "B) Questions ouvertes",
        "C": "C) Melange questions fermees et ouvertes",
        "D": "D) Drag the words",
        "E": "E) Texte a trous",
        "F": "F) Page HTML educative",
        "G": "G) Mindmap en HTML",
        "H": "H) Workflow cours complet",
    },
    "it": {
        "A": "A) Domande chiuse",
        "B": "B) Domande aperte",
        "C": "C) Mix domande chiuse e aperte",
        "D": "D) Drag the words",
        "E": "E) Fill in the blanks",
        "F": "F) Pagina HTML educativa",
        "G": "G) Mindmap in HTML",
        "H": "H) Workflow corso completo",
    },
    "es": {
        "A": "A) Preguntas cerradas",
        "B": "B) Preguntas abiertas",
        "C": "C) Mezcla de preguntas cerradas y abiertas",
        "D": "D) Drag the words",
        "E": "E) Rellenar huecos",
        "F": "F) Pagina HTML educativa",
        "G": "G) Mindmap en HTML",
        "H": "H) Flujo curso completo",
    },
}

LANG_HINT = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "es": "Spanish",
}


@st.cache_data(show_spinner=False)
def read_text_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace").strip()


def detect_language(text: str) -> str:
    lowered = text.lower()
    if not lowered.strip():
        return "en"

    # Lightweight heuristic for UI labels and language hinting only.
    if any(char in lowered for char in ["ae", "oe", "ue", "ss"]):
        if any(token in lowered for token in ["und", "oder", "nicht", "frage", "thema"]):
            return "de"

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


def process_uploaded_file(uploaded_file) -> Tuple[str, Optional[Image.Image], List[str]]:
    warnings: List[str] = []
    file_bytes = uploaded_file.getvalue()

    if uploaded_file.type == "application/pdf":
        text = extract_text_from_pdf_bytes(file_bytes)
        if text:
            return text, None, warnings
        try:
            images = convert_from_bytes(file_bytes, first_page=1, last_page=1)
            if images:
                warnings.append("No OCR text found in PDF. Using first page as image input.")
                return "", images[0], warnings
        except Exception as exc:
            warnings.append(f"PDF to image conversion failed: {exc}")
        return "", None, warnings

    if uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()
        return text, None, warnings

    if uploaded_file.type.startswith("image/"):
        image = Image.open(io.BytesIO(file_bytes))
        return "", image, warnings

    warnings.append("Unsupported file type. Upload PDF, DOCX, JPG, JPEG, or PNG.")
    return "", None, warnings


def fetch_remote_text(path_name: str) -> Optional[str]:
    candidates = [path_name]
    if path_name == "step_dragthewords.txt":
        candidates.append("step_dragthewords.txt.txt")

    with httpx.Client(timeout=20.0) as client:
        for candidate in candidates:
            url = f"{RAW_BASE_URL}/{candidate}"
            try:
                response = client.get(url)
                if response.status_code == 200 and response.text.strip():
                    return response.text.strip()
            except Exception:
                continue
    return None


def load_instruction_file(filename: str) -> Tuple[Optional[str], str]:
    local_candidates = [
        LOCAL_V2_DIR / filename,
        REPO_ROOT / filename,
    ]

    for local_path in local_candidates:
        content = read_text_file(local_path)
        if content:
            return content, f"local:{local_path}"

    remote_content = fetch_remote_text(filename)
    if remote_content:
        return remote_content, f"remote:{RAW_BASE_URL}/{filename}"

    return None, "missing"


def get_openai_client() -> Optional[OpenAI]:
    try:
        api_key = st.secrets["openai"]["api_key"]
        http_client = httpx.Client(timeout=60.0)
        return OpenAI(api_key=api_key, http_client=http_client)
    except Exception as exc:
        st.error(f"OpenAI client initialization failed: {exc}")
        return None


def build_instruction_payload(step_key: str) -> Tuple[str, List[str], List[str]]:
    sources: List[str] = []
    missing: List[str] = []

    prompt_v2 = read_text_file(REPO_ROOT / "prompt_v2.md")
    readme_v2 = read_text_file(LOCAL_V2_DIR / "README.txt")

    if prompt_v2:
        sources.append("local:prompt_v2.md")
    else:
        missing.append("prompt_v2.md")

    if readme_v2:
        sources.append("local:v2_files/README.txt")
    else:
        missing.append("v2_files/README.txt")

    selected_files = STEP_FILES[step_key]
    step_blocks: List[str] = []

    for filename in selected_files:
        content, source = load_instruction_file(filename)
        if content:
            sources.append(source)
            step_blocks.append(f"FILE {filename}\n{content}")
        else:
            missing.append(filename)

    parts = []
    if prompt_v2:
        parts.append(f"GLOBAL PROMPT V2\n{prompt_v2}")
    if readme_v2:
        parts.append(f"GLOBAL README V2\n{readme_v2}")
    parts.extend(step_blocks)

    return "\n\n".join(parts), sources, missing


def call_model(
    client: OpenAI,
    instruction_payload: str,
    user_input: str,
    language_hint: str,
    step_key: str,
    image: Optional[Image.Image],
) -> str:
    system_prompt = (
        "You are an educational content generator for OpenOLAT imports. "
        "Follow the provided instruction files exactly. "
        "If instructions conflict, prioritize selected step files, then v2 README, then prompt_v2. "
        "Respect required output format and separators. "
        "Output in the same language as the user input unless a step explicitly says otherwise. "
        "This is a single-turn execution inside an app UI, not a conversational workflow. "
        "Do not ask follow-up questions. "
        "The user has already provided input and selected the step."
    )

    user_prompt = (
        f"Selected step: {step_key}\n"
        f"Language hint: {language_hint}\n\n"
        "EXECUTION MODE\n"
        "- Execute immediately.\n"
        "- Never ask the user to provide text/topic or to choose a step.\n"
        "- Treat USER CONTENT as valid input even if short.\n"
        "- If USER CONTENT is only a topic, generate based on that topic.\n\n"
        "INSTRUCTIONS START\n"
        f"{instruction_payload}\n"
        "INSTRUCTIONS END\n\n"
        "USER CONTENT START\n"
        f"{user_input.strip()}\n"
        "USER CONTENT END"
    )

    if image is not None:
        image_data = encode_image_for_openai(image)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "low",
                        },
                    },
                ],
            },
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.4,
        max_completion_tokens=8000,
    )
    return (response.choices[0].message.content or "").strip()


def is_follow_up_request(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        "please provide",
        "provide a text",
        "provide text",
        "specific topic",
        "which step",
        "select a step",
        "paste a text",
        "enter a text",
    ]
    return any(pattern in lowered for pattern in patterns)


def normalize_output_for_codebox(output: str) -> str:
    text = output.strip()
    if not text:
        return ""

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return text


def main() -> None:
    st.title("OLAT Workflow V2")
    st.caption(
        "Step-based generator using prompt_v2 and v2_files instructions. "
        "Upload text material or provide a topic, then choose workflow A-H."
    )

    uploaded_file = st.file_uploader(
        "Upload a PDF, DOCX, or image (optional)",
        type=["pdf", "docx", "jpg", "jpeg", "png"],
    )

    extracted_text = ""
    uploaded_image: Optional[Image.Image] = None

    if uploaded_file is not None:
        extracted_text, uploaded_image, warnings = process_uploaded_file(uploaded_file)
        for warning in warnings:
            st.warning(warning)
        if extracted_text:
            st.success("Text extracted from uploaded file.")
        if uploaded_image is not None:
            st.image(uploaded_image, caption="Uploaded image", use_container_width=True)

    default_text = extracted_text if extracted_text else ""
    user_input = st.text_area(
        "Paste your source text or enter a topic",
        value=default_text,
        height=240,
    )

    detected_lang = detect_language(user_input)
    localized_labels = STEP_LABELS.get(detected_lang, STEP_LABELS["en"])

    st.markdown(f"Detected input language: `{LANG_HINT.get(detected_lang, 'English')}`")
    selected_step = st.radio(
        "Choose the workflow step",
        options=list(STEP_FILES.keys()),
        format_func=lambda key: localized_labels.get(key, key),
        horizontal=False,
    )

    if st.button("Generate", type="primary"):
        if not user_input.strip() and uploaded_image is None:
            st.warning("Please provide text/topic or upload an image.")
            st.stop()

        client = get_openai_client()
        if client is None:
            st.stop()

        instruction_payload, sources, missing = build_instruction_payload(selected_step)
        if not instruction_payload.strip():
            st.error("No instructions could be loaded for the selected step.")
            st.stop()

        with st.spinner("Generating content..."):
            try:
                raw_output = call_model(
                    client=client,
                    instruction_payload=instruction_payload,
                    user_input=user_input,
                    language_hint=LANG_HINT.get(detected_lang, "English"),
                    step_key=selected_step,
                    image=uploaded_image,
                )
                if is_follow_up_request(raw_output):
                    retry_input = (
                        user_input.strip()
                        + "\n\nIMPORTANT\n"
                        "Generate now from the provided topic/text. "
                        "Do not ask for additional input."
                    )
                    raw_output = call_model(
                        client=client,
                        instruction_payload=instruction_payload,
                        user_input=retry_input,
                        language_hint=LANG_HINT.get(detected_lang, "English"),
                        step_key=selected_step,
                        image=uploaded_image,
                    )
            except Exception as exc:
                st.error(f"Generation failed: {exc}")
                logging.exception("Generation failure")
                st.stop()

        cleaned_output = normalize_output_for_codebox(raw_output)
        st.subheader("Generated Output")
        st.code(cleaned_output if cleaned_output else raw_output, language="text")

        st.download_button(
            label="Download output",
            data=(cleaned_output if cleaned_output else raw_output),
            file_name=f"olat_v2_step_{selected_step}.txt",
            mime="text/plain",
        )

        with st.expander("Instruction sources"):
            for source in sources:
                st.write(f"- {source}")
            if missing:
                st.write("Missing files:")
                for name in missing:
                    st.write(f"- {name}")


if __name__ == "__main__":
    main()
