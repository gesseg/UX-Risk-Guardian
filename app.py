# app.py — Aura UX — UX-Risk-Guardian (versão estável final)
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st
import yaml
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit

# ===== OpenAI opcional (usado só para condensar texto; app funciona sem) =====
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
OPENAI_MODEL = "gpt-4o"

APP_NAME = "Aura UX — UX-Risk-Guardian"
st.set_page_config(page_title=APP_NAME, layout="wide")

# ===== Fallback embutido como OBJETO PYTHON (sem YAML em string) =====
EMBEDDED_REFERENCES = [
    {
        "id": "ruckenstein2022",
        "authors": "Ruckenstein, M.; Granroth, J.",
        "year": 2022,
        "title": "Definition drives design — Disability models and mechanisms of bias in AI technologies",
        "venue": "arXiv preprint",
        "doi": "10.48550/arXiv.2206.08287",
        "url": "https://arxiv.org/abs/2206.08287",
    },
    {
        "id": "mosqueira2023",
        "authors": "Mosqueira-Rey, E.; et al.",
        "year": 2023,
        "title": "Human-in-the-loop Machine Learning — A State of the Art",
        "venue": "Artificial Intelligence Review (Springer)",
        "doi": "10.1007/s10462-022-10246-w",
        "url": "https://link.springer.com/article/10.1007/s10462-022-10246-w",
    },
    {
        "id": "mehrabi2022",
        "authors": "Mehrabi, N.; et al.",
        "year": 2022,
        "title": "A survey on bias and fairness in machine learning",
        "venue": "ACM Computing Surveys",
        "doi": "10.1145/3457607",
        "url": "https://dl.acm.org/doi/10.1145/3457607",
    },
    {
        "id": "zoller2024",
        "authors": "Zöller, C.; et al.",
        "year": 2024,
        "title": "The impact of AI errors in a human-in-the-loop process",
        "venue": "PLOS ONE (PMC)",
        "doi": "10.1371/journal.pone.0296535",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10772030/",
    },
    {
        "id": "kim2023",
        "authors": "Kim, J.; et al.",
        "year": 2023,
        "title": "Designerly Understanding: Information Needs for Model Transparency to Support Design Ideation for AI-Powered UX",
        "venue": "arXiv preprint",
        "doi": "10.48550/arXiv.2302.10395",
        "url": "https://arxiv.org/abs/2302.10395",
    },
]

EMBEDDED_RISKS = [
    {
        "id": "risk_desumanizacao",
        "phase": "Understand",
        "title": "Dehumanization through context-insensitive automation",
        "severity": "High",
        "justification": "Generic models can ignore cultural/accessibility context, excluding users and harming adoption.",
        "evidence": [
            "Automation can overlook disability models and context.",
            "Cultural misalignment degrades trust and fairness perception.",
        ],
        "references": ["ruckenstein2022"],
        "mitigations": [
            "Include lived-experience users and accessibility experts in reviews.",
            "Add inclusive personas and scenario walkthroughs to decision logs.",
            "Require context notes in prompts and model cards.",
        ],
        "ai_act_note": "Potential Limited/High risk depending on domain; ensure transparency and accessibility compliance.",
    },
    {
        "id": "risk_intencionalidade",
        "phase": "Specify",
        "title": "Loss of design intentionality and purpose drift",
        "severity": "Moderate",
        "justification": "Delegating key choices to AI can detach outcomes from strategy, reducing differentiation and value.",
        "evidence": ["Practitioners report agency/purpose dilution with automation."],
        "references": ["mosqueira2023"],
        "mitigations": [
            "Human gates for vision, outcomes, success criteria.",
            "Design rationale log linked to AI-assisted artifacts.",
            "Human approval for changes to goals/metrics.",
        ],
        "ai_act_note": "Transparency and human oversight duties recommended.",
    },
    {
        "id": "risk_bias",
        "phase": "Understand",
        "title": "Algorithmic bias and unfair outcomes",
        "severity": "Very High",
        "justification": "Discriminatory outcomes cause legal/reputation risk and exclusion; remediation is costly.",
        "evidence": [
            "Bias emerges from data and reinforces discrimination at scale.",
        ],
        "references": ["mehrabi2022"],
        "mitigations": [
            "Fairness checks on representative samples before release.",
            "Human override/appeal channel for affected users.",
            "Track disparity metrics by key segments.",
        ],
        "ai_act_note": "High-risk in sensitive domains; rigorous risk management required.",
    },
    {
        "id": "risk_automation_bias",
        "phase": "Create",
        "title": "Automation bias (over-reliance on AI suggestions)",
        "severity": "High",
        "justification": "Designers may accept wrong AI suggestions, leading to usability defects and misaligned features.",
        "evidence": ["Human accuracy drops when exposed to erroneous AI outputs."],
        "references": ["zoller2024"],
        "mitigations": [
            "Show confidence/uncertainty cues.",
            "Force exploration of ≥2 alternatives before selection.",
            "Error review rituals with human-first judgment.",
        ],
        "ai_act_note": "Transparency/logging obligations; promote human oversight.",
    },
    {
        "id": "risk_transparencia",
        "phase": "Evaluate",
        "title": "Lack of traceability and transparency",
        "severity": "Moderate",
        "justification": "Without audit trails/rationale, decisions are indefensible; compliance and trust decline.",
        "evidence": [
            "Designers need model transparency artifacts to decide.",
        ],
        "references": ["kim2023"],
        "mitigations": [
            "Model/prompt cards linked to artifacts.",
            "Log AI-assisted changes with who/why.",
            "End-user disclosures where applicable.",
        ],
        "ai_act_note": "Limited-risk transparency duties likely apply.",
    },
]

# ====== Caminhos e utilitários ======
BASE_DIR = Path(__file__).parent.resolve()
def resolve_path(filename: str) -> Path:
    p_root = BASE_DIR / filename
    p_data = BASE_DIR / "data" / filename
    return p_root if p_root.exists() else p_data

RISKS_PATH = resolve_path("risks.yaml")
REFS_PATH  = resolve_path("references.yaml")
TELEM_PATH = BASE_DIR / "telemetry.csv"

def load_kb(risks_path: Path, refs_path: Path):
    """Lê YAML externo se existir; senão usa EMBEDDED_* (listas Python)."""
    try:
        if risks_path.exists() and refs_path.exists():
            with open(risks_path, "r", encoding="utf-8") as f:
                risks = yaml.safe_load(f)
            with open(refs_path, "r", encoding="utf-8") as f:
                refs = yaml.safe_load(f)
            return risks, refs
        else:
            st.caption("Using embedded curated base (data files not found).")
            return EMBEDDED_RISKS, EMBEDDED_REFERENCES
    except Exception:
        st.caption("Using embedded curated base (fallback).")
        return EMBEDDED_RISKS, EMBEDDED_REFERENCES

def build_reference_dict(refs_yaml) -> dict:
    return {r["id"]: r for r in refs_yaml}

def render_numeric_citations(ref_ids: List[str], ref_dict: Dict[str, dict], start_index: int = 1):
    lines, seen_numbers, i = [], [], start_index
    for rid in ref_ids[:5]:
        ref = ref_dict.get(rid)
        if not ref:
            continue
        doi_part = f"https://doi.org/{ref['doi']}" if ref.get("doi") else ref.get("url", "")
        authors = ref.get("authors", "").replace("&", "and")
        year = ref.get("year", "?")
        title = ref.get("title", "")
        venue = ref.get("venue", "")
        lines.append(
            f"[{i}] {authors} ({year}). <i>{title}</i>. {venue}. "
            f"<br/><a href=\"{doi_part}\" target=\"_blank\">{doi_part}</a>"
        )
        seen_numbers.append(i)
        i += 1
    html = "<br/>".join(lines) if lines else "No references."
    return html, seen_numbers

def _match_score(q: str, text: str) -> int:
    q = q.lower(); text = text.lower()
    return sum(1 for t in q.replace("-", " ").split() if t and t in text)

def retrieve_by_query(query: str, risks: List[Dict[str, Any]], ref_dict: Dict[str, Any], max_items: int = 5):
    phase_map = {
        "phase:understand": "Understand",
        "phase:specify": "Specify",
        "phase:create": "Create",
        "phase:evaluate": "Evaluate",
    }
    for key, phase in phase_map.items():
        if key in query.lower():
            return [r for r in risks if r.get("phase") == phase][:max_items]
    scored = []
    for r in risks:
        blob = " ".join([
            r.get("title",""),
            r.get("justification",""),
            " ".join(r.get("evidence",[])),
            " ".join(r.get("mitigations",[])),
        ])
        scored.append((_match_score(query, blob), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [r for s, r in scored if s > 0][:max_items]
    return out or risks[:max_items]

def phase_presets(phase_query: str, risks: List[Dict[str, Any]], ref_dict: Dict[str, Any], max_items: int = 5):
    return retrieve_by_query(phase_query, risks, ref_dict, max_items=max_items)

def map_to_eu_ai_act(query: str):
    q = query.lower()
    if any(x in q for x in ["biometric", "surveillance", "social scoring"]):
        return ("Prohibited / High-Risk",
                "Biometric identification/surveillance features can fall under high-risk or prohibited categories under the EU AI Act.")
    if any(x in q for x in ["recruit", "hiring", "credit", "loan", "education", "health"]):
        return ("High-Risk",
                "Impacts access to essential services or fundamental rights; stricter obligations apply (risk mgmt, data quality, human oversight).")
    if any(x in q for x in ["chatbot", "content generation", "assistive", "ux writing", "summarize", "persona"]):
        return ("Limited-Risk",
                "Likely transparency obligations (disclose AI use), log events, provide oversight mechanisms.")
    return ("Minimal-Risk",
            "General-purpose UX support with low rights impact; follow good practices and basic transparency.")

def map_to_other_frameworks(query: str) -> str:
    return ("GDPR: assess lawful basis, purpose limitation, data minimization. "
            "NIST AI RMF: Govern → Map → Measure → Manage; document risks and controls. "
            "OECD AI: Inclusive growth, human-centered values, transparency, robustness, accountability.")

# ===== PDF export, logging e UI =====
def export_result_to_pdf(query: str, act_tag: str, act_note: str,
                         blocks: List[Dict[str, Any]], ref_dict: Dict[str, Any]):
    path = str(BASE_DIR / "aura_ux_export.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def write_wrapped(text, x, y, max_width):
        lines = simpleSplit(text, 'Helvetica', 10, max_width)
        for line in lines:
            c.drawString(x, y, line); y -= 12
        return y

    margin = 2*cm; x = margin; y = height - margin
    c.setFont("Helvetica-Bold", 12); c.drawString(x, y, APP_NAME); y -= 16
    c.setFont("Helvetica", 10)
    y = write_wrapped(f"Query: {query}", x, y, width - 2*margin)
    y = write_wrapped(f"EU AI Act: {act_tag} — {act_note}", x, y, width - 2*margin)
    y -= 8

    for block in blocks:
        r = block["risk"]
        c.setFont("Helvetica-Bold", 11)
        y = write_wrapped(f"Risk: {r['title']} (Priority: {r['severity']}; Phase: {r['phase']})",
                          x, y, width - 2*margin)
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
                if ref:
                    line = (f"[{idx}] {ref.get('authors','')} ({ref.get('year','')}). "
                            f"{ref.get('title','')} — {ref.get('venue','')} — DOI: {ref.get('doi','')}")
                    y = write_wrapped(line, x+12, y, width - 2*margin - 12)
                    idx += 1
        y -= 8
        if y < 3*cm:
            c.showPage(); y = height - margin

    c.save()
    return path

def log_query(q: str):
    try:
        ts = datetime.utcnow().isoformat()
        header = not TELEM_PATH.exists()
        with open(TELEM_PATH, "a", encoding="utf-8") as f:
            if header:
                f.write("timestamp,query\n")
            f.write(f"{ts},{q.replace(',', ';').replace('\n',' ')}\n")
    except Exception:
        pass

# ===== UI =====
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
    show_other_frameworks = st.toggle("Show GDPR / NIST AI RMF / OECD mapping", value=False)
    st.markdown("---")
    st.markdown("**Disclaimer:** This tool is not legal advice.")
    st.markdown("**Scope Note:** Focused on UX + AI ethics.")

# ==== Carrega base ====
kb_risks, kb_refs = load_kb(RISKS_PATH, REFS_PATH)
ref_dict = build_reference_dict(kb_refs)

col_q, col_export = st.columns([4,1])
with col_q:
    query = st.text_input("Search what you are doing or want to do (e.g., 'compile interview results with AI')", "")
with col_export:
    st.write("")
    st.write("")
    export_clicked = st.button("Export PDF", key="export_top")

def render_results(results: List[Dict[str, Any]], query_text: str):
    act_tag, act_note = map_to_eu_ai_act(query_text)
    st.markdown(f"**EU AI Act**: `{act_tag}` — {act_note}")
    if show_other_frameworks:
        st.caption(map_to_other_frameworks(query_text))
    numeric_refs_seen, rendered_blocks = [], []
    for r in results:
        sev = r.get("severity", "Moderate").lower().replace(" ", "")
        badge_class = {"low":"low","moderate":"moderate","high":"high","veryhigh":"veryhigh"}.get(sev, "moderate")
        with st.expander(f"{r['title']}"):
            st.markdown(
                f"<span class='risk-badge {badge_class}'>Priority: {r['severity']}</span> "
                f"<span class='pill'>Phase: {r['phase']}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(r.get("justification", ""))
            st.markdown("<div class='section-title'>Mitigations (HCL)</div>", unsafe_allow_html=True)
            for m in r.get("mitigations", [])[:5]:
                st.markdown(f"- {m}")
            st.markdown("<div class='section-title'>Evidence Summary</div>", unsafe_allow_html=True)
            st.markdown("- " + "\n- ".join(r.get("evidence", [])[:5]))
            refs_section, seen = render_numeric_citations(
                r.get("references", [])[:5], ref_dict, start_index=len(numeric_refs_seen)+1
            )
            numeric_refs_seen.extend(seen)
            st.markdown("<div class='section-title'>References</div>", unsafe_allow_html=True)
            st.markdown(refs_section, unsafe_allow_html=True)
            if r.get("ai_act_note"):
                st.caption(f"EU AI Act note: {r['ai_act_note']}")
            rendered_blocks.append({"risk": r, "refs": seen})
    return act_tag, act_note, rendered_blocks

if query.strip():
    log_query(query)
    if any(t in query.lower() for t in ["medical", "diagnosis", "trading", "finance advice", "tax"]):
        st.warning("This app focuses on UX + AI ethics. Your query seems out of scope.")
    results = retrieve_by_query(query, kb_risks, ref_dict, max_items=5)
    act_tag, act_note, rendered_blocks = render_results(results, query)
    if export_clicked:
        pdf_path = export_result_to_pdf(query, act_tag, act_note, rendered_blocks, ref_dict)
        if pdf_path:
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, file_name=Path(pdf_path).name,
                                   mime="application/pdf", key="download_query")
else:
    st.info("Tip: Click a UCD phase to explore typical AI risks & mitigations.")
    pcol1, pcol2, pcol3, pcol4 = st.columns(4)
    phase_query = ""
    if pcol1.button("Understand"):
        phase_query = "phase:understand"
    if pcol2.button("Specify"):
        phase_query = "phase:specify"
    if pcol3.button("Create"):
        phase_query = "phase:create"
    if pcol4.button("Evaluate"):
        phase_query = "phase:evaluate"
    if phase_query:
        results = phase_presets(phase_query, kb_risks, ref_dict, max_items=5)
        act_tag, act_note, rendered_blocks = render_results(results, phase_query)
        if st.button("Export PDF", key="export_phase"):
            pdf_path = export_result_to_pdf(phase_query, act_tag, act_note, rendered_blocks, ref_dict)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f, file_name=Path(pdf_path).name,
                                       mime="application/pdf", key="download_phase")

