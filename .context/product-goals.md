# Product Goals & Mission

## Primary Objective
To provide Swiss educators with an automated pipeline that transforms textbook content or topics into pedagogical assessment materials (Questions, Blanks, Inline Choices) compatible with the OpenOLAT LMS.

## Core User Stories
- **As a Teacher**, I want to upload a PDF chapter so that I can instantly generate Bloom-aligned multiple-choice questions.
- **As a Course Designer**, I want to generate a "Full Course Workflow" (Step H) to get a variety of content types in one click.
- **As an Administrator**, I want the output in a specific Tab-separated format so I can import it into OLAT without manual editing.

## Success Criteria
- Validated JSON-to-OLAT text conversion.
- Successful extraction of text from various file formats (PDF, DOCX, Images).
- Adherence to Bloom's Taxonomy levels in all generated questions.

## Out of Scope
- Direct API integration into the OLAT database (Import is manual via .txt).
- User authentication/database persistence (Stateless Streamlit app).