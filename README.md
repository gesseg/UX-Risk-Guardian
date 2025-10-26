# Aura UX — UX-Risk-Guardian

*A white-label Streamlit app that helps UX professionals quickly see AI-related risks, scientific citations, EU AI Act relevance, and short Human-in-the-Center-of-the-Loop (HCL) mitigations. Answers are concise, objective, and sourced from a curated knowledge base.*

## ✨ Features
- **Curated-only mode**: results come from a bundled knowledge base (no live web browsing).
- **Simple output**: up to **3–5 risks**, **3–5 mitigations**, **3–5 references**.
- **Risk priority**: "Low / Moderate / High / Very High" with a **business justification**.
- **EU AI Act layer**: short tag + explanation; toggle to also map to **GDPR**, **NIST AI RMF**, **OECD**.
- **UCD shortcuts**: phase buttons — **Understand → Specify → Create → Evaluate** — open fixed risk+mitigation sets.
- **Nexus-like expanders**: click items to expand details.
- **PDF export** of the current result.
- **Anonymous telemetry** (local CSV) for query + timestamp.

## 🚀 Quickstart (Streamlit Community Cloud or local)

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
streamlit run app.py
```
