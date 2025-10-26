import os
from datetime import datetime

import streamlit as st

from lib.knowledge import load_kb, retrieve_by_query, phase_presets
from lib.eu_ai_mapper import map_to_eu_ai_act, map_to_other_frameworks
from lib.formatting import render_numeric_citations, build_reference_dict
from lib.pdf_export import export_result_to_pdf

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_NAME = "Aura UX — UX-Risk-Guardian"
st.set_page_config(page_title=APP_NAME, layout="wide")

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

kb_risks, kb_refs = load_kb("data/risks.yaml", "data/references.yaml")
ref_dict = build_reference_dict(kb_refs)

TELEM_PATH = "telemetry.csv"
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

def compose_answer(model: str, prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
    if not api_key or OpenAI is None:
        return prompt
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are Aura UX. Use only curated notes. Short bullets. No extra facts."},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return prompt

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
            ref_ids = r.get("references", [])[:5]
            refs_section, seen = render_numeric_citations(ref_ids, ref_dict, start_index=len(numeric_refs_seen) + 1)
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
                ref_ids = r.get("references", [])[:5]
                refs_section, seen = render_numeric_citations(ref_ids, ref_dict, start_index=len(numeric_refs_seen) + 1)
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
