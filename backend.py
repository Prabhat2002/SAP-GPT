import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Works locally (.env) AND on Streamlit Cloud (secrets.toml)
def _get_groq_key():
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            pass
    return key

llm = ChatGroq(
    groq_api_key=_get_groq_key(),
    model_name="llama-3.3-70b-versatile"
)

# =====================================================
# PLATFORM → ALLOWED KEYWORDS
# If the question contains keywords from a DIFFERENT
# platform, we refuse and tell the user which platform
# they should switch to.
# =====================================================

PLATFORM_KEYWORDS = {
    "SAP ABAP On-Premise": [
        "abap", "report", "class", "function module", "bapi", "badi",
        "enhancement", "se38", "se24", "st22", "sm21", "sm50", "sm66",
        "itab", "internal table", "select", "open sql", "native sql",
        "dynpro", "screen", "module pool", "alv", "smartform", "adobe form",
        "idoc", "rfc", "sap gui", "workbench", "transport", "se10",
        "short dump", "cx_", "raise exception", "field symbol"
    ],
    "SAP BTP (Business Technology Platform)": [
        "btp", "cloud foundry", "kyma", "subaccount", "entitlement",
        "service binding", "destination", "connectivity", "xsuaa",
        "approuter", "mta", "cf push", "hana cloud", "launchpad service",
        "business application studio", "bas", "sap build"
    ],
    "SAP CAPM (Cloud Application Programming Model)": [
        "capm", "cds", "cap", "node.js", "java cap", "@cds", "srv",
        "schema.cds", "entity", "service", "annotations", "fiori elements",
        "odata v4", "cap project", "cds compile", "mta.yaml", "xs-security",
        "@sap/cds", "db/schema", "cap local", "sqlite cap"
    ],
    "SAP Fiori / UI5": [
        "fiori", "ui5", "sapui5", "openui5", "view.xml", "controller.js",
        "manifest.json", "odata", "component.js", "fragment", "smart table",
        "smart form", "freestyle", "fiori elements", "flp", "launchpad",
        "tile", "i18n", "binding", "model", "router", "navigation"
    ],
    "SAP HANA": [
        "hana", "hdb", "column store", "row store", "calculation view",
        "analytic view", "attribute view", "hana studio", "hana cloud",
        "sql script", "procedure", "xsjs", "xsodata", "in-memory",
        "hana db", "hana schema", "text analysis", "predictive"
    ],
    "SAP Basis": [
        "basis", "transport", "stms", "system copy", "kernel", "patch",
        "support package", "spam", "saint", "solman", "solution manager",
        "sap router", "sap service marketplace", "snc", "ssl",
        "client", "system refresh", "homogeneous", "heterogeneous",
        "buffer", "icm", "work process", "dialog", "background", "spool",
        "enqueue", "message server", "dispatcher", "sm59"
    ],
    "SAP Functional (MM / SD / FI / HR)": [
        "mm", "sd", "fi", "hr", "hcm", "material management", "sales",
        "procurement", "purchase order", "sales order", "invoice",
        "vendor", "customer", "gl account", "cost center", "profit center",
        "payroll", "personnel", "pa40", "me21n", "me31k", "va01", "vf01",
        "fb50", "migo", "miro", "configuration", "customizing"
    ],
    "SAP Integration Suite (CPI)": [
        "cpi", "integration suite", "iflow", "integration flow",
        "groovy", "message mapping", "adapter", "idoc", "as2", "sftp",
        "rest adapter", "soap adapter", "integration content",
        "message processing log", "mpl", "integration center",
        "api management", "open connectors", "event mesh"
    ],
    "SAP S/4HANA": [
        "s4hana", "s/4", "s4", "embedded analytics", "fiori apps",
        "universal journal", "acdoca", "simplified data model",
        "migration cockpit", "activate", "best practice", "greenfield",
        "brownfield", "selective data transition", "rise with sap"
    ],
    "SAP RAP (RESTful ABAP Programming)": [
        "rap", "restful", "behavior definition", "behavior implementation",
        "managed", "unmanaged", "draft", "cds view entity",
        "bdef", "bimpl", "early numbering", "late numbering",
        "action", "determination", "validation", "feature control",
        "odata v4", "abap restful"
    ],
}

# Map keywords → their home platform (for redirect hint)
KEYWORD_TO_PLATFORM: dict[str, str] = {}
for plat, kws in PLATFORM_KEYWORDS.items():
    for kw in kws:
        KEYWORD_TO_PLATFORM[kw] = plat


def detect_platform_mismatch(selected_platform: str, question: str) -> str | None:
    """
    Returns a suggested platform name if the question clearly belongs
    to a DIFFERENT platform than what was selected, else None.
    """
    q_lower = question.lower()
    votes: dict[str, int] = {}

    for kw, plat in KEYWORD_TO_PLATFORM.items():
        if plat == selected_platform:
            continue
        if kw in q_lower:
            votes[plat] = votes.get(plat, 0) + 1

    # Also count how many keywords match the selected platform
    selected_score = sum(
        1 for kw in PLATFORM_KEYWORDS.get(selected_platform, [])
        if kw in q_lower
    )

    if not votes:
        return None

    best_other, best_score = max(votes.items(), key=lambda x: x[1])

    # Only flag mismatch if the other platform scores higher than selected
    if best_score > selected_score and best_score >= 2:
        return best_other

    return None


# =====================================================
# PLATFORM-AWARE PROMPT
# =====================================================


# =====================================================
# CHATBOT PROMPT — Platform specific OR Other (any SAP)
# =====================================================
chatbot_prompt = ChatPromptTemplate.from_template("""
You are SAP-GPT, an expert enterprise SAP assistant.

Selected Platform: {platform}

{platform_instruction}

Question / Error:
{error}

Provide a thorough answer with:
1. Root Cause / Understanding(if Applicable)
2. SAP Technical Explanation
3. Step-by-Step Fix / Solution
4. Relevant SAP Transactions / T-codes (if applicable)
5. Relevant SAP Tables (if applicable)
6. Best Practices
7. Severity: LOW / MEDIUM / HIGH / CRITICAL
8. Prevention Tips
9. Additional Notes(if Applicable)
""")

# =====================================================
# DOCUMENT ANALYZER PROMPT
# =====================================================
doc_prompt = ChatPromptTemplate.from_template("""
You are SAP-GPT, an expert SAP document analyst.

Document Type Selected: {doc_type}

First, determine if this document is SAP-related.
SAP-related means: it involves SAP systems, modules, configurations, ABAP, BTP, HANA, Fiori, CPI, RAP, CAPM, Basis, Functional (MM/SD/FI/HR), or any SAP technology.

Document Content:
{content}

RULES:
- If the document is NOT SAP-related at all: respond ONLY with:
  "❌ This document does not appear to be SAP-related. SAP-GPT can only analyze SAP documents. Please upload a document related to SAP systems, modules, or technologies."

- If the document IS SAP-related (any SAP topic — ABAP, RAP, BTP, Fiori, HANA, Functional, Basis, CPI, CAPM, etc.):
  Provide a full analysis:
  1. Executive Summary
  2. SAP Module / Technology Identified
  3. Key Technical Points
  4. Risks & Gaps Identified
  5. Recommendations
  6. Action Items
  7. Overall Assessment

Always answer based on document content — do NOT ask user to change dropdown.
""")


def analyze_error(platform: str, error_text: str, use_feedback: bool = True) -> str:
    """Used by Tab 1 Chatbot."""

    OTHER_PLATFORMS = ["Other / Not Sure", "SAP Document Analysis"]

    # For Other — answer any SAP question, no mismatch check
    if platform in OTHER_PLATFORMS:
        platform_instruction = (
            "The user has selected 'Other / Not Sure'. "
            "Answer ANY SAP-related question across ALL SAP domains: "
            "ABAP, BTP, CAPM, Fiori/UI5, HANA, Basis, Functional (MM/SD/FI/HR), "
            "CPI, S/4HANA, RAP, and any other SAP technology. "
            "If the question is completely unrelated to SAP, politely say so."
        )
    else:
        # Specific platform — check mismatch
        mismatch = detect_platform_mismatch(platform, error_text)
        if mismatch:
            return (
                f"## ⚠️ Platform Mismatch Detected\n\n"
                f"Your question appears to be about **{mismatch}**, "
                f"not **{platform}**.\n\n"
                f"**Please switch the platform dropdown to: `{mismatch}`** and ask again.\n\n"
                f"---\n"
                f"_If you're not sure about the platform, select **Other / Not Sure** "
                f"and SAP-GPT will answer across all SAP domains._"
            )
        platform_instruction = (
            f"Answer ONLY within the context of {platform}. "
            f"If the question is clearly about a different SAP platform, "
            f"tell the user to switch platform or use 'Other / Not Sure'."
        )

    # Few-shot from feedback
    few_shot_block = ""
    if use_feedback:
        try:
            from database import fetch_feedback_examples
            examples = fetch_feedback_examples(platform, rating="useful", limit=3)
            if examples:
                few_shot_block = "\n\n--- EXAMPLES FROM HIGHLY-RATED PAST ANSWERS ---\n"
                for i, (ex_q, ex_a) in enumerate(examples, 1):
                    few_shot_block += f"\nExample {i}:\nQ: {ex_q[:300]}\nA: {ex_a[:500]}\n"
                few_shot_block += "--- END EXAMPLES ---\n"
        except Exception:
            pass

    try:
        chain = chatbot_prompt | llm
        response = chain.invoke({
            "platform": platform,
            "platform_instruction": platform_instruction,
            "error": few_shot_block + error_text
        })
        return response.content
    except Exception as e:
        return f"❌ ERROR: {str(e)}"


def analyze_document(doc_type: str, content: str) -> str:
    """Used by Tab 2 Document Analyzer."""
    try:
        chain = doc_prompt | llm
        response = chain.invoke({
            "doc_type": doc_type,
            "content": content[:10000]
        })
        return response.content
    except Exception as e:
        return f"❌ ERROR: {str(e)}"