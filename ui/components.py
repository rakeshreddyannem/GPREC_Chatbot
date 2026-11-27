import streamlit as st
import base64
import os
import json
import re
import time
from datetime import datetime

from src.subject_assistant import (
    VERIFICATION_LINE,
    PRACTICE_DISCLAIMER,
    split_topics,
    get_subject_cache_key,
    generate_example_doubts,
    build_topic_explanation_prompt,
    build_practice_prompt,
    build_quick_revision_prompt,
    call_subject_llm,
    answer_subject_doubt,
    clean_subject_response,
    extract_mcq_json,
    generate_subject_mcqs,
    generate_subject_short_answers
)
from src.curated_links import (
    get_branch_latest_syllabus_pdf,
    get_branch_latest_syllabus_info,
    get_all_latest_syllabus_links_for_branch,
    is_cross_branch_url
)

def extract_unit_outcome(full_outcomes: str, unit_num: Any = None) -> str:
    """Extracts only the Course Outcome corresponding to a specific unit (e.g. Unit 1 -> CO1)."""
    if not full_outcomes or not str(full_outcomes).strip():
        return ""
    if unit_num is None or str(unit_num).strip().lower() in ("", "none", "0"):
        return full_outcomes.strip()
    
    # Match CO<unit_num>:
    pattern = rf'(?:^|[\s\n])(CO\s*{unit_num}\s*[:\-–—].*?)(?=(?:[\s\n]CO\s*\d\s*[:\-–—])|$)'
    match = re.search(pattern, full_outcomes, re.IGNORECASE | re.DOTALL)
    if match:
        res = match.group(1).strip()
        res = re.sub(r'[ \t]+', ' ', res)
        return res.strip()
    
    # Match numbered 1. ... 2. ...
    num_pattern = rf'(?:^|[\s\n])({unit_num}[\.\)]\s*.*?)(?=(?:[\s\n]\d[\.\)])|$)'
    match_num = re.search(num_pattern, full_outcomes, re.IGNORECASE | re.DOTALL)
    if match_num and len(re.findall(r'(?:^|[\s\n])\d[\.\)]', full_outcomes)) > 1:
        res = match_num.group(1).strip()
        res = re.sub(r'[ \t]+', ' ', res)
        return res.strip()

    # If already a single CO
    if re.match(r'^CO\s*\d\s*[:\-–—]', full_outcomes.strip(), re.IGNORECASE):
        all_cos = re.findall(r'CO\s*\d\s*[:\-–—]', full_outcomes, re.IGNORECASE)
        if len(all_cos) <= 1:
            return full_outcomes.strip()
            
    return full_outcomes.strip()

@st.cache_data
def get_cached_css(file_path: str = "ui/style.css") -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f"<style>{f.read()}</style>"
    except FileNotFoundError:
        return ""

def load_css(file_path="ui/style.css"):
    css_content = get_cached_css(file_path)
    if css_content:
        st.markdown(css_content, unsafe_allow_html=True)

@st.cache_data(max_entries=600)
def get_base64_of_bin_file(bin_file: str) -> str:
    if bin_file and os.path.exists(bin_file):
        try:
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except Exception:
            return ""
    return ""

@st.cache_data(ttl=300)
def get_cached_departments_with_faculty(_db):
    return _db.get_all_departments_with_faculty()

@st.cache_data(ttl=300)
def get_cached_faculty(_db, department=None, search=None, is_guest=None, is_hod=None):
    return _db.get_faculty(
        department=department,
        search=search,
        is_guest=is_guest,
        is_hod=is_hod,
        is_active=1
    )

@st.cache_data(ttl=300)
def get_cached_notices(_db, notice_type=None, program=None, semester=None, active_only=True, limit=50):
    return _db.get_notices(
        notice_type=notice_type,
        program=program,
        semester=semester,
        active_only=active_only,
        limit=limit
    )

@st.cache_data(ttl=300)
def get_cached_latest_notice_date(_db):
    notices = _db.get_notices(limit=1)
    if notices and notices[0].get("published_date"):
        return notices[0]["published_date"]
    return None

@st.cache_data(ttl=300)
def get_cached_deadlines(_db):
    deadlines = []
    try:
        with _db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title, notice_type, published_date, attachment_urls, source_page, raw_text
                FROM notices 
                WHERE is_active = 1 AND (
                    notice_type IN ('fee notification', 'revaluation') OR 
                    raw_text LIKE '%last date%' OR 
                    raw_text LIKE '%deadline%'
                )
                ORDER BY published_date DESC
            """)
            for row in cursor.fetchall():
                deadlines.append(dict(row))
    except Exception:
        pass
    return deadlines

def _ensure_fresh_db(_db):
    if _db is None or not hasattr(_db, "get_syllabus_schemes") or not hasattr(_db, "get_subject_assistance_subjects"):
        try:
            import importlib
            import src.database
            importlib.reload(src.database)
            return src.database.DatabaseManager()
        except Exception:
            pass
    return _db

@st.cache_data(ttl=300)
def get_cached_syllabus_branches(_db):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_syllabus_branches"):
        branches = fresh_db.get_syllabus_branches()
        return [b for b in branches if b != "CST"]
    from src.faculty_parser import DEPARTMENT_CONFIGS
    return [d["short_code"] for d in DEPARTMENT_CONFIGS if d["short_code"] != "CST"]

@st.cache_data(ttl=300)
def get_cached_syllabus_schemes(_db, branch):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_syllabus_schemes"):
        return fresh_db.get_syllabus_schemes(branch)
    return ["2023", "2020"]

@st.cache_data(ttl=300)
def get_cached_syllabus_semesters(_db, branch, scheme=None):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_syllabus_semesters"):
        return fresh_db.get_syllabus_semesters(branch, scheme)
    return [1, 2, 3, 4, 5, 6, 7]

@st.cache_data(ttl=300)
def get_cached_syllabus_courses(_db, branch, semester, scheme=None):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_syllabus_courses"):
        return fresh_db.get_syllabus_courses(branch, semester, scheme=scheme)
    return []

@st.cache_data(ttl=300)
def get_cached_subject_assistance_subjects(_db, branch, semester, scheme=None):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_subject_assistance_subjects"):
        return fresh_db.get_subject_assistance_subjects(branch, semester, scheme=scheme)
    return []

@st.cache_data(ttl=300)
def get_cached_syllabus_units_for_course(_db, branch, semester, course_title, course_code=None):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_syllabus_units_for_course"):
        return fresh_db.get_syllabus_units_for_course(
            branch=branch,
            semester=semester,
            course_title=course_title,
            course_code=course_code
        )
    return []

@st.cache_data(ttl=300)
def get_cached_subject_notes(_db, branch, semester, course_title=None, unit_number=None):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_subject_notes"):
        return fresh_db.get_subject_notes(
            branch=branch,
            semester=semester,
            course_title=course_title,
            unit_number=unit_number
        )
    return []

@st.cache_data(ttl=300)
def get_cached_available_note_courses(_db, branch, semester):
    fresh_db = _ensure_fresh_db(_db)
    if hasattr(fresh_db, "get_available_note_courses_for_semester"):
        return fresh_db.get_available_note_courses_for_semester(branch, semester)
    return []

def render_pdf_preview_element(pdf_path: str, height: int = 650, note_key: str = ""):
    """Renders a 100% reliable document previewer using native image rendering (never blocked by Chrome)."""
    if not pdf_path or not os.path.exists(pdf_path):
        st.warning("⚠️ Document file not found on disk.")
        return

    try:
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
    except Exception as e:
        st.error(f"Failed to open PDF document: {e}")
        return

    if total_pages == 0:
        st.info("Document contains no renderable pages.")
        return

    key_safe = (note_key or os.path.basename(pdf_path)).replace(" ", "_").replace(".", "_").replace("-", "_")

    # Reader controls: View mode, resolution, total pages
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.6, 1.2, 1.2])
    with ctrl_col1:
        view_mode = st.radio(
            "View Mode",
            ["Single Page Reader", "Continuous Scroll (First 5 Pages)"],
            horizontal=True,
            key=f"vmode_{key_safe}"
        )
    with ctrl_col2:
        zoom_level = st.selectbox(
            "Quality / Zoom",
            ["Normal (130 DPI)", "High Definition (180 DPI)"],
            index=0,
            key=f"dpi_{key_safe}"
        )
        dpi = 180 if "High" in zoom_level else 130

    with ctrl_col3:
        st.markdown(f"<div style='margin-top:28px; font-weight:600; color:#334155; font-size:0.85rem;'>📑 <b>{total_pages} Total Pages</b></div>", unsafe_allow_html=True)

    if view_mode == "Single Page Reader":
        # Page Navigation Slider
        c_nav1, c_nav2 = st.columns([3, 1])
        with c_nav1:
            cur_page = st.slider(
                f"Page Navigation",
                min_value=1,
                max_value=total_pages,
                value=1,
                key=f"pdf_slider_{key_safe}"
            )
        with c_nav2:
            st.markdown(f"<div style='margin-top:28px; font-weight:600; color:#1e293b;'>📄 Page <b>{cur_page}</b> of <b>{total_pages}</b></div>", unsafe_allow_html=True)

        # Render current page
        try:
            page_obj = doc[cur_page - 1]
            pix = page_obj.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            st.image(
                img_bytes,
                caption=f"{os.path.basename(pdf_path)} - Page {cur_page} / {total_pages}",
                use_container_width=True
            )
        except Exception as err:
            st.error(f"Error displaying page {cur_page}: {err}")

    else:
        # Continuous Scroll (First 5 pages or all if <= 5)
        pages_to_show = min(5, total_pages)
        st.caption(f"Showing first {pages_to_show} pages sequentially. Use Single Page Reader or the Download button to view all {total_pages} pages.")
        for p_idx in range(pages_to_show):
            try:
                page_obj = doc[p_idx]
                pix = page_obj.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes("png")
                st.markdown(f"<div style='margin-top:14px; margin-bottom:4px; font-weight:600; color:#334155; font-size:0.85rem;'>📄 Page {p_idx + 1} of {total_pages}</div>", unsafe_allow_html=True)
                st.image(img_bytes, use_container_width=True)
            except Exception as err:
                st.error(f"Error displaying page {p_idx + 1}: {err}")

@st.cache_data(ttl=300)
def get_cached_academics_subjects(_db, branch, semester):
    try:
        with _db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT course_code, course_title, unit_number, topics, outcomes "
                "FROM syllabus WHERE (branch = ? OR (branch = 'COMMON' AND year = 1)) AND semester = ? "
                "ORDER BY course_code, unit_number", 
                (branch, semester)
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []

def format_date(date_str):
    if not date_str: return ""
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.split(".")[0])
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except Exception:
        return date_str

def render_html_block(html_content: str):
    """
    Renders HTML safely in Streamlit without CommonMark treating 
    indented lines or blank lines inside HTML as <pre><code> blocks.
    """
    clean_lines = [line.strip() for line in html_content.strip().splitlines() if line.strip()]
    st.markdown(" ".join(clean_lines), unsafe_allow_html=True)

def render_header():
    logo_base64 = get_base64_of_bin_file("gprec_logo1.png")
    img_html = f'<img src="data:image/png;base64,{logo_base64}" alt="GPREC Logo" class="college-logo">' if logo_base64 else ''
    
    render_html_block(f"""
        <div class="main-header">
            {img_html}
            <div class="header-text">
                <h1>AI Student Assistant</h1>
                <p>G. Pulla Reddy Engineering College (Autonomous)</p>
                <div class="badge-amber">Answers from official GPREC sources only</div>
            </div>
        </div>
    """)

def render_loading_skeleton(stage_text="Consulting official GPREC knowledge base & drafting response..."):
    """Render a modern skeleton shimmer loading card with a smooth spinner and stage indication."""
    render_html_block(f"""
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
                <span class="skeleton-footer-text">{stage_text}</span>
            </div>
        </div>
    """)

def _handle_quick_question(question):
    st.session_state.prompt_trigger = question

def quick_question_button(label, question):
    st.button(label, use_container_width=True, key=f"btn_{label}", on_click=_handle_quick_question, args=(question,))

def render_welcome_state():
    st.markdown("### How can I help you today?")
    st.markdown("Select a topic below or ask your own question.")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        quick_question_button("🎓 Admissions", "What is the admission process for B.Tech?")
        quick_question_button("📖 Library Rules", "What are the library timings and borrowing rules?")
    with c2:
        quick_question_button("💼 Placements", "What are the placement statistics for last year?")
        quick_question_button("💰 Tuition Fee", "What is the tuition fee structure for B.Tech?")
    with c3:
        quick_question_button("🏛️ CSE Facilities", "What are the facilities in the CSE department?")
        quick_question_button("📞 Contact Us", "How can I contact the college administration?")

def render_source_card(sources, confidence, is_recent_query=False, debug_mode=False, confidence_reason=""):
    if not sources:
        return
        
    st.markdown("<div class='answer-source-card'>", unsafe_allow_html=True)
    
    if is_recent_query:
        dates = [s.get("published_date") for s in sources if s.get("published_date")]
        if dates:
            latest_date = sorted(dates, reverse=True)[0]
            st.markdown(f"<span class='recent-tag'>Based on the most recent notice: {format_date(latest_date)}</span>", unsafe_allow_html=True)
            
    # Group by source_url
    grouped = {}
    for s in sources:
        url = s.get("source_url", "#")
        if url not in grouped:
            grouped[url] = {
                "title": s.get("title", "Document"),
                "date": s.get("published_date") or s.get("last_checked"),
                "date_label": "Published" if s.get("published_date") else "First seen",
                "pages": set(),
                "chunks": []
            }
        if s.get("page"):
            grouped[url]["pages"].add(str(s.get("page")))
        grouped[url]["chunks"].append(s.get("content", ""))
        
    # Limit to 3 sources
    unique_sources = list(grouped.items())[:3]
    
    hover_title = f"{confidence} confidence ({confidence_reason})" if confidence_reason else f"Retrieval confidence: {confidence}"
    st.markdown(f"<span class='confidence-{confidence.lower()}' title='{hover_title}' style='font-size:0.8rem; cursor:help;'>Confidence: {confidence}</span>", unsafe_allow_html=True)
    
    with st.expander(f"Sources ({len(unique_sources)}) ▾"):
        for url, data in unique_sources:
            title = data["title"]
            date_str = f"{data['date_label']}: {format_date(data['date'])}" if data["date"] else ""
            pages_str = f" | Page(s): {', '.join(sorted(data['pages']))}" if data["pages"] else ""
            
            st.markdown(f"<div class='source-item'><a href='{url}' target='_blank'><b>{title}</b></a> {('- ' + date_str) if date_str else ''}{pages_str}</div>", unsafe_allow_html=True)
            
            if debug_mode:
                st.markdown("**[Admin Debug] Raw Passages:**")
                for chunk in data["chunks"]:
                    clean_chunk = chunk[:300].replace('\n', ' ') + ('...' if len(chunk) > 300 else '')
                    st.caption(f"_{clean_chunk}_")
                st.divider()
    
    st.markdown("</div>", unsafe_allow_html=True)

def render_not_found(suggested_questions=None):
    render_html_block("""
        <div class="not-found-card" style="padding: 15px; border-left: 4px solid #f59e0b; background-color: #fffbeb; border-radius: 6px; margin-top: 10px; margin-bottom: 10px;">
            <h4 style="margin-top:0; color: #b45309; font-size:1.05rem;">Information Not Found</h4>
            <p style="margin-bottom:8px; color: #92400e; font-size:0.92rem;">I couldn't find this information in the available official GPREC sources. Please verify with the official notice board or the relevant department office.</p>
        </div>
    """)
    
def _handle_not_found_click(sug):
    st.session_state.prompt_trigger = sug

def render_not_found(suggested_questions=None):
    st.markdown("I couldn't find specific information about that in the official GPREC knowledge base.")
    suggestions = suggested_questions or [
        "What courses are offered at GPREC?",
        "What are the library timings and rules?",
        "Who is the head of the EEE department?"
    ]
    st.markdown("<p style='font-size:0.85rem; color:#6b7280; margin-bottom:4px;'>You can also ask:</p>", unsafe_allow_html=True)
    cols = st.columns(len(suggestions))
    for idx, (col, sug) in enumerate(zip(cols, suggestions)):
        with col:
            st.button(sug, key=f"not_found_sug_{idx}_{sug[:10]}", use_container_width=True, on_click=_handle_not_found_click, args=(sug,))

def _handle_clarify_click(opt, question):
    st.session_state.prompt_trigger = f"{opt} {question}"

def render_clarify(question, options, key_prefix="clarify"):
    render_html_block(f"""
        <div style="padding: 12px 16px; border-left: 4px solid #3b82f6; background-color: #eff6ff; border-radius: 6px; margin: 8px 0;">
            <b style="color: #1e40af;">{question}</b>
        </div>
    """)
    
    cols = st.columns(min(len(options), 6))
    for idx, opt in enumerate(options):
        col_idx = idx % len(cols)
        with cols[col_idx]:
            st.button(opt, key=f"{key_prefix}_{idx}_{opt}", use_container_width=True, on_click=_handle_clarify_click, args=(opt, question))


@st.fragment
def render_notices_fragment(db):
    latest_pub = get_cached_latest_notice_date(db)
    pub_display = format_date(latest_pub) if latest_pub else "October 2026"
    st.markdown(f"<div style='font-size:0.85rem; color:#64748b; margin-bottom:12px;'>📅 <b>Notice Board Last Checked:</b> {pub_display}</div>", unsafe_allow_html=True)

    # Search and Filter controls
    notice_search = st.text_input("🔍 Search notices", placeholder="Search notices by keyword, exam type, fee, circular...", key="notices_search_kw")

    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
    with c1:
        dept_options = ["All", "General", "CSE", "ECE", "EEE", "CE", "ME", "CSM", "H&S"]
        selected_dept = st.selectbox("Department", dept_options, key="notices_filter_dept")
    with c2:
        type_options = ["All", "timetable", "seating plan", "results", "revaluation", "hall ticket", "fee notification", "circular", "event"]
        selected_type = st.selectbox("Type", type_options, format_func=lambda x: x.title(), key="notices_filter_type")
    with c3:
        prog_options = ["All", "B.Tech", "M.Tech", "MBA", "MCA"]
        selected_prog = st.selectbox("Program", prog_options, key="notices_filter_prog")
    with c4:
        sem_options = ["All", "I Sem", "II Sem", "III Sem", "IV Sem", "V Sem", "VI Sem", "VII Sem", "VIII Sem"]
        selected_sem = st.selectbox("Semester", sem_options, key="notices_filter_sem")

    # Fetch notices from structured notices table using cached query
    notices = get_cached_notices(
        db,
        notice_type=selected_type if selected_type != "All" else None,
        program=selected_prog if selected_prog != "All" else None,
        semester=selected_sem if selected_sem != "All" else None,
        active_only=True,
        limit=50
    )

    # Apply department filter if not All
    if selected_dept != "All":
        notices = [n for n in notices if (n.get("department") or "General").upper() == selected_dept.upper()]

    # Apply keyword search filter if provided
    if notice_search and notice_search.strip():
        q_lower = notice_search.strip().lower()
        notices = [
            n for n in notices
            if q_lower in (n.get("title") or "").lower()
            or q_lower in (n.get("raw_text") or "").lower()
            or q_lower in (n.get("department") or "").lower()
            or q_lower in (n.get("notice_type") or "").lower()
        ]
    
    # Check if newest notice is >30 days old using cached query
    if latest_pub:
        try:
            from datetime import datetime
            latest_dt = datetime.strptime(latest_pub[:10], "%Y-%m-%d")
            days_old = (datetime.now() - latest_dt).days
            if days_old > 30:
                st.warning(f"⚠️ **Notice Board Notice:** The latest archived notice is {days_old} days old. Please consult the physical college notice board or [examcell.gprec.ac.in](http://examcell.gprec.ac.in/) for live announcements.")
        except Exception:
            pass

    if not notices:
        st.info("No notices found matching the selected filters. Please adjust the filters or search query.")
        return

    st.caption(f"Showing {len(notices)} notices (latest first):")

    type_colors = {
        "timetable": "#2563eb",
        "seating plan": "#7c3aed",
        "results": "#059669",
        "revaluation": "#d97706",
        "hall ticket": "#4f46e5",
        "fee notification": "#dc2626",
        "circular": "#4b5563",
        "event": "#0891b2"
    }

    for idx, notice in enumerate(notices):
        title = notice.get("title") or "College Notice"
        ntype = notice.get("notice_type") or "circular"
        prog = notice.get("program") or ""
        sem = notice.get("semester") or ""
        reg = notice.get("scheme_regulation") or ""
        dept = notice.get("department") or "General"
        deadline = notice.get("deadline_date")
        
        pub_raw = notice.get("published_date")
        if pub_raw:
            date_display = format_date(pub_raw)
        else:
            date_display = "Date not found"
            
        doc_url = notice.get("document_url") or notice.get("attachment_urls") or notice.get("source_page") or "https://www.gprec.ac.in"
        # If multiple comma-separated URLs in attachment_urls, take the first valid one
        if doc_url and "," in doc_url:
            doc_url = doc_url.split(",")[0].strip()
            
        raw_text = notice.get("raw_text") or ""
        badge_color = type_colors.get(ntype.lower(), "#4b5563")

        with st.container(border=True):
            st.markdown(f"#### {title}")
            
            # Tags row: Department tag, Notice type tag, Program/Semester tags, Date, Deadline
            tags_html = f"<span style='background-color:#EEF2FF; color:#4338CA; border:1px solid #C7D2FE; padding:3px 8px; border-radius:12px; font-size:0.78rem; font-weight:600;'>🏛️ {dept}</span> "
            tags_html += f"<span style='background-color:{badge_color}; color:white; padding:3px 8px; border-radius:12px; font-size:0.78rem; font-weight:600;'>{ntype.title()}</span>"
            if prog:
                tags_html += f" <span style='background-color:#E0E7FF; color:#3730A3; padding:3px 8px; border-radius:12px; font-size:0.78rem; font-weight:500;'>{prog}</span>"
            if sem:
                tags_html += f" <span style='background-color:#F3F4F6; color:#1F2937; padding:3px 8px; border-radius:12px; font-size:0.78rem;'>{sem}</span>"
            if reg:
                tags_html += f" <span style='background-color:#FEF3C7; color:#92400E; padding:3px 8px; border-radius:12px; font-size:0.78rem;'>{reg}</span>"
            
            # Date tag - shows formatted date or 'Date not found'
            tags_html += f" <span style='color:#4B5563; font-size:0.8rem; margin-left:8px; font-weight:500;'>📅 {date_display}</span>"
            
            if deadline:
                tags_html += f" <span style='background-color:#FEE2E2; color:#991B1B; border:1px solid #FCA5A5; padding:3px 8px; border-radius:12px; font-size:0.78rem; font-weight:600; margin-left:8px;'>⏳ Deadline: {deadline}</span>"
            
            st.markdown(tags_html, unsafe_allow_html=True)
            
            if raw_text and raw_text.strip() != title.strip():
                st.caption(raw_text[:250] + ('...' if len(raw_text) > 250 else ''))
                
            # 'Open document' button using st.link_button. Never show raw URLs as text.
            if doc_url:
                st.link_button("📄 Open document", doc_url, key=f"notice_btn_{notice.get('notice_id', idx)}")

def render_notices_page(db):
    st.title("📅 Latest Notices & Examination Updates")
    st.markdown("Official notices, exam timetables, fee circulars, and announcements from GPREC.")
    render_notices_fragment(db)

def render_deadlines_page(pipeline, db=None):
    st.title("⏳ Deadlines & Important Dates")
    st.markdown("Upcoming examination fee deadlines, revaluation last dates, and academic schedule deadlines.")
    
    st.markdown("<div style='font-size:0.85rem; color:#64748b; margin-bottom:12px;'>📅 <b>Deadlines Last Synchronized:</b> October 2026</div>", unsafe_allow_html=True)

    # Collect deadlines from both database notices and pipeline metadata
    deadlines = []
    
    if db is not None:
        deadlines = get_cached_deadlines(db)

    if not deadlines and pipeline:
        deadlines = [m for m in pipeline.vstore.metadata if m.get("category") == "Deadlines"]
    
    if not deadlines:
        st.info("No upcoming deadlines found in the knowledge base. Please check official notifications.")
        return
        
    dl_search_kw = st.text_input("🔍 Search deadlines", placeholder="Search by exam fee, revaluation, semester...", key="deadlines_search_input")
    dl_dept = st.selectbox("Filter by Department", ["All", "General", "CSE", "ECE", "EEE", "CE", "ME", "CSM", "H&S"], key="deadlines_dept_select")

    if dl_dept != "All":
        deadlines = [d for d in deadlines if (d.get("department") or "General").upper() == dl_dept.upper()]

    if dl_search_kw and dl_search_kw.strip():
        q_l = dl_search_kw.strip().lower()
        deadlines = [d for d in deadlines if q_l in (d.get("title") or "").lower() or q_l in (d.get("raw_text") or "").lower()]

    if not deadlines:
        st.info("No deadlines match your filter criteria.")
        return

    for idx, item in enumerate(deadlines):
        title = item.get("title", "Important Deadline")
        pub_date = item.get("published_date", "")
        formatted_pub = format_date(pub_date)
        raw_text = item.get("raw_text", "")
        att_url = (item.get("attachment_urls") or "").split(",")[0] if item.get("attachment_urls") else item.get("source_page", "#")
        
        # Calculate countdown or status if date present
        countdown_badge = ""
        import re
        date_match = re.search(r'(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})', raw_text)
        if date_match:
            try:
                from datetime import datetime
                from dateutil import parser as dp
                d_dt = dp.parse(date_match.group(1), fuzzy=True, dayfirst=True)
                days_left = (d_dt - datetime.now()).days
                if days_left >= 0:
                    countdown_badge = f"<span style='background-color:#DEF7EC; color:#03543F; padding:2px 8px; border-radius:10px; font-size:0.8rem; font-weight:600;'>⏳ {days_left} days remaining ({date_match.group(1)})</span>"
                else:
                    countdown_badge = f"<span style='background-color:#FDE8E8; color:#9B1C1C; padding:2px 8px; border-radius:10px; font-size:0.8rem;'>Closed on {date_match.group(1)}</span>"
            except Exception:
                pass

        with st.container(border=True):
            st.markdown(f"#### {title}")
            meta_line = ""
            if formatted_pub:
                meta_line += f"Published: {formatted_pub}  "
            if countdown_badge:
                meta_line += countdown_badge
            if meta_line:
                st.markdown(meta_line, unsafe_allow_html=True)
            if raw_text and raw_text != title:
                st.caption(raw_text[:180] + ('...' if len(raw_text) > 180 else ''))
            if att_url and att_url != "#":
                st.link_button("📄 Open document", att_url, key=f"dl_open_btn_{idx}")

def _handle_topic_question(q):
    st.session_state.prompt_trigger = q
    st.session_state.page = "Ask AI"
    st.session_state.nav_radio = "Ask AI"

def render_topic_page(title, intro, questions):
    st.title(title)
    st.markdown(intro)
    st.markdown("#### Ask a quick question:")
    for q in questions:
        st.button(q, use_container_width=True, key=f"topic_{title}_{q}", on_click=_handle_topic_question, args=(q,))

def render_academics_page(db):
    st.title("📚 Academics")
    st.markdown("View official syllabus scheme documents and course details for your branch and semester.")
    
    col1, col2 = st.columns(2)
    with col1:
        branch = st.selectbox("Select Branch", ["CSE", "ECE", "EEE", "CE", "ME", "CSM"])
    with col2:
        semester = st.selectbox("Select Semester", ["1", "2", "3", "4", "5", "6", "7", "8"])

    sem_int = int(semester) if semester.isdigit() else 1
    pdf_info = get_branch_latest_syllabus_info(branch, sem_int)
    if pdf_info and pdf_info.get("url"):
        st.link_button(
            f"📄 Open Official {branch} Syllabus PDF ({pdf_info['scheme']})",
            pdf_info["url"],
            help=f"Opens official GPREC {branch} syllabus document"
        )
    
    all_links = get_all_latest_syllabus_links_for_branch(branch)
    if all_links:
        with st.expander(f"📁 All Official Scheme Syllabi for {branch}"):
            for l in all_links:
                st.markdown(f"- [{l['title']}]({l['url']}) *(Scheme: {l.get('scheme', 'Official')})*")

    st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)
        
    if st.button("View Subjects"):
        rows = get_cached_academics_subjects(db, branch, semester)
            
        if not rows:
            st.info(f"No indexed subject breakdown found for {branch} Semester {semester}. You can still open the official syllabus PDF above!")
            return
            
        st.markdown(f"### {branch} - Semester {semester} Subjects")
        
        # Group by course
        courses = {}
        for row in rows:
            cc = row['course_code']
            if cc not in courses:
                courses[cc] = {
                    'title': row['course_title'],
                    'units': [],
                    'outcomes': row['outcomes']
                }
            courses[cc]['units'].append({
                'num': row['unit_number'],
                'topics': row['topics']
            })
            
        for cc, cdata in courses.items():
            with st.expander(f"{cc} - {cdata['title']}"):
                if cdata['units']:
                    st.markdown("#### Units")
                    for u in cdata['units']:
                        st.markdown(f"**Unit {u['num']}**: {u['topics']}")
                
                if cdata['outcomes']:
                    st.markdown("#### Course Outcomes")
                    st.markdown(cdata['outcomes'])

def _handle_doubt_click(d):
    st.session_state.doubt_prompt_trigger = d

@st.fragment
def render_subject_assistance_fragment(pipeline, db):
    db = _ensure_fresh_db(db)
    from src.faculty_parser import DEPARTMENT_CONFIGS
    
    all_dept_codes = [d["short_code"] for d in DEPARTMENT_CONFIGS]
    dept_name_map = {d["short_code"]: d["name"] for d in DEPARTMENT_CONFIGS}

    # 1. State preservation
    default_branch = "EEE" if "EEE" in all_dept_codes else ("CSE" if "CSE" in all_dept_codes else all_dept_codes[0])
    if "sub_assist_branch" not in st.session_state or st.session_state.sub_assist_branch not in all_dept_codes:
        st.session_state.sub_assist_branch = default_branch
    if "sub_assist_scheme" not in st.session_state:
        st.session_state.sub_assist_scheme = "2023"
    if "sub_assist_semester" not in st.session_state:
        st.session_state.sub_assist_semester = "3"
    if "sub_assist_custom_subject" not in st.session_state:
        st.session_state.sub_assist_custom_subject = ""
    if "subject_doubt_chats" not in st.session_state:
        st.session_state.subject_doubt_chats = {}
    if "doubt_prompt_trigger" not in st.session_state:
        st.session_state.doubt_prompt_trigger = None

    # 4 columns for selectors: Branch, Scheme, Semester, Subject
    col1, col2, col3, col4 = st.columns([1.3, 1.0, 0.9, 2.2])

    # 1. Branch Selector (All 10 departments) - Defaults to EEE
    with col1:
        cur_branch = st.session_state.sub_assist_branch
        b_idx = all_dept_codes.index(cur_branch) if cur_branch in all_dept_codes else all_dept_codes.index(default_branch)
        selected_branch = st.selectbox(
            "Branch",
            all_dept_codes,
            index=b_idx,
            format_func=lambda c: f"{c} - {dept_name_map.get(c, c)}",
            key="sub_assist_branch_selector"
        )
        st.session_state.sub_assist_branch = selected_branch

    # 2. Scheme Selector (from syllabus table, default to newest that has data)
    schemes_available = get_cached_syllabus_schemes(db, selected_branch)
    if not schemes_available:
        schemes_available = ["2023", "2020"]
    with col2:
        cur_scheme = st.session_state.sub_assist_scheme
        sch_idx = schemes_available.index(cur_scheme) if cur_scheme in schemes_available else 0
        selected_scheme = st.selectbox(
            "Scheme",
            schemes_available,
            index=sch_idx,
            format_func=lambda s: s if any(k in str(s).lower() for k in ("scheme", "r-", "r2")) else f"Scheme-{s}",
            key=f"sub_assist_scheme_selector_{selected_branch}"
        )
        st.session_state.sub_assist_scheme = selected_scheme

    # 3. Semester Selector (only semesters that have rows)
    sems_available = get_cached_syllabus_semesters(db, selected_branch, selected_scheme)
    if not sems_available:
        sems_available = [1, 2, 3, 4, 5, 6, 7]
    sem_str_list = [str(s) for s in sems_available]
    with col3:
        cur_sem = str(st.session_state.sub_assist_semester)
        sem_idx = sem_str_list.index(cur_sem) if cur_sem in sem_str_list else (0 if "1" in sem_str_list else 0)
        selected_sem = st.selectbox(
            "Semester",
            sem_str_list,
            index=sem_idx,
            key=f"sub_assist_sem_selector_{selected_branch}_{selected_scheme}"
        )
        st.session_state.sub_assist_semester = selected_sem

    sem_int = int(selected_sem) if selected_sem.isdigit() else 1

    # Show Note "Common for all branches" when Year 1 (Semester 1 or 2)
    if sem_int in (1, 2):
        st.info("ℹ️ Year 1 uses the common I B.Tech syllabus. (**Common for all branches**)")

    # 4. Subject Selector:
    # List subjects from timetable_subjects first (marked "[Running this semester]"),
    # then remaining subjects of that semester from syllabus. Last option: "Other subject (type the name)"
    combined_subjects = get_cached_subject_assistance_subjects(db, selected_branch, sem_int, selected_scheme)

    resolved_title = ""
    resolved_code = ""
    resolved_credits = ""
    resolved_ltp = ""
    resolved_url = ""
    resolved_regulation = selected_scheme
    is_running_subject = False
    is_custom_subject = False
    subject_needs_review = 0

    with col4:
        if combined_subjects:
            subject_options = [s["display_label"] for s in combined_subjects]
            subject_options.append("Other subject (type the name)")

            selected_subj_opt = st.selectbox(
                "Subject",
                subject_options,
                key=f"sub_assist_subject_selector_{selected_branch}_{selected_scheme}_{selected_sem}"
            )

            if selected_subj_opt == "Other subject (type the name)":
                is_custom_subject = True
                custom_name = st.text_input(
                    "Type subject name",
                    value=st.session_state.sub_assist_custom_subject,
                    placeholder=f"e.g. {selected_branch} subject name",
                    key=f"sub_assist_custom_subject_input_{selected_branch}_{selected_scheme}_{selected_sem}"
                )
                st.session_state.sub_assist_custom_subject = custom_name
                resolved_title = custom_name.strip() if custom_name.strip() else f"Custom {selected_branch} Subject"
                resolved_code = "OTHER"
            else:
                matched_idx = subject_options.index(selected_subj_opt)
                matched_subj = combined_subjects[matched_idx]
                resolved_title = matched_subj["course_title"]
                resolved_code = matched_subj.get("course_code") or ""
                resolved_credits = matched_subj.get("credits") or ""
                resolved_ltp = matched_subj.get("ltp") or ""
                resolved_url = matched_subj.get("document_url") or ""
                resolved_regulation = matched_subj.get("regulation") or selected_scheme
                is_running_subject = matched_subj.get("is_running", False)
                subject_needs_review = matched_subj.get("needs_review", 0)
        else:
            # If a combination has no data, show a short message and the type-the-name option. Never show an empty page.
            is_custom_subject = True
            st.info("No indexed subjects found for this selection — type your subject name to proceed.")
            custom_name = st.text_input(
                "Type subject name",
                value=st.session_state.sub_assist_custom_subject,
                placeholder=f"e.g. {selected_branch} Sem {selected_sem} Subject",
                key=f"sub_assist_custom_input_empty_{selected_branch}_{selected_scheme}_{selected_sem}"
            )
            st.session_state.sub_assist_custom_subject = custom_name
            resolved_title = custom_name.strip() if custom_name.strip() else f"{selected_branch} Sem {selected_sem} Subject"
            resolved_code = "CUSTOM"

    # Fetch units for this subject if in DB
    units_data = []
    if not is_custom_subject and resolved_title:
        units_data = get_cached_syllabus_units_for_course(
            db,
            branch=selected_branch,
            semester=sem_int,
            course_title=resolved_title,
            course_code=resolved_code if resolved_code not in ("OTHER", "CUSTOM", "") else None
        )

        if units_data:
            if not resolved_url and units_data[0].get("document_url"):
                resolved_url = units_data[0]["document_url"]
            if not resolved_credits and units_data[0].get("credits"):
                resolved_credits = units_data[0]["credits"]
            if not resolved_ltp and units_data[0].get("ltp"):
                resolved_ltp = units_data[0]["ltp"]
            if not resolved_regulation and units_data[0].get("regulation"):
                resolved_regulation = units_data[0]["regulation"]

    # Subject Key for separate message history and caching
    subject_key = f"{selected_branch}_{selected_scheme}_s{selected_sem}_{resolved_code}_{resolved_title}".replace(" ", "_")

    # Fetch notes for this subject
    subject_notes = []
    if db and resolved_title:
        subject_notes = get_cached_subject_notes(db, selected_branch, sem_int, course_title=resolved_title)

    # Render Compact Subject Header Card
    badges = []
    if is_running_subject:
        badges.append('<span class="badge-running">⚡ Running this semester</span>')
    if resolved_code and resolved_code not in ("OTHER", "CUSTOM"):
        badges.append(f'<span class="badge-code">{resolved_code}</span>')
    if resolved_credits and str(resolved_credits).strip().lower() not in ("none", "", "0"):
        badges.append(f'<span class="badge-credit">Credits: {resolved_credits}</span>')
    if resolved_ltp and str(resolved_ltp).strip().lower() not in ("none", ""):
        badges.append(f'<span class="badge-ltp">L-T-P: {resolved_ltp}</span>')
    if subject_notes:
        badges.append(f'<span class="badge-notes-count">📑 {len(subject_notes)} Notes Available</span>')
    
    reg_label = resolved_regulation if any(k in str(resolved_regulation).lower() for k in ("scheme", "r-", "r2")) else f"Scheme-{resolved_regulation}"
    badges.append(f'<span class="badge-credit">{reg_label}</span>')
    badges_html = "".join(badges)

    if units_data:
        unit_badge_text = f"📚 {len(units_data)} Units Indexed"
    elif is_running_subject:
        unit_badge_text = "⚡ Running Course (Timetable)"
    else:
        unit_badge_text = "✍️ Custom Subject"

    notes_sub_text = f"<span>•</span><span>📑 <b>{len(subject_notes)}</b> Notes & Materials</span>" if subject_notes else ""
    
    render_html_block(f"""
        <div class="subject-header-card">
            <div class="subject-header-top">
                <div class="subject-header-title">{resolved_title}</div>
                <div class="subject-header-badges">
                    {badges_html}
                </div>
            </div>
            <div class="subject-header-sub">
                <span>🏛️ Branch: <b>{selected_branch}</b></span>
                <span>•</span>
                <span>📜 Scheme: <b>{reg_label}</b></span>
                <span>•</span>
                <span>📅 Semester: <b>{selected_sem}</b></span>
                <span>•</span>
                <span>{unit_badge_text}</span>
                {notes_sub_text}
            </div>
        </div>
    """)

    # 3. Six Tabs
    tab_doubt, tab_syllabus, tab_notes, tab_explain, tab_practice, tab_revision = st.tabs([
        "💬 Ask a Doubt",
        "📖 Syllabus",
        "📑 Notes & Materials",
        "💡 Explain a Topic",
        "✍️ Practice",
        "⚡ Quick Revision"
    ])

    # -------------------------------------------------------------
    # TAB A: Ask a Doubt
    # -------------------------------------------------------------
    with tab_doubt:
        # Separate message history per subject
        history = st.session_state.subject_doubt_chats.setdefault(subject_key, [])

        chat_container = st.container()

        active_doubt = st.session_state.doubt_prompt_trigger
        if st.session_state.doubt_prompt_trigger:
            st.session_state.doubt_prompt_trigger = None

        # Chat Input at bottom of the tab
        doubt_input_val = st.chat_input(f"Ask a doubt about {resolved_title}...", key=f"doubt_input_{subject_key}")
        if doubt_input_val:
            active_doubt = doubt_input_val

        # Container for chat messages above the input
        with chat_container:
            # If chat is empty and no doubt is being answered right now, show 3 example doubts
            first_topics = units_data[0].get("topics", "") if units_data else ""
            example_doubts = generate_example_doubts(resolved_title, first_topics)

            if not history and not active_doubt:
                st.markdown("<p style='font-size:0.88rem; color:var(--slate-600); margin-bottom:0.5rem;'>💡 <b>Example doubts for this subject:</b></p>", unsafe_allow_html=True)
                cols = st.columns(len(example_doubts))
                for i, d in enumerate(example_doubts):
                    with cols[i]:
                        st.button(d, key=f"ex_doubt_{subject_key}_{i}", use_container_width=True, on_click=_handle_doubt_click, args=(d,))
                st.markdown("---")

            # Display all previous conversation messages (rendered exactly once)
            for msg in history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # Process active query (single turn, renders once and appends to history)
            if active_doubt:
                from app import check_rate_limit, record_question_timestamp
                allowed, limit_msg = check_rate_limit()
                if not allowed:
                    st.warning(limit_msg)
                else:
                    record_question_timestamp()
                    history.append({"role": "user", "content": active_doubt})
                    with st.chat_message("user"):
                        st.markdown(active_doubt)
                    with st.chat_message("assistant"):
                        with st.spinner("Preparing your explanation..."):
                            client = getattr(pipeline, "client", None)
                            model_name = getattr(pipeline, "model_name", None)
                            ans = answer_subject_doubt(
                                active_doubt,
                                resolved_title,
                                units_data=units_data,
                                history=history[:-1],
                                client=client,
                                model_name=model_name,
                                db=db,
                                branch=selected_branch,
                                scheme=selected_scheme
                            )
                        st.markdown(ans)
                    history.append({"role": "assistant", "content": ans})
                    if db:
                        db.log_chat(query=active_doubt, response=ans, response_type="SUBJECT_ASSIST", confidence="High")

            # Option to clear conversation for this subject
            if history:
                st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
                col_c1, col_c2 = st.columns([4, 1])
                with col_c2:
                    if st.button("🗑️ Clear chat", key=f"clear_doubt_{subject_key}", use_container_width=True):
                        st.session_state.subject_doubt_chats[subject_key] = []
                        st.rerun(scope="fragment")

    # -------------------------------------------------------------
    # TAB B: Syllabus
    # -------------------------------------------------------------
    with tab_syllabus:
        authoritative_pdf = get_branch_latest_syllabus_pdf(selected_branch, sem_int)
        authoritative_info = get_branch_latest_syllabus_info(selected_branch, sem_int)
        
        pdf_to_open = resolved_url or authoritative_pdf
        if not pdf_to_open or is_cross_branch_url(pdf_to_open, selected_branch):
            pdf_to_open = authoritative_pdf

        if pdf_to_open:
            scheme_label = authoritative_info["scheme"] if authoritative_info else "Latest Scheme"
            st.link_button(
                f"📄 Open Official {selected_branch} Syllabus PDF ({scheme_label})",
                pdf_to_open,
                help=f"Opens official GPREC {selected_branch} syllabus document"
            )
            st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)

        # Show credits and LTP if available
        if resolved_credits or resolved_ltp:
            meta_items = []
            if resolved_credits and str(resolved_credits).strip().lower() not in ("none", "", "0"):
                meta_items.append(f"**Credits:** {resolved_credits}")
            if resolved_ltp and str(resolved_ltp).strip().lower() not in ("none", ""):
                meta_items.append(f"**L-T-P:** {resolved_ltp}")
            if meta_items:
                st.markdown(" • ".join(meta_items))
                st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

        branch_all_links = get_all_latest_syllabus_links_for_branch(selected_branch)
        if branch_all_links:
            with st.expander(f"📁 More Official Syllabi for {selected_branch}"):
                for l in branch_all_links:
                    if l.get("url") != pdf_to_open:
                        st.markdown(f"- [{l['title']}]({l['url']}) *(Scheme: {l.get('scheme', 'Official')})*")
            st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)

        if units_data:
            for u in units_data:
                unit_num = u.get("unit_number", "")
                unit_title = u.get("unit_title", "")
                topics = u.get("topics", "")
                textbooks = u.get("textbooks", "")
                outcomes = u.get("outcomes", "")
                needs_rev = u.get("needs_review", 0)

                # Check for unit-specific notes
                unit_int = None
                try:
                    unit_int = int(unit_num)
                except (ValueError, TypeError):
                    pass

                unit_notes = [n for n in subject_notes if n.get("unit_number") == unit_int] if unit_int is not None else []
                unit_header = f"Unit {unit_num}: {unit_title}"
                if unit_notes:
                    unit_header += f"  (📑 {len(unit_notes)} Notes)"

                with st.expander(unit_header, expanded=True):
                    if needs_rev == 1:
                        st.markdown("<div style='background-color:#fffbeb; color:#b45309; border:1px solid #fcd34d; border-radius:6px; padding:6px 10px; font-size:0.8rem; margin-bottom:8px;'>⚠️ Check this against the official syllabus</div>", unsafe_allow_html=True)
                    st.markdown(f"**Topics:**\n\n{topics}")
                    if textbooks:
                        st.markdown(f"**Textbooks / References:**\n\n{textbooks}")
                    unit_co = extract_unit_outcome(outcomes, unit_num)
                    if unit_co:
                        st.markdown(f"**Course Outcomes (CO):**\n\n{unit_co}")

                    if unit_notes:
                        st.markdown("---")
                        st.markdown(f"##### 📑 Unit {unit_num} Study Materials & Notes ({len(unit_notes)}):")
                        for unote in unit_notes:
                            c_u1, c_u2 = st.columns([3, 1])
                            with c_u1:
                                badge_bg = "#e0f2fe" if unote.get("file_type") == "pdf" else "#fef3c7"
                                badge_fg = "#0369a1" if unote.get("file_type") == "pdf" else "#92400e"
                                st.markdown(
                                    f"📄 **{unote['title']}** "
                                    f"<span style='background:{badge_bg}; color:{badge_fg}; padding:2px 6px; border-radius:4px; font-size:0.75rem; font-weight:600;'>{unote.get('file_type', 'pdf').upper()}</span> "
                                    f"<span style='color:#64748b; font-size:0.8rem;'>({unote.get('formatted_size', '')})</span><br>"
                                    f"<span style='color:#64748b; font-size:0.8rem;'>Category: {unote.get('category', 'Lecture Notes')}</span>",
                                    unsafe_allow_html=True
                                )
                            with c_u2:
                                fp = unote.get("abs_filepath")
                                if fp and os.path.exists(fp):
                                    with open(fp, "rb") as f_obj:
                                        u_bytes = f_obj.read()
                                    st.download_button(
                                        label="⬇️ Download",
                                        data=u_bytes,
                                        file_name=unote["filename"],
                                        mime="application/pdf" if unote.get("file_type") == "pdf" else "application/octet-stream",
                                        key=f"dl_syl_note_{unote['id']}_{unit_num}",
                                        use_container_width=True
                                    )

                            fp = unote.get("abs_filepath")
                            if fp and os.path.exists(fp):
                                is_pdf = (unote.get("file_type") or "").lower() == "pdf"
                                with st.expander(f"👁️ Preview: {unote['filename']}", expanded=False):
                                    if is_pdf:
                                        render_pdf_preview_element(fp, height=550, note_key=f"syl_note_{unote['id']}_{unit_num}")
                                    else:
                                        st.info(f"📄 Word document format (`.{unote.get('file_type', 'doc')}`). Please use the **⬇️ Download** button above to open.")
        else:
            st.info(f"Detailed unit breakdown for '{resolved_title}' is not currently indexed in the syllabus table. You can still use the **Notes & Materials**, **Explain a Topic**, **Practice**, and **Ask a Doubt** tabs!")

    # -------------------------------------------------------------
    # TAB C: Notes & Materials
    # -------------------------------------------------------------
    with tab_notes:
        st.markdown(f"#### 📑 Official Lecture Notes & Study Materials")
        st.markdown(f"Access and download course notes, unit modules, question banks, and reference materials for **{resolved_title}**.")

        if subject_notes:
            # Top summary box
            total_size_mb = sum(n.get("file_size", 0) for n in subject_notes) / (1024 * 1024)
            st.markdown(
                f"<div style='background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 14px; margin-bottom:14px; display:flex; gap:16px; flex-wrap:wrap; font-size:0.88rem;'>"
                f"<span>📚 <b>Total Notes:</b> {len(subject_notes)} files</span>"
                f"<span>•</span>"
                f"<span>💾 <b>Total Size:</b> {total_size_mb:.1f} MB</span>"
                f"<span>•</span>"
                f"<span>🏛️ <b>Department:</b> {selected_branch} Semester {selected_sem}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Filter controls: Unit, Category, Search
            f_col1, f_col2, f_col3 = st.columns([1.2, 1.3, 1.5])

            available_units = sorted(list(set(n["unit_number"] for n in subject_notes if n.get("unit_number") is not None)))
            unit_filter_options = ["All Units"] + [f"Unit {u}" for u in available_units]
            if any(n.get("unit_number") is None for n in subject_notes):
                unit_filter_options.append("General / Other")

            available_cats = sorted(list(set(n["category"] for n in subject_notes if n.get("category"))))
            cat_filter_options = ["All Categories"] + available_cats

            with f_col1:
                sel_unit_f = st.selectbox("Filter by Unit", unit_filter_options, key=f"notes_filter_unit_{subject_key}")
            with f_col2:
                sel_cat_f = st.selectbox("Filter by Category", cat_filter_options, key=f"notes_filter_cat_{subject_key}")
            with f_col3:
                notes_search_kw = st.text_input("🔍 Search notes", placeholder="Search filename or topic...", key=f"notes_search_kw_{subject_key}")

            # Apply filters
            filtered_notes = subject_notes
            if sel_unit_f != "All Units":
                if sel_unit_f == "General / Other":
                    filtered_notes = [n for n in filtered_notes if n.get("unit_number") is None]
                else:
                    u_target = int(sel_unit_f.replace("Unit ", "").strip())
                    filtered_notes = [n for n in filtered_notes if n.get("unit_number") == u_target]

            if sel_cat_f != "All Categories":
                filtered_notes = [n for n in filtered_notes if n.get("category") == sel_cat_f]

            if notes_search_kw and notes_search_kw.strip():
                kw_lower = notes_search_kw.strip().lower()
                filtered_notes = [
                    n for n in filtered_notes 
                    if kw_lower in n.get("title", "").lower() 
                    or kw_lower in n.get("filename", "").lower()
                    or kw_lower in n.get("description", "").lower()
                ]

            st.caption(f"Showing {len(filtered_notes)} of {len(subject_notes)} files:")

            if not filtered_notes:
                st.info("No notes match your selected filters. Try choosing 'All Units' or 'All Categories'.")
            else:
                for note in filtered_notes:
                    with st.container(border=True):
                        fp = note.get("abs_filepath")
                        file_exists = fp and os.path.exists(fp)
                        is_pdf = (note.get("file_type") or "").lower() == "pdf"

                        # Extract page count if PDF
                        page_count = None
                        if is_pdf and file_exists:
                            try:
                                import fitz
                                with fitz.open(fp) as doc:
                                    page_count = len(doc)
                            except Exception:
                                pass

                        c_card_info, c_card_dl = st.columns([3.5, 1.2])
                        with c_card_info:
                            unit_label = f"Unit {note['unit_number']}" if note.get('unit_number') else "General / Reference"
                            badge_unit_color = "#2563eb" if note.get('unit_number') else "#64748b"
                            cat_name = note.get('category', 'Study Material')
                            pages_badge = f"<span style='background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:600;'>📑 {page_count} Pages</span> " if page_count else ""

                            st.markdown(f"##### 📄 {note['title']}")

                            badges_line = (
                                f"<span style='background:#eff6ff; color:{badge_unit_color}; border:1px solid #bfdbfe; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:600;'>{unit_label}</span> "
                                f"<span style='background:#f1f5f9; color:#334155; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:500;'>{cat_name}</span> "
                                f"<span style='background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:12px; font-size:0.78rem; font-weight:600;'>{note.get('file_type', 'pdf').upper()} • {note.get('formatted_size', '')}</span> "
                                f"{pages_badge}"
                            )
                            st.markdown(badges_line, unsafe_allow_html=True)

                            if note.get("description") and note["description"] != note["title"]:
                                st.caption(f"📁 {note['description']}")

                        with c_card_dl:
                            if file_exists:
                                with open(fp, "rb") as f_obj:
                                    note_bytes = f_obj.read()
                                st.download_button(
                                    label="⬇️ Download",
                                    data=note_bytes,
                                    file_name=note["filename"],
                                    mime="application/pdf" if is_pdf else "application/octet-stream",
                                    key=f"dl_tab_note_{note['id']}",
                                    use_container_width=True
                                )
                            else:
                                st.caption("⚠️ File missing")

                        # On-demand Document Preview Expander
                        if file_exists:
                            expander_label = f"👁️ Preview PDF Document: {note['filename']}" if is_pdf else f"👁️ Document Details: {note['filename']}"
                            with st.expander(expander_label, expanded=False):
                                if is_pdf:
                                    render_pdf_preview_element(fp, height=650, note_key=f"tab_note_{note['id']}")
                                else:
                                    st.info(f"📄 **{note['filename']}** is a Word document format (`.{note.get('file_type', 'doc')}`). Browsers cannot preview Word documents natively. Please click the **⬇️ Download** button above to open it in Microsoft Word, LibreOffice, or Google Docs.")
        else:
            st.info(f"ℹ️ No dedicated lecture notes or materials are currently indexed for **{resolved_title}** in **{selected_branch} Semester {selected_sem}**.")

            if db:
                available_courses = get_cached_available_note_courses(db, selected_branch, sem_int)
                if available_courses:
                    st.markdown(f"#### 📚 Available Notes in {selected_branch} Semester {selected_sem}:")
                    st.markdown("Notes are available for the following subjects in this semester. You can select them from the Subject dropdown above:")
                    for ac in available_courses:
                        tot_mb = (ac.get('total_size', 0) or 0) / (1024 * 1024)
                        with st.container(border=True):
                            c_a1, c_a2 = st.columns([3, 1])
                            with c_a1:
                                st.markdown(f"**{ac['course_title']}**")
                                st.caption(f"📁 Folder: `{ac['subject_folder']}` | Categories: {ac.get('categories', 'Notes')}")
                            with c_a2:
                                st.markdown(f"📄 **{ac['note_count']} files** (`{tot_mb:.1f} MB`)")

    # -------------------------------------------------------------
    # TAB C: Explain a Topic
    # -------------------------------------------------------------
    with tab_explain:
        st.markdown("Select a unit and topic from the syllabus or enter any sub-concept for a thorough, step-by-step breakdown.")

        if units_data:
            unit_choices = [f"Unit {u.get('unit_number')}: {u.get('unit_title')}" for u in units_data]
            chosen_unit_str = st.selectbox("Select Unit", unit_choices, key=f"explain_unit_sel_{subject_key}")
            chosen_u_obj = next((u for u in units_data if f"Unit {u.get('unit_number')}: {u.get('unit_title')}" == chosen_unit_str), units_data[0])
            parsed_topics = split_topics(chosen_u_obj.get("topics", ""))
            if parsed_topics:
                chosen_topic_sel = st.selectbox("Select Topic from Syllabus", parsed_topics, key=f"explain_topic_sel_{subject_key}")
            else:
                chosen_topic_sel = chosen_u_obj.get("unit_title", "General Concepts")
        else:
            chosen_unit_str = "Unit 1: Fundamentals"
            chosen_topic_sel = "Core Principles"

        custom_topic_txt = st.text_input(
            "Free text topic or specific sub-question (optional):",
            placeholder="e.g. Infix to postfix conversion, or normal forms in DBMS",
            key=f"explain_free_text_{subject_key}"
        )

        effective_topic = custom_topic_txt.strip() if custom_topic_txt.strip() else chosen_topic_sel

        explain_btn = st.button("Explain Topic", type="primary", key=f"explain_submit_btn_{subject_key}")

        cache_key_exp = get_subject_cache_key(
            resolved_title, chosen_unit_str, effective_topic, "explain",
            branch=selected_branch, scheme=selected_scheme
        )
        cached_exp = db.get_cached_answer(cache_key_exp)

        explanation_content = None
        if explain_btn:
            with st.status("Preparing your explanation...", expanded=False):
                sys_p, usr_p = build_topic_explanation_prompt(
                    resolved_title,
                    chosen_unit_str,
                    effective_topic,
                    user_notes=custom_topic_txt.strip() or None
                )
                client = getattr(pipeline, "client", None)
                model_name = getattr(pipeline, "model_name", None)
                raw_exp = call_subject_llm(sys_p, usr_p, client=client, model_name=model_name)
                explanation_content = clean_subject_response(raw_exp)
                if VERIFICATION_LINE.lower() not in explanation_content.lower():
                    explanation_content = f"{explanation_content.rstrip()}\n\n{VERIFICATION_LINE}"
                db.set_cached_answer(cache_key_exp, {
                    "answer": explanation_content,
                    "response_type": "ANSWERED",
                    "subject": resolved_title
                })
        elif cached_exp and cached_exp.get("answer"):
            explanation_content = clean_subject_response(cached_exp["answer"])

        if explanation_content:
            st.markdown(explanation_content)

    # -------------------------------------------------------------
    # TAB D: Practice
    # -------------------------------------------------------------
    with tab_practice:
        st.markdown(f'<span class="practice-disclaimer-badge">ℹ️ {PRACTICE_DISCLAIMER}</span>', unsafe_allow_html=True)

        col_p1, col_p2, col_p3 = st.columns([2, 1, 1])
        with col_p1:
            if units_data:
                unit_prac_choices = [f"Unit {u.get('unit_number')}: {u.get('unit_title')}" for u in units_data] + ["All Units"]
            else:
                unit_prac_choices = ["Unit 1", "All Units"]
            prac_unit = st.selectbox("Choose Unit", unit_prac_choices, key=f"prac_unit_{subject_key}")
        with col_p2:
            prac_count = st.slider("Number of Questions", min_value=3, max_value=10, value=5, key=f"prac_count_{subject_key}")
        with col_p3:
            prac_type = st.radio("Question Type", ["Multiple Choice", "Short Answer"], key=f"prac_type_{subject_key}")

        col_pbtn1, col_pbtn2 = st.columns([1, 1])
        with col_pbtn1:
            generate_prac_btn = st.button("Generate Practice Questions", type="primary", key=f"prac_btn_{subject_key}")
        with col_pbtn2:
            regenerate_prac_btn = st.button("🔄 Generate Different Questions", key=f"prac_regen_btn_{subject_key}")

        cache_key_prac = get_subject_cache_key(
            resolved_title, prac_unit, f"{prac_count}_{prac_type}", "practice",
            branch=selected_branch, scheme=selected_scheme
        )
        cached_prac = db.get_cached_answer(cache_key_prac)

        def _resolve_unit_topics():
            sel_top = ""
            if prac_unit == "All Units":
                if units_data:
                    sel_top = "; ".join(u.get("topics", "") for u in units_data if u.get("topics"))
                if not sel_top and db:
                    u_db = db.get_syllabus_units_for_course(selected_branch, selected_semester, resolved_title)
                    if u_db:
                        sel_top = "; ".join(u.get("topics", "") for u in u_db if u.get("topics"))
            else:
                if units_data:
                    matched = next((u for u in units_data if f"Unit {u.get('unit_number')}: {u.get('unit_title')}" == prac_unit or str(u.get("unit_number")) in str(prac_unit)), None)
                    if matched:
                        sel_top = matched.get("topics", "")
                if not sel_top and db:
                    u_db = db.get_syllabus_units_for_course(selected_branch, selected_semester, resolved_title)
                    if u_db:
                        matched = next((u for u in u_db if f"Unit {u.get('unit_number')}: {u.get('unit_title')}" == prac_unit or str(u.get("unit_number")) in str(prac_unit)), None)
                        if matched:
                            sel_top = matched.get("topics", "")
            return sel_top

        prac_content = None
        should_generate_fresh = generate_prac_btn or regenerate_prac_btn
        if should_generate_fresh:
            status_msg = "Generating different practice questions..." if regenerate_prac_btn else "Preparing your practice questions..."
            with st.status(status_msg, expanded=False):
                # Update quiz version to reset radio buttons
                st.session_state[f"quiz_ver_{cache_key_prac}"] = st.session_state.get(f"quiz_ver_{cache_key_prac}", 0) + 1
                random_seed = int(time.time() * 1000) % 1000000

                sel_topics = _resolve_unit_topics()
                sys_p, usr_p = build_practice_prompt(resolved_title, prac_unit, prac_count, prac_type, unit_topics=sel_topics, seed=random_seed)
                client = getattr(pipeline, "client", None)
                model_name = getattr(pipeline, "model_name", None)
                raw_prac = call_subject_llm(sys_p, usr_p, client=client, model_name=model_name, max_tokens=3500)
                prac_content = clean_subject_response(raw_prac)
                if VERIFICATION_LINE.lower() not in prac_content.lower():
                    prac_content = f"{prac_content.rstrip()}\n\n{VERIFICATION_LINE}"

                # Ensure valid question content exists before caching
                if "multiple choice" in prac_type.lower():
                    mcqs = extract_mcq_json(prac_content)
                    if not mcqs:
                        # Fallback to subject-aware generator with seed for fresh questions
                        mcqs = generate_subject_mcqs(resolved_title, prac_unit, sel_topics, prac_count, seed=random_seed)
                        prac_content = f"```json\n{json.dumps(mcqs, indent=2)}\n```\n\n{VERIFICATION_LINE}"
                else:
                    if not prac_content or "### Question" not in prac_content:
                        prac_content = generate_subject_short_answers(resolved_title, prac_unit, sel_topics, prac_count, seed=random_seed)

                db.set_cached_answer(cache_key_prac, {
                    "answer": prac_content,
                    "response_type": "ANSWERED",
                    "subject": resolved_title
                })
        elif cached_prac and cached_prac.get("answer"):
            cand_ans = clean_subject_response(cached_prac["answer"])
            if "multiple choice" in prac_type.lower():
                # Verify that cached answer contains valid MCQs and not an unparsed reasoning trace
                if extract_mcq_json(cand_ans):
                    prac_content = cand_ans
                else:
                    # Invalidate bad cache and generate clean subject MCQs
                    sel_topics = _resolve_unit_topics()
                    mcqs = generate_subject_mcqs(resolved_title, prac_unit, sel_topics, prac_count)
                    prac_content = f"```json\n{json.dumps(mcqs, indent=2)}\n```\n\n{VERIFICATION_LINE}"
                    db.set_cached_answer(cache_key_prac, {
                        "answer": prac_content,
                        "response_type": "ANSWERED",
                        "subject": resolved_title
                    })
            else:
                if not cand_ans or "### Question" not in cand_ans:
                    sel_topics = _resolve_unit_topics()
                    prac_content = generate_subject_short_answers(resolved_title, prac_unit, sel_topics, prac_count)
                    db.set_cached_answer(cache_key_prac, {
                        "answer": prac_content,
                        "response_type": "ANSWERED",
                        "subject": resolved_title
                    })
                else:
                    prac_content = cand_ans

        if prac_content:
            # Render Practice Content
            if "multiple choice" in prac_type.lower():
                mcq_list = extract_mcq_json(prac_content)
                if not mcq_list:
                    # Safety fallback to ensure student always gets interactive radio buttons
                    sel_topics = _resolve_unit_topics()
                    mcq_list = generate_subject_mcqs(resolved_title, prac_unit, sel_topics, prac_count)

                if mcq_list and isinstance(mcq_list, list):
                    q_ver = st.session_state.get(f"quiz_ver_{cache_key_prac}", 0)
                    for idx, q in enumerate(mcq_list):
                        q_num = q.get("question_number", idx + 1)
                        q_text = q.get("question", "")
                        options = q.get("options", {})
                        correct_opt = str(q.get("correct_option", "")).strip().upper()
                        explanation = q.get("explanation", "")

                        st.markdown(f"**Q{q_num}: {q_text}**")
                        opt_keys = list(options.keys())
                        opt_display = [f"{k}: {options[k]}" for k in opt_keys]

                        chosen = st.radio(
                            f"Select answer for Q{q_num}:",
                            opt_display,
                            index=None,
                            key=f"mcq_radio_{cache_key_prac}_{q_ver}_{idx}",
                            label_visibility="collapsed"
                        )

                        if chosen:
                            chosen_key = chosen.split(":")[0].strip().upper()
                            if chosen_key == correct_opt:
                                st.markdown(f'<div class="mcq-feedback-correct">✅ <b>Correct!</b> Option {chosen_key} is right.<br><b>Explanation:</b> {explanation}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div class="mcq-feedback-incorrect">❌ <b>Incorrect.</b> You selected {chosen_key}. The correct answer is <b>Option {correct_opt}</b>.<br><b>Explanation:</b> {explanation}</div>', unsafe_allow_html=True)
                        st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)
                    st.markdown(f'<div class="verification-footnote">{VERIFICATION_LINE}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(prac_content)
            else:
                st.markdown(prac_content)

    # -------------------------------------------------------------
    # TAB E: Quick Revision
    # -------------------------------------------------------------
    with tab_revision:
        st.markdown("Generate a high-yield, one-page revision summary of a unit including key points, formulas, definitions, and a 5-line recap.")

        if units_data:
            rev_unit_choices = [f"Unit {u.get('unit_number')}: {u.get('unit_title')}" for u in units_data]
        else:
            rev_unit_choices = ["Unit 1: Fundamentals"]

        chosen_rev_unit = st.selectbox("Choose Unit for Quick Revision", rev_unit_choices, key=f"rev_unit_sel_{subject_key}")
        rev_btn = st.button("Generate Revision Sheet", type="primary", key=f"rev_btn_{subject_key}")

        cache_key_rev = get_subject_cache_key(
            resolved_title, chosen_rev_unit, "all", "revision",
            branch=selected_branch, scheme=selected_scheme
        )
        cached_rev = db.get_cached_answer(cache_key_rev)

        rev_content = None
        if rev_btn:
            with st.status("Preparing your revision summary...", expanded=False):
                sel_topics = ""
                if units_data:
                    matched_u = next((u for u in units_data if f"Unit {u.get('unit_number')}: {u.get('unit_title')}" == chosen_rev_unit), None)
                    if matched_u:
                        sel_topics = matched_u.get("topics", "")
                sys_p, usr_p = build_quick_revision_prompt(resolved_title, chosen_rev_unit, unit_topics=sel_topics)
                client = getattr(pipeline, "client", None)
                model_name = getattr(pipeline, "model_name", None)
                raw_rev = call_subject_llm(sys_p, usr_p, client=client, model_name=model_name)
                rev_content = clean_subject_response(raw_rev)
                if VERIFICATION_LINE.lower() not in rev_content.lower():
                    rev_content = f"{rev_content.rstrip()}\n\n{VERIFICATION_LINE}"
                db.set_cached_answer(cache_key_rev, {
                    "answer": rev_content,
                    "response_type": "ANSWERED",
                    "subject": resolved_title
                })
        elif cached_rev and cached_rev.get("answer"):
            rev_content = clean_subject_response(cached_rev["answer"])

        if rev_content:
            st.markdown(rev_content)

def render_subject_assistance_page(pipeline, db):
    db = _ensure_fresh_db(db)
    st.title("🎓 Subject Assistance")
    st.markdown("Your patient AI academic tutor for B.Tech subjects, syllabus reference, practice problems, and quick revision.")
    render_subject_assistance_fragment(pipeline, db)

def render_admin_page(db):
    st.title("⚙️ Admin & Maintenance")
    st.markdown("Manage the AI knowledge base and view crawler statistics.")
    
    st.subheader("Manual Update")
    st.markdown("Trigger an incremental update of the knowledge base. This runs the web crawler in the background and indexes new or modified documents.")
    
    if st.button("Run Update Script Now", type="primary"):
        import subprocess
        import sys
        try:
            # Run asynchronously so it doesn't block the UI indefinitely
            subprocess.Popen([sys.executable, "update_knowledge_base.py"])
            st.success("Update script started in the background! Please check back later for the new report.")
        except Exception as e:
            st.error(f"Failed to start update: {e}")
            
    st.divider()
    
    st.subheader("Latest Coverage Report")
    report = db.get_latest_crawl_report()
    if report:
        st.markdown(f"**Last Run:** {format_date(report.get('timestamp'))}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pages Discovered", report.get("total_discovered", 0))
        c2.metric("Pages Processed", report.get("total_processed", 0))
        c3.metric("PDFs Found", report.get("total_pdfs", 0))
        c4.metric("Failed URLs", report.get("total_failed", 0))
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("New Items", report.get("new_count", 0))
        c6.metric("Modified Items", report.get("modified_count", 0))
        c7.metric("Unchanged Items", report.get("unchanged_count", 0))
        c8.metric("Removed Items", report.get("removed_count", 0))
        
        with st.expander("View Raw Report JSON"):
            st.json(report)
    else:
        st.info("No crawl reports found in the database. Run an update first.")

    st.divider()

    st.subheader("🛡️ Verified Ground Truth Facts (Highest Priority)")
    st.markdown("Facts added here override and supplement RAG search results with authoritative ground truth.")

    facts = db.get_all_verified_facts()
    if facts:
        import pandas as pd
        df = pd.DataFrame(facts)[["category", "entity", "attribute", "value", "source_url", "updated_at"]]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No verified facts currently stored.")

    with st.expander("➕ Add / Update Verified Fact"):
        with st.form("add_verified_fact_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                cat = st.selectbox("Category", ["leadership", "departments", "fees", "hostel", "library", "examinations", "placements", "general"])
            with c2:
                entity = st.text_input("Entity", placeholder="e.g. Principal / EEE HOD")
            with c3:
                attr = st.text_input("Attribute", placeholder="e.g. name / timings / fee_amount")
            val = st.text_area("Ground Truth Value", placeholder="e.g. Dr. B. Sreenivasa Reddy, M.Tech., Ph.D.")
            src = st.text_input("Official Source URL", placeholder="https://gprec.ac.in/...")
            admin_name = st.text_input("Verified By (Admin Name)*", placeholder="Enter your full name (cannot be 'admin')")
            submitted = st.form_submit_button("Save Verified Fact", type="primary")
            if submitted:
                if not entity or not val:
                    st.error("Entity and Ground Truth Value are required.")
                elif not admin_name or admin_name.strip().lower() == "admin":
                    st.error("Please enter a valid admin name. It cannot be blank or 'admin'.")
                else:
                    db.upsert_verified_fact(cat, entity, attr, val, src, verified_by=admin_name.strip())
                    st.cache_data.clear()
                    st.success(f"Saved verified fact for {entity} ({attr}) by {admin_name.strip()}!")
                    st.rerun()

    st.divider()

    st.subheader("🏛️ Entity Directory (Leadership, HODs, Offices)")
    st.markdown("Structured directory of verified leadership, departmental HODs, and key offices. Entries marked 'needs review' require confirmation.")

    entities = db.get_all_entities()
    if entities:
        import pandas as pd
        ent_df = pd.DataFrame(entities)[["role", "department", "name", "designation", "qualification", "contact_email", "source_url", "needs_review"]]
        st.dataframe(ent_df, use_container_width=True)
    else:
        st.info("No entities currently in directory.")

    with st.expander("➕ Add / Update Directory Entity"):
        with st.form("add_entity_form"):
            c1, c2 = st.columns(2)
            with c1:
                e_role = st.text_input("Role", placeholder="e.g. Principal / Head of Department / Librarian")
                e_dept = st.text_input("Department / Unit", placeholder="e.g. Administration / EEE / Library")
                e_name = st.text_input("Official Name", placeholder="e.g. Dr. B. Sreenivasa Reddy")
            with c2:
                e_desig = st.text_input("Designation", placeholder="e.g. Professor & Head")
                e_qual = st.text_input("Qualification", placeholder="e.g. Ph.D. / M.Tech.")
                e_email = st.text_input("Email", placeholder="e.g. principal@gprec.ac.in")
            e_src = st.text_input("Source URL", placeholder="https://gprec.ac.in/...")
            e_review = st.checkbox("Mark as 'Needs Review'", value=False)
            submitted_ent = st.form_submit_button("Save Entity", type="primary")
            if submitted_ent and e_role and e_dept and e_name:
                db.upsert_entity({
                    "role": e_role,
                    "department": e_dept,
                    "name": e_name,
                    "designation": e_desig,
                    "qualification": e_qual,
                    "contact_email": e_email,
                    "contact_phone": "",
                    "source_url": e_src,
                    "needs_review": 1 if e_review else 0
                })
                st.cache_data.clear()
                st.success(f"Saved entity: {e_name} ({e_role})!")
                st.rerun()

    st.divider()

    st.subheader("📊 Domain Coverage Audit")
    from src.data_quality import CoverageAuditor
    coverage = CoverageAuditor.audit_coverage(db)
    cov_cols = st.columns(3)
    for idx, (target_name, data) in enumerate(coverage.items()):
        col = cov_cols[idx % 3]
        with col:
            color = "#10b981" if data["status"] == "PRESENT" else "#f59e0b" if data["status"] == "INCOMPLETE" else "#ef4444"
            render_html_block(f"""
                <div style="border: 1px solid #e5e7eb; border-left: 4px solid {color}; border-radius: 6px; padding: 10px; margin-bottom: 10px;">
                    <b style="font-size: 0.9rem;">{target_name}</b><br>
                    <span style="font-size: 0.8rem; color: {color}; font-weight: bold;">{data['status']}</span>
                    <span style="font-size: 0.75rem; color: #6b7280;">({data['pages_count']} pages, {data['total_content_bytes']} bytes)</span>
                </div>
            """)


def get_canonical_designation(desig_raw: str) -> str:
    """Map raw designation to clean canonical academic title."""
    if not desig_raw:
        return "Faculty Member"
    d = desig_raw.lower().replace("\xa0", " ").strip()
    if "principal" in d:
        return "Principal & Professor"
    if "dean" in d:
        return "Dean & Professor" if "prof" in d else "Dean"
    if "associate head" in d or "assoc. head" in d:
        return "Associate Head of Dept."
    if "associate professor" in d or "assoc. prof" in d or "assoc prof" in d:
        return "Associate Professor"
    if "assistant professor" in d or "asst. prof" in d or "asst prof" in d:
        return "Assistant Professor"
    if "professor & head" in d or "professor and head" in d:
        return "Professor & Head"
    if "professor" in d:
        return "Professor"
    if "adjunct" in d:
        return "Adjunct Faculty"
    if "guest" in d:
        return "Guest Faculty"
    if "lecturer" in d:
        return "Lecturer"
    return desig_raw.strip()


def check_is_hod(faculty: dict) -> bool:
    """Return True if faculty record indicates Head of the Department."""
    if faculty.get("is_hod") == 1:
        return True
    desig = (faculty.get("designation") or "").lower().replace("\xa0", " ")
    if "assoc" in desig or "associate" in desig:
        return False
    return bool(re.search(r'\b(hod|head of the department|head of department|head)\b', desig))


def get_initials(name: str) -> str:
    """Extract clean 2-letter initials from name, stripping honorary prefixes."""
    cleaned = re.sub(r'^(dr[\s\.]+|sri[\s\.]+|smt[\s\.]+|mr[\s\.]+|mrs[\s\.]+|ms[\s\.]+|prof[\s\.]+)', '', name.strip(), flags=re.IGNORECASE)
    parts = [p for p in re.split(r'[\s\.]+', cleaned) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif len(parts) == 1 and parts[0]:
        return parts[0][:2].upper()
    return "GP"


def render_chat_faculty_cards(faculty_records: list, key_prefix: str = "chat_fac"):
    """Render custom modern HTML/CSS photo cards in chat message for faculty queries."""
    if not faculty_records:
        return

    # Deduplicate identical cards by name and department
    unique_records = []
    seen = set()
    for f in faculty_records:
        k = (re.sub(r'[^a-zA-Z0-9]', '', f.get("name", "")).lower(), f.get("department"))
        if k not in seen:
            seen.add(k)
            unique_records.append(f)
        
    for idx, f in enumerate(unique_records[:3]):
        photo_path = f.get("photo_path")
        has_photo = photo_path and os.path.exists(photo_path) and os.path.getsize(photo_path) > 0
        name = f.get("name", "Faculty Member")
        raw_desig = f.get("designation") or "Not listed"
        canonical_desig = get_canonical_designation(raw_desig)
        dept = f.get("department") or "Not listed"
        qual = f.get("qualification") or "Not listed"
        email = f.get("email")
        profile_url = f.get("profile_url")
        is_hod = check_is_hod(f)

        # Photo media HTML
        if has_photo:
            img_b64 = get_base64_of_bin_file(photo_path)
            media_html = f'<img src="data:image/jpeg;base64,{img_b64}" alt="{name}" class="faculty-photo" />'
        else:
            initials = get_initials(name)
            media_html = (
                f'<div class="faculty-photo-placeholder">'
                f'<span class="faculty-avatar-icon">👤</span>'
                f'<span class="faculty-avatar-initials">{initials}</span>'
                f'</div>'
            )

        # Badges HTML
        hod_badge = '<span class="fac-badge-hod">⭐ Head of Department</span>' if is_hod else ''
        badges_html = f'<span class="fac-badge-desig">{canonical_desig}</span> {hod_badge}'.strip()

        # Email HTML with copy-friendly button
        if email:
            email_html = (
                f'<div class="faculty-detail-item">'
                f'<span class="fac-icon">✉️</span>'
                f'<span class="fac-label">Email:</span>'
                f'<span class="fac-val">'
                f'<a href="mailto:{email}" class="fac-email-link" title="Click to compose email">{email}</a>'
                f'<button type="button" class="fac-copy-btn" '
                f'onclick="navigator.clipboard.writeText(\'{email}\'); this.innerText=\'✓ Copied\'; this.classList.add(\'copied\'); setTimeout(() => {{ this.innerText=\'📋 Copy\'; this.classList.remove(\'copied\'); }}, 1500);" '
                f'title="Copy email to clipboard">📋 Copy</button>'
                f'</span>'
                f'</div>'
            )
        else:
            email_html = (
                f'<div class="faculty-detail-item">'
                f'<span class="fac-icon">✉️</span>'
                f'<span class="fac-label">Email:</span>'
                f'<span class="fac-val fac-val-muted">Not officially listed</span>'
                f'</div>'
            )

        # Profile URL action button
        profile_action_html = ""
        if profile_url:
            profile_action_html = (
                f'<div class="faculty-card-actions">'
                f'<a href="{profile_url}" target="_blank" rel="noopener noreferrer" class="fac-profile-link">'
                f'📄 View Official Profile PDF ↗'
                f'</a>'
                f'</div>'
            )

        card_html = (
            f'<div class="faculty-card">'
            f'<div class="faculty-card-media">{media_html}</div>'
            f'<div class="faculty-card-content">'
            f'<div class="faculty-card-header">'
            f'<h3 class="faculty-name">{name}</h3>'
            f'<div class="faculty-badges">{badges_html}</div>'
            f'</div>'
            f'<div class="faculty-details-grid">'
            f'<div class="faculty-detail-item">'
            f'<span class="fac-icon">🏛️</span>'
            f'<span class="fac-label">Department:</span>'
            f'<span class="fac-val">{dept}</span>'
            f'</div>'
            f'<div class="faculty-detail-item">'
            f'<span class="fac-icon">🎓</span>'
            f'<span class="fac-label">Qualification:</span>'
            f'<span class="fac-val">{qual}</span>'
            f'</div>'
            f'{email_html}'
            f'</div>'
            f'{profile_action_html}'
            f'</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)


@st.fragment
def render_faculty_directory_fragment(db):
    # 1. Department List (cached)
    all_depts = get_cached_departments_with_faculty(db)
    dept_options = ["All Departments"] + all_depts

    # 2. Controls
    c_dept, c_search, c_filter = st.columns([1.5, 1.5, 1])
    with c_dept:
        selected_dept = st.selectbox("Department", dept_options, index=0, key="fac_filter_dept")
    with c_search:
        search_query = st.text_input("Search by Name or Keyword", placeholder="e.g. Kishor, Praveen, Ph.D.", key="fac_filter_search")
    with c_filter:
        fac_type = st.selectbox("Type", ["All Faculty", "Regular Only", "Guest / Adjunct", "HODs Only"], key="fac_filter_type")

    # Map filters
    dept_arg = None if selected_dept == "All Departments" else selected_dept
    guest_arg = None
    hod_arg = None
    if fac_type == "Regular Only":
        guest_arg = 0
    elif fac_type == "Guest / Adjunct":
        guest_arg = 1
    elif fac_type == "HODs Only":
        hod_arg = 1

    # Fetch faculty from database (cached)
    faculty_list = get_cached_faculty(
        db,
        department=dept_arg,
        search=search_query.strip() if search_query and search_query.strip() else None,
        is_guest=guest_arg,
        is_hod=hod_arg
    )

    # When browsing All Departments, deduplicate cross-appointed faculty profiles across branches
    # so students don't see duplicate cards for the exact same person, while showing all their departments
    if dept_arg is None and faculty_list:
        deduped = []
        seen = {}
        for f in faculty_list:
            name = f.get("name", "").strip()
            title_m = re.match(r'^(dr|sri|smt|prof|mr|mrs|ms)\.?\s*', name, re.IGNORECASE)
            title = title_m.group(1).lower() if title_m else ""
            raw_name = re.sub(r'^(dr|sri|smt|prof|mr|mrs|ms)\.?\s*', '', name, flags=re.IGNORECASE)
            letters = re.sub(r'[^a-zA-Z0-9]', '', raw_name).lower()
            photo = (f.get("photo_path") or "").replace("\\", "/").split("/")[-1].lower()
            profile = (f.get("profile_url") or "").replace("\\", "/").split("/")[-1].lower()
            key = (title, letters, photo or profile)
            if key in seen:
                existing = seen[key]
                existing_depts = existing.get("_all_depts", [existing["department"]])
                if f["department"] not in existing_depts:
                    existing_depts.append(f["department"])
                    existing["_all_depts"] = existing_depts
                    if f.get("is_hod"):
                        existing["is_hod"] = 1
            else:
                f_copy = dict(f)
                f_copy["_all_depts"] = [f["department"]]
                seen[key] = f_copy
                deduped.append(f_copy)
        faculty_list = deduped

    # Reset page to 1 when filters change
    cur_filter_state = (selected_dept, search_query.strip() if search_query else "", fac_type)
    if st.session_state.get("faculty_last_filter") != cur_filter_state:
        st.session_state.faculty_page_num = 1
        st.session_state.faculty_last_filter = cur_filter_state

    total_count = len(faculty_list)
    page_size = 12
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    
    current_page = st.session_state.get("faculty_page_num", 1)
    if current_page > total_pages:
        current_page = total_pages
        st.session_state.faculty_page_num = current_page
    elif current_page < 1:
        current_page = 1
        st.session_state.faculty_page_num = current_page

    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_count)
    visible_faculty = faculty_list[start_idx:end_idx]

    # Status / Metrics Header
    last_updated = "Official Website"
    if faculty_list and faculty_list[0].get("last_checked"):
        last_updated = faculty_list[0]["last_checked"].split()[0]

    count_label = f"Showing {start_idx + 1}–{end_idx} of {total_count} faculty members (Page {current_page} of {total_pages})" if total_count > 0 else "0 faculty members found"

    render_html_block(f"""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 18px; margin:15px 0 20px 0; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-size:1.05rem; font-weight:600; color:#1e293b;">{count_label}</span>
            </div>
            <div style="font-size:0.85rem; color:#64748b;">
                📅 <b>Last Updated:</b> {last_updated}
            </div>
        </div>
    """)

    if not faculty_list:
        st.info("No faculty members found matching your search and filter criteria.")
        return

    # Pagination controls at top
    if total_pages > 1:
        cp1, cp2, cp3 = st.columns([1, 2, 1])
        with cp1:
            if st.button("⬅️ Previous", disabled=(current_page <= 1), key=f"fac_top_prev_{current_page}", use_container_width=True):
                st.session_state.faculty_page_num = current_page - 1
                st.rerun(scope="fragment")
        with cp2:
            st.markdown(f"<div style='text-align:center; padding-top:6px; font-weight:600; color:#475569;'>Page {current_page} of {total_pages}</div>", unsafe_allow_html=True)
        with cp3:
            if st.button("Next ➡️", disabled=(current_page >= total_pages), key=f"fac_top_next_{current_page}", use_container_width=True):
                st.session_state.faculty_page_num = current_page + 1
                st.rerun(scope="fragment")

    # 3. Responsive 3-Column Grid for visible 12 items only
    cols_per_row = 3
    for i in range(0, len(visible_faculty), cols_per_row):
        row_members = visible_faculty[i:i + cols_per_row]
        cols = st.columns(cols_per_row)

        for j, f in enumerate(row_members):
            with cols[j]:
                photo_path = f.get("photo_path")
                has_photo = photo_path and os.path.exists(photo_path) and os.path.getsize(photo_path) > 0
                is_hod = check_is_hod(f)
                name = f.get("name", "Faculty Member")
                raw_desig = f.get("designation") or "Not listed"
                canonical_desig = get_canonical_designation(raw_desig)
                dept = f.get("department") or "Not listed"
                qual = f.get("qualification") or "Not listed"
                email = f.get("email")
                profile_url = f.get("profile_url")

                with st.container(border=True):
                    # Top Photo with relative static URL & lazy loading, and cached b64 fallback
                    if has_photo:
                        rel_photo = photo_path.replace("\\", "/").replace("data/faculty_photos/", "app/static/faculty_photos/")
                        b64_fallback = get_base64_of_bin_file(photo_path)
                        render_html_block(f"""
                            <div style="height:170px; background:#f8fafc; border-radius:6px; display:flex; align-items:center; justify-content:center; overflow:hidden; margin-bottom:10px;">
                                <img src="{rel_photo}" alt="{name}" loading="lazy" style="max-height:170px; max-width:100%; object-fit:cover; border-radius:6px;" onerror="this.onerror=null; this.src='data:image/jpeg;base64,{b64_fallback}';" />
                            </div>
                        """)
                    else:
                        initials = get_initials(name)
                        render_html_block(f"""
                            <div style="height:170px; background:#f1f5f9; border-radius:6px; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:3rem; color:#94a3b8; margin-bottom:10px;">
                                <span>👤</span>
                                <span style="font-size:0.82rem; font-weight:700; color:#64748b; margin-top:4px;">{initials}</span>
                            </div>
                        """)

                    # Info
                    hod_badge = " <span class='fac-badge-hod'>HOD</span>" if is_hod else ""

                    st.markdown(f"<div style='font-size:1.05rem; font-weight:700; line-height:1.3; min-height:45px; color:#0f172a;'>{name}{hod_badge}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin:4px 0;'><span class='fac-badge-desig'>{canonical_desig}</span></div>", unsafe_allow_html=True)
                    dept_display = ", ".join(f["_all_depts"]) if f.get("_all_depts") and len(f["_all_depts"]) > 1 else dept
                    st.markdown(f"<div style='font-size:0.82rem; color:#64748b; margin-bottom:4px;'>🏛️ {dept_display}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:0.82rem; margin-bottom:6px; color:#334155;'>🎓 <b>Qual:</b> {qual}</div>", unsafe_allow_html=True)

                    if email:
                        render_html_block(f"""
                            <div style='font-size:0.8rem; margin-bottom:10px; display:flex; align-items:center; gap:4px;'>
                                <span>📧</span> 
                                <a href='mailto:{email}' style='color:#2563eb; text-decoration:none;'>{email}</a>
                                <button type='button' class='fac-copy-btn' 
                                    onclick="navigator.clipboard.writeText('{email}'); this.innerText='✓'; setTimeout(() => this.innerText='📋', 1500);" 
                                    title='Copy email'>📋</button>
                            </div>
                        """)
                    else:
                        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-bottom:10px;'>📧 <i>Email not listed</i></div>", unsafe_allow_html=True)

                    if profile_url:
                        st.link_button("📄 View Profile", profile_url, key=f"grid_btn_{f['id']}_{start_idx}_{i}_{j}", use_container_width=True)
                    else:
                        st.button("No Profile PDF", key=f"grid_dis_{f['id']}_{start_idx}_{i}_{j}", disabled=True, use_container_width=True)

    # Bottom pagination
    if total_pages > 1:
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        bp1, bp2, bp3 = st.columns([1, 2, 1])
        with bp1:
            if st.button("⬅️ Previous Page", disabled=(current_page <= 1), key=f"fac_bot_prev_{current_page}", use_container_width=True):
                st.session_state.faculty_page_num = current_page - 1
                st.rerun(scope="fragment")
        with bp2:
            st.markdown(f"<div style='text-align:center; padding-top:6px; font-weight:600; color:#475569;'>Page {current_page} of {total_pages}</div>", unsafe_allow_html=True)
        with bp3:
            if st.button("Next Page ➡️", disabled=(current_page >= total_pages), key=f"fac_bot_next_{current_page}", use_container_width=True):
                st.session_state.faculty_page_num = current_page + 1
                st.rerun(scope="fragment")

def render_faculty_directory_page(db):
    """Render full-featured Faculty Directory page with filters and 3-column card grid."""
    st.title("👨‍🏫 GPREC Faculty Directory")
    st.markdown("Search and browse official faculty profiles, qualifications, and department directories.")
    render_faculty_directory_fragment(db)




