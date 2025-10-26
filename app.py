import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

import streamlit as st
import yaml
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_NAME = "Aura UX — UX-Risk-Guardian"
st.set_page_config(page_title=APP_NAME, layout="wide")

# ---------------------- Styles ----------------------
st.markdown(
    """
    <style>
    .main { background-color: #ffffff; }
    .risk-badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .low { background: #e8f5e9; color: #1b5e20; }
    .moderate { background: #fff8e1; color: #e65100; }
    .high { background: #ffebee; color: #b71c1c; }
    .veryhigh { background: #fbe9e7; color: #bf360c; border: 1px solid #bf360c33; }
    .pill { border-radius: 999px; padding: 2px 8px; background: #f1f3f5; font-size: 12px; margin-right: 6px; }
    .section-title { font-weight: 700; font-size: 16px; margin-top: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(APP_NAME)

with st.sidebar:
    st.markdown("### Settings")
    model_name = st.selectbox("OpenAI model", ["gpt-4o"], index=0)
    show_other_frameworks = st.toggle("Show GDPR / NIST AI RMF / OECD mapping", value=False)
    st.markdown("---")
    st.markdown("**Disclaimer:** This tool is not legal advice.")
    st.markdown("**Scope Note:** Focused on UX + AI ethics. Off-topic queries may be flagged.")

# ---------------------- Paths & KB ----------------------
BASE_DIR = Path(__file__).parent.resolve()
RISKS_PATH = str(BASE_DIR / "data" / "risks.yaml")
REFS_PATH = str(BASE_DIR / "data" / "references.yaml")
TELEM_PATH = str(BASE_DIR / "telemetry.csv")

def load_kb(risks_path: str, refs_path: str):
    with open(risks_path, "r", encoding="utf-8") as f:
        risks = yaml.safe_load(f)
    with open(refs_path, "r", encoding="utf-8") as f:
        refs = yaml.safe_load(f)
    return risks, refs

def build_reference_dict(refs_yaml) -> dict:
    d = {}
    for r in refs_yaml:
        d[r["id"]] = r
    return d

def render_numeric_citations(ref_ids: List[str], ref_dict: Dict[str, dict], start_index: int = 1):
    lines = []
    seen_numbers = []
    i = start_index
    for rid in ref_ids[:5]:
        ref = ref_dict.get(rid)
        if not ref:
            continue
        doi_part = f"https://doi.org/{ref['doi']}" if ref.get("doi") else ref.get("url", "")
        authors = ref.get("authors", "").replace("&", "and")
        year = ref.get("year", "?")
        title = ref.get("title", "")
        venue = ref.get("venue", "")
        lines.append(f"[{i}] {authors} ({year}). <i>{title}</i>. {venue}. <br/><a href=\"{doi_part}\" target=\"_blank\">{doi_part}</a>")
        seen_numbers.append(i)
        i += 1
    html = "<br/>".join(lines) if lines else "No references."
    return html, seen_numbers

def _match_score(q: str, text: str) -> int:
    q = q.lower()
    text = text.lower()
    score = 0
    for token in [t for t in q.replace("-", " ").split() if t]:
        if token in text:
            score += 1
    return score

def retrieve_by_query(query: str, risks: List[Dict[str, Any]], ref_dict: Dict[str, Any], max_items: int = 5):
    phase_map = {
        "phase:understand": "Understand",
        "phase:specify": "Specify",
        "phase:create": "Create",
        "phase:evaluate": "Evaluate",
    }
    for key, phase in phase_map.items():
        if key in query.lower():
            filtered = [r for r in risks if r.get("phase") == phase]
            return filtered[:max_items]

    scored = []
    for r in risks:
        blob = " ".join([
            r.get("title", ""),
            r.get("justification", ""),
            " ".join(r.get("evidence", [])),
            " ".join(r.get("mitigations", [])),
        ])
        scored.append((_match_score(query, blob), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [r for s, r in scored if s > 0][:max_items]
    if not out:
        out = risks[:max_items]
    return out

def phase_presets(phase_query: str, risks: List[Dict[str, Any]], ref_dict: Dict[str, Any], max_items: int = 5):
    return retrieve_by_query(phase_query, risks, ref_dict, max_items=max_items)

def map_to_eu_ai_act(query: str):
    q = query.lower()
    if any(x in q for x in ["biometric", "surveillance", "social scoring"]):
        return ("Prohibited / High-Risk", "Biometric identification/surveillance features can fall under high-risk or prohibited categories under the EU AI Act.")
    if any(x in q for x in ["recruit", "hiring", "credit", "loan", "education", "health"]):
        return ("High-Risk", "Impacts access to essential services or fundamental rights; stricter obligations apply (risk mgmt, data quality, human oversight).")
    if any(x in q for x in ["chatbot", "content generation", "assistive", "ux writing", "summarize", "persona"]):
        return ("Limited-Risk", "Likely transparency obligations (disclose AI use), log events, provide oversight mechanisms.")
    return ("Minimal-Risk", "General-purpose UX support with low rights impact; follow good practices and basic transparency.")

def map_to_other_frameworks(query: str) -> str:
    return (
        "GDPR: assess lawful basis, purpose limitation, data minimization. "
        "NIST AI RMF: Govern → Map → Measure → Manage; document risks and controls. "
        "OECD AI: Inclusive growth, human-centered values, transparency, robustness, accountability."
    )

def export_result_to_pdf(query: str, act_tag: str, act_note: str, blocks: List[Dict[str, Any]], ref_dict: Dict[str, Any]):
    path = str(BASE_DIR / f"aura_ux_export.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def write_wrapped(text, x, y, max_width):
        lines = simpleSplit(text, 'Helvetica', 10, max_width)
        for line in lines:
            c.drawString(x, y, line)
            y -= 12
        return y

    margin = 2*cm
    x = margin
    y = height - margin

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Aura UX — UX-Risk-Guardian")
    y -= 16
    c.setFont("Helvetica", 10)
    y = write_wrapped(f"Query: {query}", x, y, width - 2*margin)
    y = write_wrapped(f"EU AI Act: {act_tag} — {act_note}", x, y, width - 2*margin)
    y -= 8

    for block in blocks:
        r = block["risk"]
        c.setFont("Helvetica-Bold", 11)
        y = write_wrapped(f"Risk: {r['title']} (Priority: {r['severity']}; Phase: {r['phase']})", x, y, width - 2*margin)
        c.setFont("Helvetica", 10)
        y = write_wrapped(f"Justification: {r.get('justification','')}", x, y, width - 2*margin)
        y = write_wrapped("Mitigations:", x, y, width - 2*margin)
        for m in r.get("mitigations", [])[:5]:
            y = write_wrapped(f" - {m}", x+12, y, width - 2*margin - 12)
        y = write_wrapped("Evidence:", x, y, width - 2*margin)
        for e in r.get("evidence", [])[:5]:
            y = write_wrapped(f" - {e}", x+12, y, width - 2*margin - 12)
        ref_ids = r.get("references", [])[:5]
        if ref_ids:
            y = write_wrapped("References:", x, y, width - 2*margin)
            idx = 1
            for rid in ref_ids:
                ref = ref_dict.get(rid)
                if not ref:
                    continue
                line = f"[{idx}] {ref.get('authors','')} ({ref.get('year','')}). {ref.get('title','')} — {ref.get('venue','')} — DOI: {ref.get('doi','')}"
                y = write_wrapped(line, x+12, y, width - 2*margin - 12)
                idx += 1
        y -= 8
        if y < 3*cm:
            c.showPage()
            y = height - margin

    c.save()
    return path

def log_query(q: str):
    try:
        ts = datetime.utcnow().isoformat()
        header = not os.path.exists(TELEM_PATH)
        with open(TELEM_PATH, "a", encoding="utf-8") as f:
            if header:
                f.write("timestamp,query\n")
            q_clean = q.replace("\n", " ").replace(",", ";")
            f.write(f"{ts},{q_clean}\n")
    except Exception:
        pass

# ---------------------- Load KB ----------------------
kb_risks, kb_refs = load_kb(RISKS_PATH, REFS_PATH)
ref_dict = build_reference_dict(kb_refs)

# ---------------------- UI ----------------------
col_q, col_export = st.columns([4,1])
with col_q:
    query = st.text_input("Search what you are doing or want to do (e.g., 'compile interview results with AI')", "")
with col_export:
    st.write("")
    st.write("")
    export_clicked = st.button("Export PDF")

if query.strip():
    log_query(query)
    off_scope = any(token in query.lower() for token in ["medical", "diagnosis", "trading", "finance advice", "tax"])
    if off_scope:
        st.warning("This app focuses on UX + AI ethics. Your query seems out of scope.")

    results = retrieve_by_query(query, kb_risks, ref_dict, max_items=5)
    act_tag, act_note = map_to_eu_ai_act(query)
    st.markdown(f"**EU AI Act**: `{act_tag}` — {act_note}")
    if show_other_frameworks:
        st.caption(map_to_other_frameworks(query))

    numeric_refs_seen = []
    rendered_blocks = []
    for r in results:
        sev = r.get("severity", "Moderate").lower().replace(" ", "")
        badge_class = {"low":"low","moderate":"moderate","high":"high","veryhigh":"veryhigh"}.get(sev, "moderate")
        with st.expander(f"{r['title']}"):
            st.markdown(f"<span class='risk-badge {badge_class}'>Priority: {r['severity']}</span> <span class='pill'>Phase: {r['phase']}</span>", unsafe_allow_html=True)
            st.markdown(r.get("justification", ""))
            st.markdown("<div class='section-title'>Mitigations (HCL)</div>", unsafe_allow_html=True)
            for m in r.get("mitigations", [])[:5]:
                st.markdown(f"- {m}")
            st.markdown("<div class='section-title'>Evidence Summary</div>", unsafe_allow_html=True)
            st.markdown("- " + "\n- ".join(r.get("evidence", [])[:5]))
            refs_section, seen = render_numeric_citations(r.get("references", [])[:5], ref_dict, start_index=len(numeric_refs_seen) + 1)
            numeric_refs_seen.extend(seen)
            st.markdown("<div class='section-title'>References</div>", unsafe_allow_html=True)
            st.markdown(refs_section, unsafe_allow_html=True)
            if r.get("ai_act_note"):
                st.caption(f"EU AI Act note: {r['ai_act_note']}")
            rendered_blocks.append({"risk": r, "refs": seen})

    if export_clicked:
        pdf_path = export_result_to_pdf(query, act_tag, act_note, rendered_blocks, ref_dict)
        if pdf_path:
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, file_name=os.path.basename(pdf_path), mime="application/pdf")

else:
    st.info("Tip: Click a UCD phase to explore typical AI risks & mitigations.")
    pcol1, pcol2, pcol3, pcol4 = st.columns(4)
    if pcol1.button("Understand"):
        query = "phase:understand"
    if pcol2.button("Specify"):
        query = "phase:specify"
    if pcol3.button("Create"):
        query = "phase:create"
    if pcol4.button("Evaluate"):
        query = "phase:evaluate"

    if query:
        preset_results = phase_presets(query, kb_risks, ref_dict, max_items=5)
        act_tag, act_note = map_to_eu_ai_act(query)
        st.markdown(f"**EU AI Act**: `{act_tag}` — {act_note}")
        if show_other_frameworks:
            st.caption(map_to_other_frameworks(query))

        numeric_refs_seen = []
        rendered_blocks = []
        for r in preset_results:
            sev = r.get("severity", "Moderate").lower().replace(" ", "")
            badge_class = {"low":"low","moderate":"moderate","high":"high","veryhigh":"veryhigh"}.get(sev, "moderate")
            with st.expander(f"{r['title']}"):
                st.markdown(f"<span class='risk-badge {badge_class}'>Priority: {r['severity']}</span> <span class='pill'>Phase: {r['phase']}</span>", unsafe_allow_html=True)
                st.markdown(r.get("justification", ""))
                st.markdown("<div class='section-title'>Mitigations (HCL)</div>", unsafe_allow_html=True)
                for m in r.get("mitigations", [])[:5]:
                    st.markdown(f"- {m}")
                st.markdown("<div class='section-title'>Evidence Summary</div>", unsafe_allow_html=True)
                st.markdown("- " + "\n- ".join(r.get("evidence", [])[:5]))
                refs_section, seen = render_numeric_citations(r.get("references", [])[:5], ref_dict, start_index=len(numeric_refs_seen) + 1)
                numeric_refs_seen.extend(seen)
                st.markdown("<div class='section-title'>References</div>", unsafe_allow_html=True)
                st.markdown(refs_section, unsafe_allow_html=True)
                if r.get("ai_act_note"):
                    st.caption(f"EU AI Act note: {r['ai_act_note']}")
                rendered_blocks.append({"risk": r, "refs": seen})

        if st.button("Export PDF"):
            pdf_path = export_result_to_pdf(query, act_tag, act_note, rendered_blocks, ref_dict)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, file_name=os.path.basename(pdf_path), mime="application/pdf")
