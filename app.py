import streamlit as st
import config
from src.embeddings import Embedder
from src.vectorstore import VectorStore
from src.rag_pipeline import RAGPipeline
from src.database import DatabaseManager
import importlib
import ui.components

try:
    from ui.components import (
        load_css, render_header, render_welcome_state, 
        render_source_card, render_not_found, render_clarify,
        render_notices_page, render_deadlines_page, render_topic_page, format_date,
        render_academics_page, render_admin_page,
        render_chat_faculty_cards, render_loading_skeleton
    )
except (ImportError, AttributeError):
    importlib.reload(ui.components)
    from ui.components import (
        load_css, render_header, render_welcome_state, 
        render_source_card, render_not_found, render_clarify,
        render_notices_page, render_deadlines_page, render_topic_page, format_date,
        render_academics_page, render_admin_page,
        render_chat_faculty_cards
    )
    render_loading_skeleton = getattr(ui.components, "render_loading_skeleton", None)
    if render_loading_skeleton is None:
        def render_loading_skeleton():
            st.markdown("""
                <div class="skeleton-card">
                    <div class="skeleton-header">
                        <div class="skeleton-avatar skeleton-shimmer"></div>
                        <div class="skeleton-header-text">
                            <div class="skeleton-line skeleton-shimmer" style="width: 140px; height: 14px;"></div>
                            <div class="skeleton-line skeleton-shimmer" style="width: 85px; height: 10px; margin-top: 4px;"></div>
                        </div>
                    </div>
                    <div class="skeleton-body">
                        <div class="skeleton-line skeleton-shimmer" style="width: 95%;"></div>
                        <div class="skeleton-line skeleton-shimmer" style="width: 88%;"></div>
                        <div class="skeleton-line skeleton-shimmer" style="width: 65%;"></div>
                    </div>
                    <div class="skeleton-footer">
                        <span class="skeleton-spinner-ring"></span>
                        <span class="skeleton-footer-text">Consulting official GPREC knowledge base & drafting response...</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
import os
import glob
import json
from datetime import datetime

st.set_page_config(
    page_title="GPREC AI Student Assistant",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded"
)

def get_latest_report():
    report_files = glob.glob(os.path.join(config.REPORTS_DIR, "crawl_report_*.json"))
    if not report_files:
        return None
    latest_file = max(report_files, key=os.path.getctime)
    try:
        with open(latest_file, "r") as f:
            return json.load(f)
    except:
        return None

# Initialize components only once
@st.cache_resource
def get_pipeline_v3():
    embedder = Embedder()
    vstore = VectorStore(embedder.dimension)
    return RAGPipeline(embedder, vstore)

def render_answer_sources(sources, confidence="High", key_prefix="src"):
    conf_str = (confidence or "").strip().lower()
    # 1. Show a small coloured badge ONLY when confidence is Medium or Low
    if conf_str in ["medium", "low"]:
        bg = "#fef3c7" if conf_str == "medium" else "#fee2e2"
        color = "#92400e" if conf_str == "medium" else "#991b1b"
        border = "#fcd34d" if conf_str == "medium" else "#fca5a5"
        st.markdown(
            f'<div style="margin: 6px 0 10px 0;">'
            f'<span style="display:inline-block; padding: 3px 10px; background-color:{bg}; color:{color}; '
            f'border: 1px solid {border}; border-radius: 12px; font-size: 0.78rem; font-weight: 500;">'
            f'⚠️ Check this on the official website'
            f'</span></div>',
            unsafe_allow_html=True
        )

    if not sources:
        return

    seen_urls = set()
    display_sources = []
    for s in sources:
        url = s.get("source_url") or "https://gprec.ac.in"
        if url in seen_urls:
            continue
        seen_urls.add(url)
        raw_title = s.get("title") or "Official College Page"
        clean_title = (
            raw_title.replace("GPREC - ", "")
            .replace("GPREC | ", "")
            .replace("Official Directory: ", "")
            .replace("Verified Fact: ", "")
            .strip()
        )
        if len(clean_title) > 40:
            clean_title = clean_title[:37] + "..."
        display_sources.append((clean_title, url))

    if not display_sources:
        return

    display_sources = display_sources[:3]

    for i, (short_title, url) in enumerate(display_sources):
        st.link_button(f"Open: {short_title}", url, key=f"{key_prefix}_{i}")

def render_syllabus_units(matched_syllabus, key_prefix="syl"):
    if not matched_syllabus:
        return
    course_name = matched_syllabus.get("course_title") or "Course Syllabus"
    units = matched_syllabus.get("units", [])
    doc_url = matched_syllabus.get("document_url")
    st.markdown(f"**📖 Relevant GPREC Syllabus: {course_name}**")
    if units:
        for idx, u in enumerate(units[:6]):
            st.markdown(f"- **Unit {idx+1}:** {u}")
    if doc_url:
        st.link_button(f"Open: {course_name} Syllabus", doc_url, key=f"{key_prefix}_doc")

def main():
    load_css()
    
    pipeline = get_pipeline_v3()
    db = DatabaseManager()
    
    if pipeline.client is None:
        provider = getattr(config, "LLM_PROVIDER", "").lower()
        key_var = "OPENROUTER_API_KEY" if provider == "openrouter" else "GEMINI_API_KEY"
        st.error(f"⚠️ {key_var} is not set in the `.env` file. The assistant cannot generate responses.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "prompt_trigger" not in st.session_state:
        st.session_state.prompt_trigger = None

    is_admin_param = st.query_params.get("admin") == "1"

    if "page" not in st.session_state:
        st.session_state.page = "Admin" if is_admin_param else "Ask AI"
        
    if "admin_mode" not in st.session_state:
        st.session_state.admin_mode = False

    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    # If admin URL is not active, ensure student cannot access admin page or mode
    if not is_admin_param:
        if st.session_state.page == "Admin":
            st.session_state.page = "Ask AI"
        st.session_state.admin_mode = False
        st.session_state.admin_authenticated = False

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("<div class='sidebar-nav-title'>Navigation</div>", unsafe_allow_html=True)
        pages = {
            "Ask AI": "💬", 
            "Academics": "📘",
            "Latest Notices": "📅", 
            "Deadlines": "⏳", 
            "Contact": "📞", 
            "About": "ℹ️"
        }
        
        # Show Admin page option only when URL has ?admin=1
        if is_admin_param:
            pages["Admin"] = "⚙️"
        
        if st.session_state.page not in pages:
            st.session_state.page = "Ask AI"

        selected_page = st.radio("Go to", list(pages.keys()), format_func=lambda x: f"{pages[x]} {x}", index=list(pages.keys()).index(st.session_state.page), label_visibility="collapsed")
        if selected_page != st.session_state.page:
            st.session_state.page = selected_page
            st.rerun()
            
        st.markdown("---")
        study_mode = st.toggle(
            "Study mode (academic help)",
            value=st.session_state.get("study_mode", False),
            key="study_mode_toggle"
        )
        st.session_state.study_mode = study_mode
        if study_mode:
            st.caption("📚 Answers academic & concept doubts using general knowledge + GPREC syllabus.")
        st.markdown("---")
        
        latest_report = get_latest_report()
        last_checked = format_date(latest_report.get("timestamp", "")) if latest_report else "Oct 2026"
            
        st.markdown(f"""
            <div class="kb-status-card">
                <div class="kb-status-header">
                    <span class="status-indicator">
                        <span class="status-pulse-ring"></span>
                        <span class="status-pulse-dot"></span>
                    </span>
                    <span class="kb-status-title">Knowledge Base Status</span>
                </div>
                <div class="kb-index-badge">
                    <span class="kb-index-dot"></span>
                    Indexed: Oct 2026
                </div>
                <div class="kb-status-details">
                    <div class="kb-detail-row">
                        <span class="kb-detail-label">Status:</span>
                        <span class="kb-detail-val">Live & Active</span>
                    </div>
                    <div class="kb-detail-row">
                        <span class="kb-detail-label">Last Checked:</span>
                        <span class="kb-detail-val">{last_checked}</span>
                    </div>
                </div>
                <div class="kb-disclaimer">
                    Official GPREC regulations, syllabus, faculty directory & exam circulars.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    # Routing based on selected page
    if st.session_state.page == "Ask AI":
        render_header()
        
        # a. Initialise st.session_state.messages once (ensuring safe fallback)
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        # b. Render ALL saved messages in one loop, in a single st.container
        chat_container = st.container()
        welcome_placeholder = None

        with chat_container:
            if not st.session_state.messages:
                welcome_placeholder = st.empty()
                with welcome_placeholder.container():
                    render_welcome_state()
            else:
                for idx, msg in enumerate(st.session_state.messages):
                    with st.container(key=f"msg_block_{idx}"):
                        with st.chat_message(msg["role"]):
                            if msg.get("rewritten_query"):
                                st.caption(f"🔍 Searching for: *{msg['rewritten_query']}*")
                            resp_type = msg.get("response_type", "ANSWERED")
                            if resp_type == "CLARIFY":
                                render_clarify(
                                    msg.get("clarify_question") or msg["content"], 
                                    msg.get("clarify_options", []), 
                                    key_prefix=f"hist_{idx}"
                                )
                            elif resp_type == "NOT_FOUND":
                                render_not_found(msg.get("suggested_questions"))
                            else:
                                is_particular = msg.get("is_particular_faculty", False) or (
                                    bool(msg.get("faculty_records")) and len(msg.get("faculty_records", [])) in [1, 2] and not any(k in msg.get("content", "").lower() for k in ["faculty members of the department", "regular faculty members", "faculty count"])
                                )
                                if is_particular and msg.get("faculty_records"):
                                    render_chat_faculty_cards(msg["faculty_records"], key_prefix=f"hist_{idx}")
                                else:
                                    st.markdown(msg["content"])
                                    if msg.get("faculty_records"):
                                        render_chat_faculty_cards(msg["faculty_records"], key_prefix=f"hist_{idx}")
                                if msg.get("matched_syllabus"):
                                    render_syllabus_units(msg.get("matched_syllabus"), key_prefix=f"hist_{idx}_syl")
                                render_answer_sources(
                                    msg.get("sources", []), 
                                    msg.get("confidence", "High"), 
                                    key_prefix=f"hist_{idx}"
                                )

        # c. Then call st.chat_input
        chat_input_val = st.chat_input("Ask about GPREC...")

        prompt = st.session_state.prompt_trigger or chat_input_val
        
        # Clear trigger so it doesn't loop
        if st.session_state.prompt_trigger:
            st.session_state.prompt_trigger = None
            
        if prompt:
            # If welcome state was rendered on this first interaction, clear it
            if welcome_placeholder is not None:
                welcome_placeholder.empty()

            # Extract the last 3 question/answer pairs from existing conversation
            history = []
            for i in range(len(st.session_state.messages) - 1):
                m_curr = st.session_state.messages[i]
                m_next = st.session_state.messages[i+1]
                if m_curr.get("role") == "user" and m_next.get("role") == "assistant":
                    history.append({
                        "question": m_curr.get("content", ""),
                        "answer": m_next.get("content", "")
                    })
            history = history[-3:]

            # 1. Append user message to session state
            st.session_state.messages.append({"role": "user", "content": prompt})
            user_idx = len(st.session_state.messages) - 1

            # 2. Show user message with st.chat_message("user") inside chat_container
            with chat_container:
                with st.container(key=f"msg_block_{user_idx}"):
                    with st.chat_message("user"):
                        st.markdown(prompt)

                # 3. Inside st.chat_message("assistant") create ONE placeholder = st.empty()
                asst_idx = user_idx + 1
                with st.container(key=f"msg_block_{asst_idx}"):
                    with st.chat_message("assistant"):
                        placeholder = st.empty()
                        # Show the "Generating answer..." status inside it
                        with placeholder.container():
                            render_loading_skeleton()
                            res = pipeline.answer_question(
                                prompt,
                                history=history,
                                study_mode=st.session_state.get("study_mode", False)
                            )
                                
                        resp_type = res.get("response_type", "ANSWERED")
                        answer = res.get("answer", "")
                        sources = res.get("sources", [])
                        confidence = res.get("confidence", "Medium")
                        confidence_reason = res.get("confidence_reason", "")
                        is_recent_query = any(word in prompt.lower() for word in ["latest", "current", "deadline", "recent", "upcoming"])
                        is_particular = res.get("is_particular_faculty", False) or (
                            bool(res.get("faculty_records")) and len(res.get("faculty_records", [])) in [1, 2] and not any(k in answer.lower() for k in ["faculty members of the department", "regular faculty members", "faculty count"])
                        )
                        
                        # Replace the placeholder with the final answer and sources area
                        with placeholder.container():
                            if res.get("rewritten_query"):
                                st.caption(f"🔍 Searching for: *{res['rewritten_query']}*")
                            if resp_type == "CLARIFY":
                                render_clarify(
                                    res.get("clarify_question", answer), 
                                    res.get("clarify_options", []),
                                    key_prefix=f"curr_{asst_idx}"
                                )
                            elif resp_type == "NOT_FOUND":
                                render_not_found(res.get("suggested_questions"))
                            else:
                                if is_particular and res.get("faculty_records"):
                                    render_chat_faculty_cards(res["faculty_records"], key_prefix=f"curr_{asst_idx}")
                                else:
                                    st.markdown(answer)
                                    if res.get("faculty_records"):
                                        render_chat_faculty_cards(res["faculty_records"], key_prefix=f"curr_{asst_idx}")
                                if res.get("matched_syllabus"):
                                    render_syllabus_units(res.get("matched_syllabus"), key_prefix=f"curr_{asst_idx}_syl")
                                render_answer_sources(
                                    sources, 
                                    confidence, 
                                    key_prefix=f"curr_{asst_idx}"
                                )
                                
            # 4. Append assistant message to session state
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "response_type": resp_type,
                "rewritten_query": res.get("rewritten_query"),
                "matched_syllabus": res.get("matched_syllabus"),
                "clarify_question": res.get("clarify_question"),
                "clarify_options": res.get("clarify_options", []),
                "suggested_questions": res.get("suggested_questions", []),
                "sources": sources if resp_type in ["ANSWERED", "PARTIAL"] else [],
                "confidence": confidence,
                "confidence_reason": confidence_reason,
                "is_recent_query": is_recent_query,
                "faculty_records": res.get("faculty_records", []),
                "is_particular_faculty": is_particular
            })
            # d. Do NOT call st.rerun after a response. Do not render the new turn a second time anywhere.
            
        # Clear chat button
        if st.session_state.messages:
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                if st.button("Clear chat", use_container_width=True):
                    st.session_state.messages = []
                    st.rerun()

    elif st.session_state.page == "Academics":
        render_academics_page(db)
    elif st.session_state.page == "Latest Notices":
        render_notices_page(db)
    elif st.session_state.page == "Deadlines":
        render_deadlines_page(pipeline, db=db)
    elif st.session_state.page == "Contact":
        render_topic_page("📞 Contact", "Get in touch with college administration and departments.", [
            "What is the college contact number?",
            "What is the email address of the admissions office?",
            "How do I reach the college campus?",
            "Who should I contact for fee-related queries?"
        ])
    elif st.session_state.page == "About":
        render_topic_page("ℹ️ About GPREC", "General information about G. Pulla Reddy Engineering College.", [
            "When was GPREC established?",
            "Is the college autonomous?",
            "What are the accreditations of the college?",
            "Who is the principal of the college?"
        ])
    elif is_admin_param and st.session_state.page == "Admin":
        env_admin_pass = os.environ.get("ADMIN_PASSWORD", "")
        if not env_admin_pass:
            st.error("⚠️ ADMIN_PASSWORD is not configured in the environment. Admin access is disabled.")
        elif not st.session_state.get("admin_authenticated", False):
            st.subheader("🔐 Admin Authentication")
            st.markdown("Please enter the administrator password to access the Admin Panel.")
            with st.form("admin_auth_form"):
                entered_pass = st.text_input("Admin Password", type="password")
                auth_submit = st.form_submit_button("Log In", type="primary")
                if auth_submit:
                    if entered_pass == env_admin_pass:
                        st.session_state.admin_authenticated = True
                        st.session_state.admin_mode = True
                        st.success("Authenticated successfully!")
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            render_admin_page(db)

if __name__ == "__main__":
    main()
