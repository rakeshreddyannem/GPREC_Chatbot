import streamlit as st
import config
from src.database import DatabaseManager
import ui.components
from typing import Optional, Tuple
from pathlib import Path
import importlib

import time
from contextlib import contextmanager

# Timing metrics tracker (console logging only)
@contextmanager
def time_block(label: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[TIMING] {label}: {elapsed:.4f}s", flush=True)

try:
    from ui.components import (
        load_css, render_header, render_welcome_state, 
        render_source_card, render_not_found, render_clarify,
        render_notices_page, render_deadlines_page, render_topic_page, format_date,
        render_academics_page, render_subject_assistance_page, render_admin_page,
        render_chat_faculty_cards, render_loading_skeleton, render_html_block,
        render_faculty_directory_page, get_base64_of_bin_file
    )
except (ImportError, AttributeError):
    importlib.reload(ui.components)
    from ui.components import (
        load_css, render_header, render_welcome_state, 
        render_source_card, render_not_found, render_clarify,
        render_notices_page, render_deadlines_page, render_topic_page, format_date,
        render_academics_page, render_subject_assistance_page, render_admin_page,
        render_chat_faculty_cards, render_html_block,
        render_faculty_directory_page, get_base64_of_bin_file
    )
    render_loading_skeleton = getattr(ui.components, "render_loading_skeleton", None)
    if render_loading_skeleton is None:
        def render_loading_skeleton():
            render_html_block("""
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
            """)
import os
import glob
import json
from datetime import datetime

st.set_page_config(
    page_title="GPREC AI Student Assistant",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="auto"
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

@st.cache_resource
def get_database_v6():
    import importlib
    import src.database
    importlib.reload(src.database)
    return src.database.DatabaseManager()

def get_database():
    db = get_database_v6()
    if not hasattr(db, "get_syllabus_schemes") or not hasattr(db, "get_subject_assistance_subjects"):
        import importlib
        import src.database
        importlib.reload(src.database)
        db = src.database.DatabaseManager()
    return db

def log_startup_metrics(pipeline_load_sec: float):
    mem_mb = 0.0
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        mem_mb = rusage.ru_maxrss / 1024.0
    except Exception:
        try:
            import subprocess
            out = subprocess.check_output(['powershell', '-Command', f'(Get-Process -Id {os.getpid()}).WorkingSet64 / 1MB'])
            mem_mb = float(out.decode().strip())
        except Exception:
            pass

    print(f"[STARTUP] Pipeline & models initialized in {pipeline_load_sec:.2f}s", flush=True)
    if mem_mb > 0:
        print(f"[STARTUP] Memory in use: {mem_mb:.2f} MB ({mem_mb / 1024.0:.2f} GB)", flush=True)
        if mem_mb > 3072:
            print(f"[WARNING] High memory usage detected: {mem_mb:.2f} MB exceeds 3 GB!", flush=True)
        else:
            print(f"[STARTUP] Memory check OK: under 3 GB threshold.", flush=True)

# Initialize components only once (version bumped to v5 to invalidate stale cached instances)
@st.cache_resource
def get_pipeline_v5():
    from src.embeddings import Embedder
    from src.vectorstore import VectorStore
    from src.rag_pipeline import RAGPipeline
    t_start = time.perf_counter()
    db = get_database()
    embedder = Embedder()
    vstore = VectorStore(embedder.dimension)
    pipe = RAGPipeline(embedder, vstore, db=db)
    elapsed = time.perf_counter() - t_start
    log_startup_metrics(elapsed)
    return pipe

def check_rate_limit() -> Tuple[bool, str]:
    """
    Per-session rate limit:
    - At most 6 questions per minute
    - At most 60 questions per hour
    """
    now = time.time()
    if "rate_limit_timestamps" not in st.session_state:
        st.session_state.rate_limit_timestamps = []

    # Keep timestamps within the last hour (3600 seconds)
    st.session_state.rate_limit_timestamps = [
        t for t in st.session_state.rate_limit_timestamps if now - t < 3600
    ]

    recent_minute = [t for t in st.session_state.rate_limit_timestamps if now - t < 60]

    if len(recent_minute) >= 6:
        return False, "⏳ You're asking questions a bit too quickly. Please wait a moment before sending another query (rate limit: 6 questions per minute)."

    if len(st.session_state.rate_limit_timestamps) >= 60:
        return False, "⏳ You have reached the question limit for this browser session (rate limit: 60 questions per hour). Please take a break and try again later."

    return True, ""

def record_question_timestamp():
    if "rate_limit_timestamps" not in st.session_state:
        st.session_state.rate_limit_timestamps = []
    st.session_state.rate_limit_timestamps.append(time.time())

def render_app_footer(db):
    try:
        last_date = db.get_last_data_update_date()
    except Exception:
        last_date = "October 2026"

    st.markdown(f"""
        <div style="margin-top: 3.5rem; padding: 1.5rem 0 1rem 0; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 0.8rem; line-height: 1.6;">
            <div>Knowledge base last updated: <strong>{last_date}</strong></div>
            <div>Student project. Verify important information on the official GPREC website.</div>
        </div>
    """, unsafe_allow_html=True)

def get_confidence_badge_html(confidence: str) -> Optional[str]:
    """Returns HTML for small badge if confidence is Medium or Low; None for High."""
    conf_str = (confidence or "").strip().lower()
    if conf_str in ["medium", "low"]:
        bg = "#fef3c7" if conf_str == "medium" else "#fee2e2"
        color = "#92400e" if conf_str == "medium" else "#991b1b"
        border = "#fcd34d" if conf_str == "medium" else "#fca5a5"
        return (
            f'<div style="margin: 6px 0 10px 0;">'
            f'<span style="display:inline-block; padding: 3px 10px; background-color:{bg}; color:{color}; '
            f'border: 1px solid {border}; border-radius: 12px; font-size: 0.78rem; font-weight: 500;">'
            f'⚠️ Check this on the official website'
            f'</span></div>'
        )
    return None


def render_answer_footer(msg_idx: int, answer_text: str, question_text: str, sources: list, confidence: str = "High", key_prefix: str = "src", db = None):
    """
    Renders the unified answer footer:
    1. Confidence badge ONLY when Medium or Low.
    2. Sources as small link buttons (up to 3).
    3. Action buttons: Copy answer to clipboard and Thumbs Up / Down saved to feedback table.
    """
    # 1. Coloured badge ONLY when confidence is Medium or Low
    badge_html = get_confidence_badge_html(confidence)
    if badge_html:
        st.markdown(badge_html, unsafe_allow_html=True)

    # 2. Sources as small link buttons
    if sources:
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
            if len(clean_title) > 38:
                clean_title = clean_title[:35] + "..."
            display_sources.append((clean_title, url))

        if display_sources:
            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            src_cols = st.columns(min(len(display_sources[:3]), 3))
            for i, (short_title, url) in enumerate(display_sources[:3]):
                with src_cols[i]:
                    st.link_button(f"📄 {short_title}", url, key=f"{key_prefix}_src_{i}", use_container_width=True)

    # 3. Actions Row: Copy button and Thumbs Up / Down feedback
    if answer_text:
        fb_state_key = f"fb_rating_{key_prefix}_{msg_idx}"
        curr_fb = st.session_state.get(fb_state_key)

        st.markdown("<div style='margin-top: 6px;'></div>", unsafe_allow_html=True)
        act_col1, act_col2, act_col3, _ = st.columns([0.22, 0.14, 0.14, 0.50])
        
        with act_col1:
            escaped_ans = answer_text.replace('\\', '\\\\').replace('"', '&quot;').replace("'", "\\'").replace('\n', '\\n')
            st.markdown(f"""
                <button type="button" class="btn-copy-ans" onclick="navigator.clipboard.writeText('{escaped_ans}'); this.innerText='✓ Copied'; setTimeout(() => this.innerText='📋 Copy', 2000);" title="Copy answer to clipboard">
                    📋 Copy
                </button>
            """, unsafe_allow_html=True)

        with act_col2:
            up_btn = st.button("👍", key=f"{key_prefix}_up_{msg_idx}", help="Helpful answer", disabled=(curr_fb == 1))
            if up_btn and db:
                db.save_feedback(question=question_text, answer=answer_text, rating=1, message_idx=msg_idx)
                st.session_state[fb_state_key] = 1
                st.rerun()

        with act_col3:
            down_btn = st.button("👎", key=f"{key_prefix}_down_{msg_idx}", help="Needs improvement", disabled=(curr_fb == -1))
            if down_btn and db:
                db.save_feedback(question=question_text, answer=answer_text, rating=-1, message_idx=msg_idx)
                st.session_state[fb_state_key] = -1
                st.rerun()

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
    # 0. Fast health check endpoint (probed by Docker / container orchestrator)
    if st.query_params.get("healthz") == "1":
        db_file = Path(config.DB_PATH)
        idx_file = Path(config.FAISS_INDEX_PATH)
        meta_file = Path(config.FAISS_METADATA_PATH)
        db_ok = db_file.exists() and db_file.stat().st_size > 0
        idx_ok = idx_file.exists() and idx_file.stat().st_size > 0
        meta_ok = meta_file.exists() and meta_file.stat().st_size > 0
        is_healthy = db_ok and idx_ok and meta_ok
        st.json({
            "status": "healthy" if is_healthy else "unhealthy",
            "database": db_ok,
            "vector_index": idx_ok,
            "vector_metadata": meta_ok
        })
        st.stop()

    # 1. Check that required knowledge base files exist before creating or initializing DB
    db_file = Path(config.DB_PATH)
    idx_file = Path(config.FAISS_INDEX_PATH)
    meta_file = Path(config.FAISS_METADATA_PATH)

    if not db_file.exists() or not idx_file.exists() or not meta_file.exists() or db_file.stat().st_size == 0 or idx_file.stat().st_size == 0:
        st.error("🚨 **Data files are missing.** The required knowledge base database (`gprec_knowledge.db`) or vector store files (`vectorstore/`) could not be found or are empty. Please ensure the full data bundle is uploaded.")
        st.stop()

    startup_placeholder = None
    if "pipeline_warmed" not in st.session_state:
        startup_placeholder = st.empty()
        startup_placeholder.info("Starting up, one moment...")

    with time_block("css and logo"):
        load_css()
        # Touch logo read for baseline measurement
        _ = get_base64_of_bin_file("gprec_logo1.png")
    
    with time_block("pipeline load"):
        pipeline = get_pipeline_v5()

    with time_block("database init"):
        db = get_database()

    if "pipeline_warmed" not in st.session_state:
        st.session_state.pipeline_warmed = True
        if startup_placeholder is not None:
            startup_placeholder.empty()
    
    if pipeline.client is None:
        provider = getattr(config, "LLM_PROVIDER", "").lower()
        key_var = "OPENROUTER_API_KEY" if provider == "openrouter" else "GEMINI_API_KEY"
        st.warning(f"⚠️ **{key_var} is not configured.** Please set the `{key_var}` environment variable or secret to enable AI responses.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "prompt_trigger" not in st.session_state:
        st.session_state.prompt_trigger = None

    admin_password = (os.environ.get("ADMIN_PASSWORD") or getattr(config, "ADMIN_PASSWORD", "") or "").strip()
    admin_password_set = bool(admin_password)
    is_admin_param = admin_password_set and (st.query_params.get("admin") == "1")

    # If student navigates to ?admin=1 but admin password is not set, inform them it is disabled
    if st.query_params.get("admin") == "1" and not admin_password_set:
        st.warning("⚠️ Admin access is disabled because `ADMIN_PASSWORD` is not configured in the environment.")

    if "page" not in st.session_state:
        st.session_state.page = "Admin" if is_admin_param else "Ask AI"
        
    if "admin_mode" not in st.session_state:
        st.session_state.admin_mode = False

    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    # If admin URL is not active or admin password not set, ensure student cannot access admin page or mode
    if not is_admin_param:
        if st.session_state.page == "Admin":
            st.session_state.page = "Ask AI"
        st.session_state.admin_mode = False
        st.session_state.admin_authenticated = False

    # Sidebar Navigation
    with time_block("sidebar"):
        with st.sidebar:
            if st.button("➕ New Chat", use_container_width=True, type="primary"):
                st.session_state.messages = []
                st.session_state.prompt_trigger = None
                st.session_state.page = "Ask AI"
                st.rerun()

            st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
            st.markdown("<div class='sidebar-group-label'>🤖 AI ASSISTANTS</div>", unsafe_allow_html=True)
            
            nav_groups = {
                "Ask AI": "💬",
                "Subject Assistance": "🎓",
                "Academics": "📘",
                "Latest Notices": "📅",
                "Deadlines": "⏳"
            }
            if is_admin_param and admin_password_set:
                nav_groups["Admin"] = "⚙️"

            if st.session_state.page not in nav_groups:
                st.session_state.page = "Ask AI"

            def _on_nav_change():
                st.session_state.page = st.session_state.nav_radio

            if "nav_radio" not in st.session_state or st.session_state.nav_radio != st.session_state.page:
                st.session_state.nav_radio = st.session_state.page

            st.radio(
                "Go to",
                list(nav_groups.keys()),
                format_func=lambda x: f"{nav_groups[x]} {x}",
                key="nav_radio",
                on_change=_on_nav_change,
                label_visibility="collapsed"
            )

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
                
            render_html_block(f"""
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
            """)
        
    # Routing based on selected page
    if st.session_state.page == "Ask AI":
        with time_block("render: Ask AI"):
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
                                    prev_q = ""
                                    if idx > 0 and st.session_state.messages[idx - 1].get("role") == "user":
                                        prev_q = st.session_state.messages[idx - 1].get("content", "")
                                    render_answer_footer(
                                        msg_idx=idx,
                                        answer_text=msg.get("content", ""),
                                        question_text=prev_q,
                                        sources=msg.get("sources", []),
                                        confidence=msg.get("confidence", "High"),
                                        key_prefix=f"hist_{idx}",
                                        db=db
                                    )

            # c. Then call st.chat_input
            chat_input_val = st.chat_input("Ask about GPREC...")

            prompt = st.session_state.prompt_trigger or chat_input_val
            
            # Clear trigger so it doesn't loop
            if st.session_state.prompt_trigger:
                st.session_state.prompt_trigger = None
                
            if prompt:
                allowed, limit_msg = check_rate_limit()
                if not allowed:
                    st.warning(limit_msg)
                else:
                    record_question_timestamp()
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
                                    try:
                                        res = pipeline.answer_question(
                                            prompt,
                                            history=history,
                                            study_mode=st.session_state.get("study_mode", False)
                                        )
                                    except Exception as e:
                                        res = {
                                            "response_type": "ERROR",
                                            "answer": f"I encountered an unexpected issue while retrieving the answer: {e}. Please try asking again.",
                                            "sources": [],
                                            "confidence": "Low",
                                            "confidence_reason": "Execution error fallback"
                                        }
                                        
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
                                        render_answer_footer(
                                            msg_idx=asst_idx,
                                            answer_text=answer,
                                            question_text=prompt,
                                            sources=sources,
                                            confidence=confidence,
                                            key_prefix=f"curr_{asst_idx}",
                                            db=db
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

                    # 5. Log chat to database (safely wrapped against disk reset/read-only)
                    db.log_chat(
                        query=prompt,
                        response=answer,
                        response_type=resp_type,
                        confidence=confidence
                    )
                    # d. Do NOT call st.rerun after a response. Do not render the new turn a second time anywhere.
                
            # Clear chat button
            if st.session_state.messages:
                st.markdown("<br>", unsafe_allow_html=True)
                col1, col2, col3 = st.columns([1,2,1])
                with col2:
                    if st.button("Clear chat", use_container_width=True):
                        st.session_state.messages = []
                        st.rerun()

    elif st.session_state.page == "Subject Assistance":
        with time_block("render: Subject Assistance"):
            render_subject_assistance_page(pipeline, db)
    elif st.session_state.page == "Academics":
        with time_block("render: Academics"):
            render_academics_page(db)
    elif st.session_state.page == "Latest Notices":
        with time_block("render: Latest Notices"):
            render_notices_page(db)
    elif st.session_state.page == "Deadlines":
        with time_block("render: Deadlines"):
            render_deadlines_page(pipeline, db=db)

    elif is_admin_param and st.session_state.page == "Admin":
        env_admin_pass = (os.environ.get("ADMIN_PASSWORD") or getattr(config, "ADMIN_PASSWORD", "") or "").strip()
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

    # Render global application footer
    render_app_footer(db)

if __name__ == "__main__":
    main()

