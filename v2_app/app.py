import base64
import io
import json
import logging
import os
import re
import time
from datetime import date
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
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)

for env_var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(env_var, None)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_V2_DIR = REPO_ROOT / "v2_files"
RAW_BASE_URL = "https://raw.githubusercontent.com/aburossi/prompts/main/olatimport"
MODEL_CANDIDATES = ["gpt-4o", "gpt-5-mini"]
MAX_IMAGE_ATTACHMENTS = 12

ACCEPTED_FILE_TYPES = ["pdf", "docx", "jpg", "jpeg", "png", "txt", "md", "json", "csv", "html", "htm", "xml"]

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

STEP_ICONS = {"A": "🔒", "B": "✏️", "C": "🔀", "D": "🎯", "E": "📝", "H": "🎓"}
STEP_DESCRIPTIONS = {
    "en": {
        "A": "Multiple choice, single choice, KPRIM & true/false",
        "B": "Fill-in-the-blank & essay prompts",
        "C": "Combination of closed and open question types",
        "D": "Drag-the-word inline choice exercises",
        "E": "Fill-in-the-blank cloze texts",
        "H": "Full course: all question types combined",
    },
    "de": {
        "A": "Multiple Choice, Single Choice, KPRIM & Wahr/Falsch",
        "B": "Lückentexte und Aufsatzfragen",
        "C": "Kombination geschlossener und offener Fragetypen",
        "D": "Drag-the-Word Inline-Choice Übungen",
        "E": "Lückentexte (Cloze)",
        "H": "Vollständiger Kurs: alle Fragetypen kombiniert",
    },
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
        "E": "E) Lückentexte",
        "H": "H) Vollständiger Kursablauf",
    },
}

LANG_HINT = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "es": "Spanish",
}

LANG_NAMES = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "es": "Español",
}

FILE_TYPE_ICONS = {
    "pdf_text": ("📄", "PDF (text)"),
    "pdf_image": ("🖼️", "PDF (scanned)"),
    "docx": ("📝", "Word document"),
    "image": ("🖼️", "Image"),
    "text": ("📋", "Text file"),
    "json": ("🔧", "JSON"),
    "csv": ("📊", "CSV"),
    "html": ("🌐", "HTML"),
    "xml": ("🌐", "XML"),
    "unknown": ("❓", "Unknown"),
}

UI_STRINGS = {
    "en": {
        "title": "OLAT Workflow V2",
        "caption": "Backend-controlled multi-step workflow with JSON parsing",
        "upload_label": "Upload materials",
        "preview_label": "📄 Extracted Content Preview",
        "words": "words",
        "chars": "chars",
        "input_label": "Input Text or Topic",
        "step_select": "Select Question Type",
        "num_questions": "Number of questions per step",
        "generate": "Generate",
        "generating": "Generating…",
        "please_provide": "Please provide some input text or upload a file.",
        "step_progress": "Step {current}/{total} – {filename}",
        "complete": "✅ Generation complete!",
        "output_title": "Generated OLAT Content",
        "copy_btn": "📋 Copy to Clipboard",
        "copied": "✅ Copied!",
        "download_btn": "⬇️ Download .txt",
        "regenerate": "🔄 Regenerate",
        "regenerating": "Regenerating…",
        "missing_instructions": "Missing instructions for: {file}",
        "api_key_missing_title": "🔑 API Key not configured",
        "api_key_missing_body": (
            "Add your OpenAI API key to `.streamlit/secrets.toml`:\n\n"
            "```toml\n[openai]\napi_key = \"sk-...\"\n```"
        ),
        "lang_override": "Language override",
        "lang_auto": "Auto-detect",
        "uploaded_files_header": "📎 Uploaded Files",
        "elapsed": "{s:.1f}s",
    },
    "de": {
        "title": "OLAT Workflow V2",
        "caption": "Backend-gesteuerter Mehrstufiger Workflow mit JSON-Parsing",
        "upload_label": "Materialien hochladen",
        "preview_label": "📄 Extrahierter Inhalt (Vorschau)",
        "words": "Wörter",
        "chars": "Zeichen",
        "input_label": "Eingabetext oder Thema",
        "step_select": "Fragetyp auswählen",
        "num_questions": "Anzahl Fragen pro Schritt",
        "generate": "Generieren",
        "generating": "Generiere…",
        "please_provide": "Bitte geben Sie einen Text ein oder laden Sie eine Datei hoch.",
        "step_progress": "Schritt {current}/{total} – {filename}",
        "complete": "✅ Generierung abgeschlossen!",
        "output_title": "Generierter OLAT-Inhalt",
        "copy_btn": "📋 In Zwischenablage kopieren",
        "copied": "✅ Kopiert!",
        "download_btn": "⬇️ Herunterladen (.txt)",
        "regenerate": "🔄 Neu generieren",
        "regenerating": "Generiere neu…",
        "missing_instructions": "Fehlende Anleitung für: {file}",
        "api_key_missing_title": "🔑 API-Schlüssel nicht konfiguriert",
        "api_key_missing_body": (
            "Fügen Sie Ihren OpenAI API-Schlüssel in `.streamlit/secrets.toml` ein:\n\n"
            "```toml\n[openai]\napi_key = \"sk-...\"\n```"
        ),
        "lang_override": "Sprache überschreiben",
        "lang_auto": "Automatisch erkennen",
        "uploaded_files_header": "📎 Hochgeladene Dateien",
        "elapsed": "{s:.1f}s",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Parsing & file helpers
# ──────────────────────────────────────────────────────────────────────────────

def parse_json_to_olat(json_str: str) -> str:
    """Converts the generated JSON format to the OLAT import text format."""
    try:
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
                    "Text\t✏",
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
        return json_str


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


def process_uploaded_file(uploaded_file) -> Tuple[str, List[Image.Image], List[str], str]:
    """Returns (text, images, warnings, file_type_key)."""
    warnings: List[str] = []
    file_bytes = uploaded_file.getvalue()
    file_name = getattr(uploaded_file, "name", "uploaded_file")
    mime = uploaded_file.type or ""

    if mime == "application/pdf":
        text = extract_text_from_pdf_bytes(file_bytes)
        if text:
            return f"[Source: {file_name}]\n{text}", [], warnings, "pdf_text"
        try:
            images = convert_from_bytes(file_bytes)
            if images:
                warnings.append(f"No OCR text found in {file_name}. Using PDF pages as images.")
                return "", images, warnings, "pdf_image"
        except Exception as exc:
            warnings.append(f"PDF conversion failed: {exc}")
        return "", [], warnings, "pdf_image"

    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs).strip()
        labeled = f"[Source: {file_name}]\n{text}" if text else ""
        return labeled, [], warnings, "docx"

    if mime.startswith("image/"):
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        return "", [image], warnings, "image"

    # Plain text-based formats: txt, md, json, csv, html, xml, etc.
    ext = Path(file_name).suffix.lower().lstrip(".")
    text_extensions = {"txt", "md", "json", "csv", "html", "htm", "xml", "yaml", "yml", "toml", "rst"}
    if ext in text_extensions or mime.startswith("text/"):
        try:
            text = file_bytes.decode("utf-8", errors="replace").strip()
            labeled = f"[Source: {file_name}]\n{text}"
            type_key = ext if ext in {"json", "csv", "html", "htm", "xml"} else "text"
            if type_key == "htm":
                type_key = "html"
            return labeled, [], warnings, type_key
        except Exception as exc:
            warnings.append(f"Could not read {file_name} as text: {exc}")

    return "", [], ["Unsupported file type."], "unknown"


def process_uploaded_files(uploaded_files) -> Tuple[str, List[Image.Image], List[str], List[Dict]]:
    """Returns (text, images, warnings, file_meta_list)."""
    text_chunks, images, warnings, file_meta = [], [], [], []
    for f in uploaded_files:
        t, i, w, type_key = process_uploaded_file(f)
        if t:
            text_chunks.append(t)
        if i:
            images.extend(i)
        if w:
            warnings.extend(w)
        file_meta.append({"name": f.name, "type_key": type_key, "has_text": bool(t), "has_images": bool(i)})
    return "\n\n".join(text_chunks).strip(), images, warnings, file_meta


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
    if content:
        return content, f"local:{filename}"
    remote = fetch_remote_text(filename)
    if remote:
        return remote, f"remote:{filename}"
    return None, "missing"


def get_openai_client() -> Optional[OpenAI]:
    try:
        api_key = st.secrets["openai"]["api_key"]
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def call_model(
    client: OpenAI,
    instruction_payload: str,
    user_input: str,
    language_hint: str,
    step_filename: str,
    images: List[Image.Image],
    num_questions: int,
) -> str:
    # Inject num_questions placeholder into the instruction (e.g. kprim.txt)
    instruction_payload = instruction_payload.replace("{num_questions}", str(num_questions))

    # NOTE: Do NOT put a hard question-count mandate in the system prompt.
    # step_closed_questions uses Bloom-level structure (4 levels = 4 Qs) and a
    # contradicting "exactly N" at system level causes model refusals.
    # The count is passed as a soft hint in the user message instead.
    system_prompt = (
        "You are an educational content generator for OpenOLAT imports. "
        "Strictly follow the provided JSON schema and Bloom-level instructions. "
        "Output ONLY the JSON in a markdown code box. "
        "Do not ask questions, add explanations, or apologise."
    )

    content_items = [
        {
            "type": "text",
            "text": (
                f"Instruction File: {step_filename}\n"
                f"Language: {language_hint}\n"
                f"Target number of questions (adjust per Bloom-level rules): {num_questions}\n\n"
                f"Content:\n{user_input}\n\n{instruction_payload}"
            ),
        }
    ]
    for img in images[:MAX_IMAGE_ATTACHMENTS]:
        content_items.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image_for_openai(img)}", "detail": "low"}}
        )

    for model in MODEL_CANDIDATES:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_items},
                ],
                temperature=0.3,
                max_completion_tokens=4000,
            )
            return resp.choices[0].message.content or ""
        except Exception:
            continue
    return "Error: All model attempts failed."


REFUSAL_MARKERS = ("i'm sorry", "i cannot", "i can't", "i am unable", "unable to help", "can't help", "cannot help", "as an ai")

def is_model_refusal(text: str) -> bool:
    lowered = text.lower().strip()
    return any(m in lowered for m in REFUSAL_MARKERS) and not lowered.startswith("{") and "```" not in lowered


def run_step(client, step_file, user_input, lang, num_questions, images) -> Tuple[str, Optional[str]]:
    """Returns (olat_text, error_message). error_message is None on success."""
    content, _ = load_instruction_file(step_file)
    if not content:
        return "", f"Missing instruction file: {step_file}"
    raw_json = call_model(client, content, user_input, LANG_HINT.get(lang, "English"), step_file, images, num_questions)
    if not raw_json or raw_json.startswith("Error:"):
        return "", raw_json or "Model returned empty response."
    if is_model_refusal(raw_json):
        return "", f"Model refused to generate content for **{step_file}**. Try a different input or check the image content."
    return parse_json_to_olat(raw_json), None



def make_download_filename(selected_step: str, lang: str) -> str:
    labels = STEP_LABELS.get(lang, STEP_LABELS["en"])
    label = labels.get(selected_step, selected_step)
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    today = date.today().isoformat()
    return f"olat_{slug}_{today}.txt"


def clipboard_button(text: str, button_label: str, copied_label: str, key: str):
    """Renders a clipboard copy button using a JS component (works on streamlit.app)."""
    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    html = f"""
    <textarea id="clip_{key}" style="position:absolute;left:-9999px;">{escaped}</textarea>
    <button id="btn_{key}"
        style="background:#0D6EFD;color:white;border:none;border-radius:6px;
               padding:8px 16px;font-size:14px;cursor:pointer;font-family:inherit;"
        onclick="(function(){{
            var el = document.getElementById('clip_{key}');
            el.select(); el.setSelectionRange(0, 99999);
            document.execCommand('copy');
            var btn = document.getElementById('btn_{key}');
            btn.innerText = '{copied_label}';
            btn.style.background='#198754';
            setTimeout(function(){{btn.innerText='{button_label}';btn.style.background='#0D6EFD';}}, 2000);
        }})()">
        {button_label}
    </button>
    """
    st.components.v1.html(html, height=48)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    # ── Session state defaults ────────────────────────────────────────────────
    if "selected_step" not in st.session_state:
        st.session_state["selected_step"] = "A"
    if "step_outputs" not in st.session_state:
        st.session_state["step_outputs"] = {}
    if "lang_override" not in st.session_state:
        st.session_state["lang_override"] = None
    if "last_input_hash" not in st.session_state:
        st.session_state["last_input_hash"] = None

    # ── Sidebar: API key check ─────────────────────────────────────────────────
    client = get_openai_client()
    if not client:
        st.sidebar.error("🔑 API Key not configured")
        st.sidebar.markdown(
            "> Add your OpenAI API key to `.streamlit/secrets.toml`:\n"
            "> ```toml\n> [openai]\n> api_key = \"sk-...\"\n> ```"
        )

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("🎓 OLAT Workflow V2")
    st.caption("Backend-controlled multi-step workflow with JSON parsing.")

    # ── File uploader ─────────────────────────────────────────────────────────
    uploaded_files = st.file_uploader(
        "Upload materials",
        type=ACCEPTED_FILE_TYPES,
        accept_multiple_files=True,
        help=f"Supported: {', '.join(f'.{t}' for t in ACCEPTED_FILE_TYPES)}",
    )

    extracted_text, images, warnings, file_meta = (
        process_uploaded_files(uploaded_files) if uploaded_files else ("", [], [], [])
    )

    for w in warnings:
        st.warning(w)

    # ── File chips ────────────────────────────────────────────────────────────
    if file_meta:
        st.markdown("**📎 Uploaded Files**")
        chip_cols = st.columns(min(len(file_meta), 4))
        for idx, meta in enumerate(file_meta):
            icon, label = FILE_TYPE_ICONS.get(meta["type_key"], FILE_TYPE_ICONS["unknown"])
            mode = "text" if meta["has_text"] else ("images" if meta["has_images"] else "—")
            with chip_cols[idx % 4]:
                st.info(f"{icon} **{meta['name']}**\n\n{label} · parsed as: *{mode}*")

    # ── Text area ─────────────────────────────────────────────────────────────
    user_input = st.text_area("Input Text or Topic", value=extracted_text, height=200)

    # ── Language: detect once, allow override ─────────────────────────────────
    input_hash = hash(user_input[:500])
    if st.session_state["last_input_hash"] != input_hash or st.session_state["lang_override"] is None:
        detected_lang = detect_language(user_input)
        st.session_state["last_input_hash"] = input_hash
        if st.session_state["lang_override"] is None:
            st.session_state["detected_lang"] = detected_lang

    effective_lang = st.session_state.get("lang_override") or st.session_state.get("detected_lang", "en")
    labels = STEP_LABELS.get(effective_lang, STEP_LABELS["en"])
    descriptions = STEP_DESCRIPTIONS.get(effective_lang, STEP_DESCRIPTIONS["en"])

    # ── Extracted content preview ─────────────────────────────────────────────
    if user_input.strip():
        word_count = len(user_input.split())
        char_count = len(user_input)
        with st.expander(f"📄 Extracted Content Preview — {word_count:,} words / {char_count:,} chars"):
            st.text(user_input[:500] + ("…" if len(user_input) > 500 else ""))

    st.divider()

    # ── Step selector cards ────────────────────────────────────────────────────
    st.markdown("**Select Question Type**")
    step_keys = list(STEP_FILES.keys())
    card_cols = st.columns(len(step_keys))
    for col, key in zip(card_cols, step_keys):
        with col:
            is_selected = st.session_state["selected_step"] == key
            border_style = "border: 2px solid #0D6EFD;" if is_selected else ""
            label = labels.get(key, key)
            short_label = label.split(")")[0] + ")"  # "A)"
            icon = STEP_ICONS.get(key, "📌")
            desc = descriptions.get(key, "")
            bg = "#EFF6FF" if is_selected else ""
            st.markdown(
                f"""<div style="border-radius:10px;padding:12px;text-align:center;
                    {border_style}background:{bg};min-height:110px;">
                  <div style="font-size:1.6rem;">{icon}</div>
                  <div style="font-weight:700;font-size:1rem;">{short_label}</div>
                  <div style="font-size:0.75rem;color:#555;margin-top:4px;">{desc}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(f"Select {short_label}", key=f"step_btn_{key}", use_container_width=True):
                st.session_state["selected_step"] = key
                st.rerun()

    selected_step = st.session_state["selected_step"]
    st.caption(f"Selected: **{labels.get(selected_step, selected_step)}**")

    st.divider()

    # ── Sidebar: number of questions + language override ──────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Generation Settings")
        num_questions = st.slider("Number of questions per step", min_value=3, max_value=20, value=6, step=1)

        st.markdown("---")
        st.markdown("### 🌍 Language")
        lang_options = {"Auto-detect": None, **{v: k for k, v in LANG_NAMES.items()}}
        current_override = st.session_state.get("lang_override")
        current_name = next((v for k, v in LANG_NAMES.items() if k == current_override), "Auto-detect")
        override_selection = st.selectbox(
            "Language override",
            options=list(lang_options.keys()),
            index=list(lang_options.keys()).index(current_name),
        )
        st.session_state["lang_override"] = lang_options[override_selection]

        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.caption(f"Effective language: **{LANG_NAMES.get(effective_lang, effective_lang)}**")
        step_count = len(STEP_FILES.get(selected_step, []))
        st.caption(f"Steps in workflow: **{step_count}** API call(s)")

    # ── Generate button ───────────────────────────────────────────────────────
    if st.button("🚀 Generate", type="primary", use_container_width=True):
        if not user_input.strip() and not images:
            st.warning("Please provide input text or upload a file.")
            st.stop()
        if not client:
            st.error("Cannot generate: API key is not configured.")
            st.stop()

        steps = STEP_FILES[selected_step]
        st.session_state["step_outputs"] = {}

        with st.status("Executing Workflow…", expanded=True) as status:
            progress = st.progress(0.0)
            total = len(steps)
            for idx, step_file in enumerate(steps):
                t0 = time.time()
                status.write(f"⏳ Step {idx + 1}/{total} — {step_file}")
                result, err = run_step(client, step_file, user_input, effective_lang, num_questions, images)
                elapsed = time.time() - t0
                if result:
                    st.session_state["step_outputs"][step_file] = result
                    status.write(f"✅ {step_file} done in {elapsed:.1f}s")
                elif err:
                    status.write(f"❌ {step_file} failed ({elapsed:.1f}s): {err}")
                    st.session_state["step_errors"] = st.session_state.get("step_errors", {})
                    st.session_state["step_errors"][step_file] = err
                progress.progress((idx + 1) / total)
            status.update(label="✅ Generation complete!", state="complete")

    # ── Output section ────────────────────────────────────────────────────────
    if st.session_state["step_outputs"]:
        st.divider()
        st.subheader("Generated OLAT Content")

        combined_text = "\n\n".join(st.session_state["step_outputs"].values())

        # Copy + Download row
        col_copy, col_dl = st.columns([1, 1])
        with col_copy:
            clipboard_button(
                combined_text,
                "📋 Copy All to Clipboard",
                "✅ Copied!",
                key="main_copy",
            )
        with col_dl:
            filename = make_download_filename(selected_step, effective_lang)
            st.download_button(
                "⬇️ Download .txt",
                combined_text,
                file_name=filename,
                mime="text/plain",
                use_container_width=True,
            )

        st.caption(f"Download filename: `{filename}`")

        # Per-step output blocks
        for step_file, output in st.session_state["step_outputs"].items():
            with st.expander(f"📄 {step_file}", expanded=True):
                st.code(output, language="text")

                regen_col, _ = st.columns([1, 3])
                with regen_col:
                    if st.button(f"🔄 Regenerate", key=f"regen_{step_file}"):
                        if not client:
                            st.error("API key not configured.")
                        else:
                            with st.spinner(f"Regenerating {step_file}…"):
                                new_output, regen_err = run_step(
                                    client, step_file, user_input, effective_lang, num_questions, images
                                )
                            if new_output:
                                st.session_state["step_outputs"][step_file] = new_output
                                st.rerun()
                            elif regen_err:
                                st.error(regen_err)

        # Full combined view
        with st.expander("📋 Combined output (all steps)", expanded=False):
            st.code(combined_text, language="text")


if __name__ == "__main__":
    main()
