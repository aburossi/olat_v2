# OLAT Workflow V2

This sub-app provides a second Streamlit workflow based on `prompt_v2.md` and `v2_files/*.txt`.

## Run locally

From repository root:

```powershell
streamlit run v2_app/app.py
```

## Deploy on Streamlit Cloud

Set the app entrypoint to:

- `v2_app/app.py`

The app uses the same root-level dependencies (`requirements.txt` and `packages.txt`) and the same secret:

- `st.secrets["openai"]["api_key"]`

## Workflow

User provides source text/topic (optionally uploads PDF, DOCX, or image), then selects step `A` to `H`.

The app loads instructions from local `v2_files` first and falls back to:

- `https://raw.githubusercontent.com/aburossi/prompts/main/olatimport/<file>`

for files that are not present locally.
