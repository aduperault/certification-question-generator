import pdfplumber
import trafilatura
import io
import json
import streamlit as st
from anthropic import Anthropic

client = Anthropic()

def extract_text_from_pdf(file_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages).strip()

def extract_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace").strip()

def extract_text_from_url(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded)
    return text.strip() if text else ""

def preview(text: str) -> str:
    words = len(text.split())
    chars = len(text)
    print(f"--- Extracted {words} words / {chars} characters ---")
    print(text[:500])
    print("...")

def build_prompt(doc_text: str) -> str:
    return f"""You are an expert certification exam developer with deep experience writing psychometrically sound multiple choice questions.

DOCUMENT TEXT:
\"\"\"
{doc_text[:12000]}
\"\"\"

Generate between 3 and 5 certification exam questions based strictly on the document text above.
Choose the question type (single answer or multiple answer) based on what the content best supports.

Return ONLY a single valid JSON object with this exact structure:

{{
  "title": "A concise descriptive title for the source document",
  "questions": [
{{
      "type": "single",
      "question": "Full question text. Select one answer.",
      "choices": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": ["A"],
      "rationale": "One sentence explaining why this answer is correct."
    }},
    {{
      "type": "multiple",
      "question": "Full question text. Select 3 answer choices.",
      "choices": ["A. ...", "B. ...", "C. ...", "D. ...", "E. ..."],
      "answer": ["A", "B", "C"],
      "rationale": "One sentence explaining why these answers are correct."
    }}
  ]
}}

CERTIFICATION QUESTION RULES — follow every rule for every question:

LANGUAGE & STYLE:
- Do not use contractions (write "do not" not "don't")
- Do not use negatives in the question stem or answer choices (no "EXCEPT", "NOT", "never")
- Do not use abbreviations without spelling them out in full first on first use (example: "Family Educational Rights and Privacy Act (FERPA)")
- Do not use jargon or slang
- Questions must be succinct — 1 to 3 sentences maximum

SCENARIO-BASED QUESTIONS:
- Do not use people's names — refer to the role instead (write "The system administrator" not "Sally")
- Do not use gender or pronouns — refer to the role (write "the administrator needs" not "she needs")

ANSWER CHOICE CONSTRUCTION:
- Single answer questions: exactly 1 correct answer and exactly 3 distractors (4 choices total) — end with "Select one answer."
- Multiple answer questions: exactly 3 correct answers and exactly 2 distractors (5 choices total) — end with "Select 3 answer choices."
- The correct answer must be 100% correct and verifiable from the source document
- Distractors must be 100% incorrect but factually plausible — no fictional product names
- All answer choices must be similar in length to each other

Return ONLY the JSON object — no markdown, no commentary, no code fences.
"""

def call_claude(prompt: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cert Question Generator",
    page_icon="📋",
    layout="centered"
)
# ── Load CSS ──────────────────────────────────────────────────────────────────
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="aa-eyebrow">AnneAble Consulting</div>', unsafe_allow_html=True)
st.title("Certification Question Generator")
st.markdown('<div class="aa-subtitle">Upload a document, paste a URL, or enter text — and generate certification-ready exam questions in seconds.</div>', unsafe_allow_html=True)

st.divider()

# ── Input tabs ────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📄 Upload File", "🔗 Enter URL", "✍️ Paste Text"])

doc_text = ""
r = None

with tab1:
    uploaded_file = st.file_uploader(
        "Upload a PDF or plain text file",
        type=["pdf", "txt"]
    )
    if uploaded_file:
        file_bytes = uploaded_file.read()
        if uploaded_file.name.endswith(".pdf"):
            doc_text = extract_text_from_pdf(file_bytes)
        else:
            doc_text = extract_text_from_txt(file_bytes)

with tab2:
    url_input = st.text_input("Paste a URL")
    st.caption("Works best with publicly accessible static pages. For authenticated content, use the Paste Text tab instead.")
    if url_input:
        with st.spinner("Fetching page content..."):
            doc_text = extract_text_from_url(url_input)

with tab3:
    pasted_text = st.text_area("Paste your text here", height=200)
    if pasted_text:
        doc_text = pasted_text.strip()

# ── Preview ───────────────────────────────────────────────────────────────────
if doc_text:
    words = len(doc_text.split())
    chars = len(doc_text)
    st.success(f"Content ready — {words} words / {chars} characters")

st.divider()

# ── Generate button ───────────────────────────────────────────────────────────
ready = bool(doc_text)
generate_btn = st.button(
    "Generate Certification Questions",
    disabled=not ready,
    use_container_width=True,
    type="primary"
)# ── Generate ──────────────────────────────────────────────────────────────────
if generate_btn and doc_text:
    with st.spinner("Generating certification questions..."):
        try:
            prompt = build_prompt(doc_text)
            result = call_claude(prompt)
            st.session_state["result"] = result
        except Exception as e:
            st.error(f"Something went wrong: {e}")

# ── Results ───────────────────────────────────────────────────────────────────
if "result" in st.session_state:
    r = st.session_state["result"]
    st.subheader(r.get("title", "Generated Questions"))
    st.divider()
    for i, q in enumerate(r.get("questions", []), 1):
        question_type = q.get("type", "single")
        type_label = "Multiple Answer" if question_type == "multiple" else "Single Answer"
        badge_class = "multiple" if question_type == "multiple" else "single"
        st.markdown(
            f'<div class="question-card">'
            f'<div class="type-badge {badge_class}">{type_label}</div>'
            f'<div class="question-text">Q{i}. {q.get("question", "")}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        for choice in q.get("choices", []):
            st.markdown(f'<div class="choice">{choice}</div>', unsafe_allow_html=True)
        with st.expander("Show answer"):
            correct = q.get("answer", [])
            st.markdown(f"**Correct answer:** {', '.join(correct)}")
            st.markdown(f"**Rationale:** {q.get('rationale', '')}")
        st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
    st.download_button(
        label="⬇ Download Questions as JSON",
        data=json.dumps(r, indent=2),
        file_name="certification_questions.json",
        mime="application/json",
        use_container_width=True,
    )