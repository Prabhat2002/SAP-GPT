import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
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

prompt = ChatPromptTemplate.from_template("""
You are SAP-GPT, an expert enterprise SAP assistant.

IMPORTANT RULE — Platform Boundary:
You MUST answer ONLY within the context of the selected platform below.
If the question is about a different SAP module or platform, politely decline
and tell the user to switch to the correct platform.

Selected Platform: {platform}

Question / Error:
{error}

If the question is within scope of {platform}, provide:
1. Root Cause
2. SAP Technical Explanation
3. Step-by-Step Fix
4. Relevant SAP Transactions / Tcodes
5. Relevant SAP Tables
6. Best Practices
7. Severity (LOW / MEDIUM / HIGH / CRITICAL)
8. Prevention Tips
9. Additional Notes

If the question is NOT within the scope of {platform}:
- Say: "⚠️ This question appears to be about [correct platform], not {platform}."
- Tell the user to select the correct platform from the dropdown.
- Do NOT answer the question.
""")


def analyze_error(platform: str, error_text: str, use_feedback: bool = True) -> str:

    # Client-side pre-check for obvious mismatches
    mismatch = detect_platform_mismatch(platform, error_text)

    if mismatch:
        return (
            f"## ⚠️ Platform Mismatch Detected\n\n"
            f"Your question appears to be about **{mismatch}**, "
            f"not **{platform}**.\n\n"
            f"**Please switch the platform dropdown to: `{mismatch}`** and ask again.\n\n"
            f"---\n"
            f"_SAP-GPT enforces platform boundaries to give you accurate, "
            f"context-specific answers._"
        )

    # Build few-shot examples from user feedback (self-training)
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
        chain = prompt | llm

        response = chain.invoke({
            "platform": platform,
            "error": few_shot_block + error_text
        })

        return response.content

    except Exception as e:
        return f"❌ ERROR: {str(e)}"
