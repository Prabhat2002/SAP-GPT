import streamlit as st
from auth import register_user, login_user
from backend import analyze_error
from database import *
from report_generator import generate_report

import io
import os
import pandas as pd
import plotly.express as px
import PyPDF2

from reportlab.pdfgen import canvas
from docx import Document

# =====================================================
# TESSERACT CONFIG (cross-platform safe)
# =====================================================

try:
    import pytesseract
    from PIL import Image

    if os.name == "nt":
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    TESSERACT_AVAILABLE = True

except Exception:
    TESSERACT_AVAILABLE = False

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="SAP-GPT",
    page_icon="🤖",
    layout="wide"
)

# =====================================================
# LOAD CSS
# =====================================================
#
# FIX: Original code used open("styles.css") which breaks
# when the app is NOT run from the project folder.
#
# Two safe options:
#
# Option A — embedded (used here, always works):
#   Put the CSS string directly in the file.
#
# Option B — file-relative path (also safe):
#   _here = os.path.dirname(os.path.abspath(__file__))
#   css_path = os.path.join(_here, "style.css")   # note: "style.css" not "styles.css"
#   with open(css_path) as f:
#       CSS = f.read()
#
# Additional bug in original: file is named "style.css" in
# the project but the open() call used "styles.css" — wrong name.
# =====================================================

CSS = """
body { background: #020617; }

.main-title {
    font-size: 4rem;
    text-align: center;
    color: white;
    font-weight: 700;
}

.subtitle {
    text-align: center;
    color: #cbd5e1;
    font-size: 1.2rem;
}

.live-text {
    text-align: center;
    color: #06b6d4;
    font-size: 1rem;
    margin-bottom: 30px;
}

.stButton > button {
    background: linear-gradient(90deg, #7c3aed, #06b6d4);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 20px;
    font-weight: 600;
}
"""

st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

# =====================================================
# INIT DB
# =====================================================

init_db()

# =====================================================
# SESSION STATE
# =====================================================

# SAFE session state init — never overwrites existing values.
# This is the correct pattern for Streamlit to survive widget reruns.
if "logged_in"      not in st.session_state: st.session_state.logged_in      = False
if "user_id"        not in st.session_state: st.session_state.user_id        = None
if "show_register"  not in st.session_state: st.session_state.show_register  = False
if "chat_history"   not in st.session_state: st.session_state.chat_history   = []
if "last_analysis"  not in st.session_state: st.session_state.last_analysis  = None
if "followups"      not in st.session_state: st.session_state.followups      = []
if "feedback_given" not in st.session_state: st.session_state.feedback_given = False
if "similar_matches"  not in st.session_state: st.session_state.similar_matches  = []
if "reg_success"    not in st.session_state: st.session_state.reg_success    = False

# =====================================================
# HERO
# =====================================================

st.markdown("""
<h1 class='main-title'>🤖 SAP-GPT</h1>
<p class='subtitle'>Enterprise AI Assistant for SAP Developers</p>
<p class='live-text'>⚡ We support all your SAP problems — ABAP · BTP · CAPM · Fiori · HANA · Basis ⚡</p>
""", unsafe_allow_html=True)

# =====================================================
# LOGIN / REGISTER
# =====================================================

if not st.session_state.logged_in:

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        if not st.session_state.show_register:

            st.markdown("## 🚀 Welcome Back")

            if st.session_state.get("reg_success"):
                st.success("🎉 Registration Successful! Please log in.")
                st.session_state.reg_success = False

            username = st.text_input("👤 Username")
            password = st.text_input("🔒 Password", type="password")

            if st.button("🚀 Login"):
                user_id = login_user(username, password)

                if user_id:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.success("✅ Login Successful")
                    st.rerun()
                else:
                    st.error("❌ Invalid Credentials")

            st.markdown("---")
            st.markdown("### 🆕 New User?")

            if st.button("✨ Register Here"):
                st.session_state.show_register = True
                st.rerun()

        else:

            st.markdown("## ✨ Create Account")

            new_username = st.text_input("👤 User ID")
            new_password = st.text_input("🔒 New Password", type="password")
            confirm_password = st.text_input("🔒 Confirm Password", type="password")

            # Live feedback
            if confirm_password:
                if new_password != confirm_password:
                    st.error("❌ Passwords do not match")
                else:
                    st.success("✅ Passwords match")

            if st.button("🚀 Register"):
                if not new_username or not new_password:
                    st.error("❌ Please fill all fields")
                elif new_password != confirm_password:
                    st.error("❌ Passwords do not match")
                else:
                    success = register_user(new_username, new_password)
                    if success:
                        st.session_state.show_register = False
                        st.session_state.reg_success = True
                        st.rerun()
                    else:
                        st.error("❌ Username already exists")

            if st.button("⬅ Back To Login"):
                st.session_state.show_register = False
                st.rerun()

# =====================================================
# MAIN APP
# =====================================================

else:

    # =====================================================
    # TOP-RIGHT USER PROFILE PANEL
    # =====================================================

    _username = get_username(st.session_state.user_id)
    _history  = fetch_user_history(st.session_state.user_id)
    _teams    = fetch_user_teams(str(st.session_state.user_id))
    _fb_stats = fetch_user_feedback_stats(st.session_state.user_id)

    # Place profile button flush to the top-right using columns
    _spacer, _profile_col = st.columns([10, 1])
    with _profile_col:
        with st.popover(f"👤 {_username}", use_container_width=False):

            st.markdown(f"## 👤 {_username}")
            st.markdown("---")

            # ---- Stats ----
            st.markdown("### 📊 My Stats")
            _c1, _c2, _c3 = st.columns(3)
            _c1.metric("🔍 Analyses", len(_history))
            _c2.metric("🤝 Teams", len(_teams))
            _c3.metric("👍 Useful Ratings", _fb_stats.get("useful", 0))

            st.markdown("---")

            # ---- Saved History (last 5) ----
            st.markdown("### 🧠 Recent History")
            if _history:
                for _h in _history[:5]:
                    st.markdown(f"- 🖥 **{_h[2]}** — `{str(_h[3])[:40]}...`")
            else:
                st.caption("No saved analyses yet.")

            st.markdown("---")

            # ---- My Teams ----
            st.markdown("### 🤝 My Teams")
            if _teams:
                for _t in _teams:
                    _role = "👑" if str(_t[2]) == str(st.session_state.user_id) else "👤"
                    st.markdown(f"- {_role} **{_t[0]}** `{_t[1]}`")
            else:
                st.caption("No teams yet.")

            st.markdown("---")

            # ---- Trends (mini chart) ----
            st.markdown("### 📈 My Trends")
            if _history:
                import pandas as pd
                _df = pd.DataFrame([{"Platform": r[2], "Severity": r[5]} for r in _history])
                _sev_counts = _df["Severity"].value_counts().reset_index()
                _sev_counts.columns = ["Severity", "Count"]
                st.bar_chart(_sev_counts.set_index("Severity"))
            else:
                st.caption("Analyze some errors to see trends here.")

            st.markdown("---")

            # ---- Join Request Notification ----
            st.markdown("### 🔔 Notifications")
            if st.button("🔄 Check Join Requests", key="profile_check_req"):
                st.session_state["pending_count"] = count_pending_requests(str(st.session_state.user_id))

            _pending = st.session_state.get("pending_count", None)
            if _pending is None:
                st.caption("Click above to check pending requests.")
            elif _pending > 0:
                st.error(f"🔔 {_pending} pending join request{'s' if _pending > 1 else ''}! → Join Team tab")
            else:
                st.success("🟢 No pending requests")

            st.markdown("---")

            # ---- Logout ----
            if st.button("🔓 Logout", key="profile_logout", type="primary"):
                for _k in list(st.session_state.keys()):
                    del st.session_state[_k]
                st.rerun()

    # Slim sidebar — only keep notifications & manual refresh
    st.sidebar.markdown("### 🔔 Join Requests")
    if st.sidebar.button("🔄 Check Requests"):
        st.session_state["pending_count"] = count_pending_requests(str(st.session_state.user_id))

    _pending = st.session_state.get("pending_count", None)
    if _pending is None:
        st.sidebar.caption("Click above to check.")
    elif _pending > 0:
        st.sidebar.error(f"🔔 {_pending} pending request{'s' if _pending > 1 else ''}! → Join Team tab")
    else:
        st.sidebar.success("🟢 No pending requests")

    # IMPORTANT: Always use STATIC tab labels.
    tabs = st.tabs([
        "🔍 Analyze Error",
        "📄 Document Analyzer",
        "🤝 Join Team",
        "🧠 Saved History",
        "📊 My Trends",
    ])

    # =================================================
    # TAB 1 — ANALYZE ERROR
    # =================================================

    with tabs[0]:

        st.markdown("## 🔍 Analyze SAP Error")

        platform = st.selectbox(
            "🖥 Select SAP Domain / Platform",
            [
                "SAP ABAP On-Premise",
                "SAP BTP (Business Technology Platform)",
                "SAP CAPM (Cloud Application Programming Model)",
                "SAP Fiori / UI5",
                "SAP HANA",
                "SAP Basis",
                "SAP Functional (MM / SD / FI / HR)",
                "SAP Integration Suite (CPI)",
                "SAP S/4HANA",
                "SAP RAP (RESTful ABAP Programming)",
            ]
        )

        error_text = st.text_area(
            "📋 Paste SAP Error / Dump / Logs / Question",
            height=250,
            placeholder="Paste your SAP error, short dump, log, or ask any SAP question..."
        )

        uploaded_image = st.file_uploader(
            "📸 Upload Screenshot (optional)",
            type=["png", "jpg", "jpeg"]
        )

        if uploaded_image:
            if TESSERACT_AVAILABLE:
                try:
                    image = Image.open(uploaded_image)
                    extracted_text = pytesseract.image_to_string(image)
                    st.success("✅ OCR Extraction Successful")
                    st.text_area("📝 OCR Extracted Text", extracted_text, height=150)
                    if not error_text:
                        error_text = extracted_text
                except Exception as e:
                    st.warning(f"⚠️ OCR failed: {e}")
            else:
                st.info("ℹ️ Tesseract OCR not installed. "
                        "Download from https://github.com/tesseract-ocr/tesseract")

        if st.button("⚡ Analyze Error"):
            if not error_text.strip():
                st.warning("⚠️ Please enter an error or question.")
            else:
                # --- Check team for already-addressed similar issues FIRST ---
                # Store in session_state so results PERSIST across reruns
                _all_teams = fetch_user_teams(str(st.session_state.user_id))
                _pre_similar = []
                for _pt in _all_teams:
                    _pm = search_similar_team_defects(_pt[1], error_text)
                    for _m in _pm:
                        # Store serialisable tuple: (team_name, team_code, match_id, error, analysis)
                        _pre_similar.append((_pt[0], _pt[1], _m[0], _m[1], _m[2]))

                # Save matches to session state — survives page reruns
                st.session_state.similar_matches = _pre_similar

                with st.spinner("🤖 SAP-GPT is analyzing..."):
                    response = analyze_error(platform, error_text)

                st.session_state.last_analysis = (platform, error_text, response)
                # Clear follow-ups and feedback when a new question is asked
                st.session_state.followups = []
                st.session_state.feedback_given = False
                # similar_matches is set above before the AI call; reset only on new question

        # ---- Show similar/duplicate matches (persisted in session state) ----
        # Rendered OUTSIDE the button block so it survives reruns & tab switches
        if st.session_state.get("similar_matches"):
            st.markdown("---")
            st.warning("⚠️ **This issue has already been addressed in your team!**")
            for _tname, _tcode, _mid, _merr, _mans in st.session_state.similar_matches[:3]:
                with st.expander(f"🔁 Already solved in **{_tname}** — click to expand", expanded=True):
                    st.markdown("**Original Question / Error:**")
                    st.code(_merr[:600])
                    st.markdown("**Team Solution / Analysis:**")
                    st.success(_mans[:1500])
                    if st.button(
                        f"📂 Go to Join Team → view in {_tname}",
                        key=f"goto_team_{_tcode}_{_mid}"
                    ):
                        # Jump to Join Team tab (tab index 2)
                        st.session_state["jump_tab"] = 2
                        st.rerun()
            st.markdown("---")
            st.info("ℹ️ AI analysis is shown below for additional reference.")

        if st.session_state.get("last_analysis"):
            _p, _e, _r = st.session_state.last_analysis
            st.markdown("## 🎯 AI Analysis")
            st.markdown(_r)

        # Show follow-up Q&A thread if analysis exists
        if st.session_state.last_analysis:
            platform_a, error_text_a, response_a = st.session_state.last_analysis

            # Follow-up conversation thread
            if st.session_state.get("followups"):
                st.markdown("---")
                st.markdown("### 💬 Follow-up Conversation")
                for i, (fq, fa) in enumerate(st.session_state.followups):
                    with st.chat_message("user"):
                        st.markdown(fq)
                    with st.chat_message("assistant"):
                        st.markdown(fa)

            st.markdown("---")
            st.markdown("**💬 Ask a follow-up** *(type and press Enter)*")
            follow_up = st.chat_input(
                "e.g. How do I check for this in ST22? Can you show an ABAP example?",
                key="followup_chat"
            )
            if follow_up and follow_up.strip():
                # Build context from original + all previous follow-ups
                context = (
                    f"Platform: {platform_a}\n\n"
                    f"Original Error:\n{error_text_a}\n\n"
                    f"Initial Analysis:\n{response_a}"
                )
                for fq, fa in st.session_state.get("followups", []):
                    context += f"\n\nUser Follow-up: {fq}\nAssistant: {fa}"
                context += f"\n\nNew Follow-up Question: {follow_up}"
                with st.spinner("🤖 Answering follow-up..."):
                    fu_response = analyze_error(platform_a, context, use_feedback=False)
                if "followups" not in st.session_state:
                    st.session_state.followups = []
                st.session_state.followups.append((follow_up, fu_response))
                st.rerun()

        # Post-analysis actions
        if st.session_state.last_analysis:

            platform_a, error_text_a, response_a = st.session_state.last_analysis

            severity = "MEDIUM"
            if "HIGH" in response_a:
                severity = "HIGH"
            if "CRITICAL" in response_a:
                severity = "CRITICAL"

            report = generate_report(platform_a, error_text_a, response_a)

            st.markdown("---")
            st.markdown("### 📥 Download Report")

            download_format = st.radio("Format", ["TXT", "PDF", "WORD"], horizontal=True)

            if download_format == "TXT":
                st.download_button("⬇ Download (TXT)", report, file_name="sap_gpt_report.txt")

            elif download_format == "PDF":
                pdf_buffer = io.BytesIO()
                p = canvas.Canvas(pdf_buffer)
                textobject = p.beginText(40, 800)
                for line in report.split("\n"):
                    textobject.textLine(line[:120])
                p.drawText(textobject)
                p.save()
                pdf_buffer.seek(0)
                st.download_button(
                    "⬇ Download (PDF)", pdf_buffer,
                    file_name="sap_gpt_report.pdf", mime="application/pdf"
                )

            elif download_format == "WORD":
                doc = Document()
                doc.add_heading("SAP-GPT Analysis Report", 0)
                doc.add_paragraph(report)
                word_buffer = io.BytesIO()
                doc.save(word_buffer)
                word_buffer.seek(0)
                st.download_button(
                    "⬇ Download (Word)", word_buffer,
                    file_name="sap_gpt_report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            st.markdown("---")

            if st.button("💾 Save For Later"):
                save_error(
                    st.session_state.user_id,
                    platform_a,
                    error_text_a,
                    response_a,
                    severity
                )
                st.success("✅ Saved to your history!")

            st.markdown("---")
            st.markdown("### 👥 Save To Team")

            teams = fetch_user_teams(str(st.session_state.user_id))

            if teams:
                team_dropdown = [f"{t[0]} ({t[1]})" for t in teams]
                selected_team = st.selectbox("📁 Select Team", team_dropdown)

                if st.button("🚀 Push Error To Team"):
                    code = selected_team.split("(")[-1].replace(")", "").strip()
                    save_team_defect(code, selected_team, error_text_a, response_a,
                                    str(st.session_state.user_id))
                    st.success("✅ Added to team shared space!")
            else:
                st.info("ℹ️ No teams yet. Create one in the Join Team tab.")

            # ---- Feedback / Self-Training ----
            st.markdown("---")
            st.markdown("### 💡 Was this analysis helpful?")

            if not st.session_state.get("feedback_given"):
                col_good, col_bad, col_ok = st.columns([1, 1, 1])
                with col_good:
                    if st.button("👍 Found it Useful", key="fb_useful"):
                        save_feedback(
                            st.session_state.user_id, platform_a,
                            error_text_a, response_a, "useful"
                        )
                        st.session_state.feedback_given = True
                        st.success("🙏 Thanks! This helps SAP-GPT improve.")
                        st.rerun()
                with col_bad:
                    if st.button("👎 Not Helpful", key="fb_bad"):
                        save_feedback(
                            st.session_state.user_id, platform_a,
                            error_text_a, response_a, "not_useful"
                        )
                        st.session_state.feedback_given = True
                        st.warning("📝 Noted! We'll improve on this.")
                        st.rerun()
                with col_ok:
                    if st.button("😐 Partially Helpful", key="fb_ok"):
                        save_feedback(
                            st.session_state.user_id, platform_a,
                            error_text_a, response_a, "partial"
                        )
                        st.session_state.feedback_given = True
                        st.info("📝 Thanks for the feedback!")
                        st.rerun()

                # Optional comment box
                fb_comment = st.text_input(
                    "💬 Optional: What could be improved?",
                    key="fb_comment_input",
                    placeholder="e.g. The fix steps were unclear, needed more detail on transaction..."
                )
                if fb_comment and st.button("📤 Submit Comment", key="fb_submit_comment"):
                    save_feedback(
                        st.session_state.user_id, platform_a,
                        error_text_a, response_a, "comment", fb_comment
                    )
                    st.success("✅ Comment saved — thank you!")
            else:
                st.success("✅ Feedback already submitted for this analysis.")

    # =================================================
    # TAB 2 — DOCUMENT ANALYZER
    # =================================================

    with tabs[1]:

        st.markdown("## 📄 SAP Document Analyzer")

        uploaded_doc = st.file_uploader(
            "📂 Upload Document (PDF, Word, TXT)",
            type=["pdf", "docx", "txt"]
        )

        if uploaded_doc:

            analysis_type = st.selectbox(
                "🧠 Document Type",
                [
                    "FSD (Functional Specification)",
                    "TSD (Technical Specification)",
                    "Defect Report",
                    "Technical Document",
                    "Functional Document",
                    "Others",
                ]
            )

            if st.button("⚡ Analyze Document"):

                extracted_text = ""

                with st.spinner("📖 Extracting content..."):
                    try:
                        if uploaded_doc.name.endswith(".txt"):
                            extracted_text = uploaded_doc.read().decode("utf-8", errors="ignore")

                        elif uploaded_doc.name.endswith(".docx"):
                            d = Document(uploaded_doc)
                            extracted_text = "\n".join(p.text for p in d.paragraphs)

                        elif uploaded_doc.name.endswith(".pdf"):
                            reader = PyPDF2.PdfReader(uploaded_doc)
                            for page in reader.pages:
                                txt = page.extract_text()
                                if txt:
                                    extracted_text += txt

                    except Exception as e:
                        st.error(f"❌ Failed to read document: {e}")

                if extracted_text.strip():
                    prompt = f"""
Analyze this SAP document thoroughly.

Document Type: {analysis_type}

Content:
{extracted_text[:10000]}

Provide:
1. Executive Summary
2. Key Takeaways (bullet points)
3. Technical Notes / SAP Specifics
4. Risks & Gaps
5. Recommendations
6. Action Items
"""
                    with st.spinner("🤖 Analyzing..."):
                        doc_response = analyze_error("SAP Document", prompt)

                    st.markdown("## 📊 Document Analysis")
                    st.markdown(doc_response)
                else:
                    st.warning("⚠️ Could not extract text from document.")

    # =================================================
    # TAB 3 — JOIN TEAM
    # =================================================

    with tabs[2]:

        st.markdown("## 🤝 Team Collaboration")

        with st.expander("🚀 Create a New Team", expanded=True):

            team_name = st.text_input("👥 Team Name")
            project_name = st.text_input("📁 Project Name")
            notes = st.text_area("📝 Notes (optional)")

            if st.button("✅ Create Team"):
                if not team_name.strip():
                    st.warning("⚠️ Please enter a team name.")
                else:
                    team_code = create_team(
                        team_name, project_name,
                        str(st.session_state.user_id), notes
                    )
                    st.success(f"✅ Team **{team_name}** created!")
                    st.info(f"🔑 Team Code (share with colleagues): **`{team_code}`**")

        st.markdown("---")
        st.markdown("## 📋 My Teams")

        teams = fetch_user_teams(str(st.session_state.user_id))

        if teams:
            for t in teams:
                t_name   = t[0]
                t_code   = t[1]
                t_owner  = t[2]
                is_owner = str(t_owner) == str(st.session_state.user_id)
                role_tag = "👑 Owner" if is_owner else "👤 Member"

                with st.expander(f"🚀 {t_name}  |  {role_tag}  |  Code: {t_code}", expanded=True):

                    if is_owner:
                        st.info(f"🔑 Share this code with colleagues: **`{t_code}`**")
                    else:
                        st.success(f"✅ You are a member of this team (Code: `{t_code}`)")

                    st.markdown("### 👥 Team Members")
                    members = fetch_team_members(t_code)
                    if members:
                        for m in members:
                            uname = m[1] if m[1] else f"User #{m[0]}"
                            role  = m[2] if len(m) > 2 else "member"
                            icon  = "👑" if role == "owner" else "👤"
                            label = " *(Owner)*" if role == "owner" else ""
                            st.markdown(f"- {icon} **{uname}**{label}")
                    else:
                        st.caption("No members yet — share the code so others can join.")

                    st.markdown("### 🐛 Shared Errors & Analyses")
                    defects = fetch_team_defects(t_code)
                    if defects:
                        for d in defects:
                            d_id, d_team, d_error, d_analysis, d_by = d[0], d[1], d[2], d[3], d[4]
                            try:
                                poster_rows = fetch_team_members(t_code)
                                poster_name = next(
                                    (m[1] for m in poster_rows if str(m[0]) == str(d_by)),
                                    d_by
                                )
                            except Exception:
                                poster_name = d_by
                            with st.expander(f"📌 Error #{d_id}  |  Posted by: {poster_name}"):
                                st.markdown("**Error / Input:**")
                                st.code(d_error)
                                st.markdown("**Analysis:**")
                                st.write(d_analysis)
                    else:
                        st.caption("No errors pushed to this team yet.")

                    st.markdown("---")

                    if is_owner:
                        # Owner: Delete Team (cascades to all members)
                        st.markdown("### 🗑 Delete Team")
                        st.caption("⚠️ This will remove the team for ALL members permanently.")
                        confirm_key = f"confirm_del_{t_code}"
                        if st.session_state.get(confirm_key):
                            col_yes, col_no = st.columns([1, 1])
                            with col_yes:
                                if st.button("🔴 Yes, Delete", key=f"yes_del_{t_code}"):
                                    delete_team(t_code, str(st.session_state.user_id))
                                    st.session_state[confirm_key] = False
                                    st.success(f"✅ Team '{t_name}' deleted.")
                                    st.rerun()
                            with col_no:
                                if st.button("↩ Cancel", key=f"no_del_{t_code}"):
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                        else:
                            if st.button(f"🗑 Delete Team '{t_name}'", key=f"del_team_{t_code}"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                    else:
                        # Member: Leave Team
                        st.markdown("### 🚪 Leave Team")
                        st.caption("You will be removed from this team.")
                        leave_key = f"confirm_leave_{t_code}"
                        if st.session_state.get(leave_key):
                            col_yes, col_no = st.columns([1, 1])
                            with col_yes:
                                if st.button("🔴 Yes, Leave", key=f"yes_leave_{t_code}"):
                                    leave_team(t_code, str(st.session_state.user_id))
                                    st.session_state[leave_key] = False
                                    st.success(f"✅ You left team '{t_name}'.")
                                    st.rerun()
                            with col_no:
                                if st.button("↩ Cancel", key=f"no_leave_{t_code}"):
                                    st.session_state[leave_key] = False
                                    st.rerun()
                        else:
                            if st.button(f"🚪 Leave Team '{t_name}'", key=f"leave_{t_code}"):
                                st.session_state[leave_key] = True
                                st.rerun()
        else:
            st.info("ℹ️ No teams created yet.")

        st.markdown("---")
        st.markdown("## 🔗 Join Existing Team")

        join_code = st.text_input("🔑 Enter Team Code")

        if st.button("📨 Send Join Request"):
            if not join_code.strip():
                st.warning("⚠️ Please enter a team code.")
            else:
                send_join_request(join_code.strip().upper(), str(st.session_state.user_id))
                st.success("✅ Request sent! Waiting for team owner to approve.")

        st.markdown("---")
        st.markdown("## 🛡 Pending Join Requests (for your teams)")

        requests = fetch_join_requests(str(st.session_state.user_id))

        if requests:
            for req in requests:
                # req cols: id, team_code, requested_user(id), display_name, team_name
                req_id       = req[0]
                team_code_r  = req[1]
                user_id_r    = req[2]
                display_name = req[3]   # actual username, not a number
                team_name_r  = req[4]

                st.markdown(
                    f"👤 **{display_name}** wants to join **{team_name_r}** (`{team_code_r}`)"
                )

                col1, col2, _ = st.columns([1, 1, 4])

                with col1:
                    if st.button("✅ Approve", key=f"approve_{req_id}"):
                        approve_request(req_id, team_code_r, user_id_r)
                        st.success(f"✅ {display_name} approved!")
                        st.rerun()

                with col2:
                    if st.button("❌ Reject", key=f"reject_{req_id}"):
                        reject_request(req_id)
                        st.warning(f"🚫 {display_name} rejected.")
                        st.rerun()

                st.divider()
        else:
            st.info("ℹ️ No pending requests.")

    # =================================================
    # TAB 4 — SAVED HISTORY
    # =================================================

    with tabs[3]:

        st.markdown("## 🧠 Saved History")

        rows = fetch_user_history(st.session_state.user_id)

        if rows:
            for row in rows:
                with st.expander(f"🖥 {row[2]}  |  Severity: {row[5]}  |  #{row[0]}"):
                    st.markdown("**Input / Error:**")
                    st.code(row[3])
                    st.markdown("**Analysis:**")
                    st.write(row[4])
                    if st.button(f"🗑 Delete", key=f"del_{row[0]}"):
                        delete_error(row[0])
                        st.rerun()
        else:
            st.info("ℹ️ Nothing saved yet.")

    # =================================================
    # TAB 5 — TRENDS
    # =================================================

    with tabs[4]:

        st.markdown("## 📊 My SAP Trends")

        rows = fetch_user_history(st.session_state.user_id)

        if rows:
            df = pd.DataFrame([{"platform": r[2], "severity": r[5]} for r in rows])

            col1, col2 = st.columns(2)

            with col1:
                fig = px.pie(df, names="severity", title="Severity Distribution",
                             color_discrete_sequence=px.colors.sequential.Plasma)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig2 = px.histogram(df, x="platform", title="Errors By Platform",
                                    color_discrete_sequence=["#7c3aed"])
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("ℹ️ No data yet.")
