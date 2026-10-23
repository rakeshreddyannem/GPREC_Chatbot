import streamlit as st
import base64
import os
import json
import re
from datetime import datetime

def load_css(file_path="ui/style.css"):
    try:
        with open(file_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

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

def render_header():
    logo_base64 = get_base64_of_bin_file("gprec_logo1.png")
    img_html = f'<img src="data:image/png;base64,{logo_base64}" alt="GPREC Logo" class="college-logo">' if logo_base64 else ''
    
    st.markdown(f"""
        <div class="main-header">
            {img_html}
            <div class="header-text">
                <h1>AI Student Assistant</h1>
                <p>G. Pulla Reddy Engineering College (Autonomous)</p>
                <div class="badge-amber">Answers from official GPREC sources only</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_loading_skeleton():
    """Render a modern skeleton shimmer loading card with a smooth spinner."""
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

def quick_question_button(label, question):
    if st.button(label, use_container_width=True, key=f"btn_{label}"):
        st.session_state.prompt_trigger = question

def render_welcome_state():
    st.markdown("### How can I help you today?")
    st.markdown("Select a topic below or ask your own question.")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        quick_question_button("🎓 Admissions", "What is the admission process for B.Tech?")
        quick_question_button("💼 Placements", "What are the placement statistics for last year?")
    with c2:
        quick_question_button("📚 Departments", "What are the facilities in the CSE department?")
        quick_question_button("📖 Library", "What are the library timings and borrowing rules?")
    with c3:
        quick_question_button("🏢 Hostel", "What are the rules and facilities of the college hostel?")
        quick_question_button("📞 Contact", "How can I contact the college administration?")
    with c4:
        quick_question_button("📅 Notices", "What are the most recent notices?")
        quick_question_button("📝 Exams", "When are the upcoming examinations?")

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
    st.markdown("""
        <div class="not-found-card" style="padding: 15px; border-left: 4px solid #f59e0b; background-color: #fffbeb; border-radius: 6px; margin-top: 10px; margin-bottom: 10px;">
            <h4 style="margin-top:0; color: #b45309; font-size:1.05rem;">Information Not Found</h4>
            <p style="margin-bottom:8px; color: #92400e; font-size:0.92rem;">I couldn't find this information in the available official GPREC sources. Please verify with the official notice board or the relevant department office.</p>
        </div>
    """, unsafe_allow_html=True)
    
    suggestions = suggested_questions or [
        "What courses are offered at GPREC?",
        "What are the library timings and rules?",
        "Who is the head of the EEE department?"
    ]
    st.markdown("<p style='font-size:0.85rem; color:#6b7280; margin-bottom:4px;'>You can also ask:</p>", unsafe_allow_html=True)
    cols = st.columns(len(suggestions))
    for idx, (col, sug) in enumerate(zip(cols, suggestions)):
        with col:
            if st.button(sug, key=f"not_found_sug_{idx}_{sug[:10]}", use_container_width=True):
                st.session_state.prompt_trigger = sug
                st.rerun()

def render_clarify(question, options, key_prefix="clarify"):
    st.markdown(f"""
        <div style="padding: 12px 16px; border-left: 4px solid #3b82f6; background-color: #eff6ff; border-radius: 6px; margin: 8px 0;">
            <b style="color: #1e40af;">{question}</b>
        </div>
    """, unsafe_allow_html=True)
    
    cols = st.columns(min(len(options), 6))
    for idx, opt in enumerate(options):
        col_idx = idx % len(cols)
        with cols[col_idx]:
            if st.button(opt, key=f"{key_prefix}_{idx}_{opt}", use_container_width=True):
                st.session_state.prompt_trigger = f"{opt} {question}"
                st.rerun()


def render_notices_page(db):
    st.title("📅 Latest Notices & Examination Updates")
    st.markdown("Official notices, exam timetables, fee circulars, and announcements from GPREC.")
    
    # Filter controls
    c1, c2, c3 = st.columns(3)
    with c1:
        type_options = ["All", "timetable", "seating plan", "results", "revaluation", "hall ticket", "fee notification", "circular", "event"]
        selected_type = st.selectbox("Filter by Type", type_options, format_func=lambda x: x.title())
    with c2:
        prog_options = ["All", "B.Tech", "M.Tech", "MBA", "MCA"]
        selected_prog = st.selectbox("Filter by Program", prog_options)
    with c3:
        sem_options = ["All", "I Sem", "II Sem", "III Sem", "IV Sem", "V Sem", "VI Sem", "VII Sem", "VIII Sem"]
        selected_sem = st.selectbox("Filter by Semester", sem_options)

    # Fetch notices from structured notices table
    notices = db.get_notices(
        notice_type=selected_type if selected_type != "All" else None,
        program=selected_prog if selected_prog != "All" else None,
        semester=selected_sem if selected_sem != "All" else None,
        active_only=True,
        limit=50
    )
    
    # Check if newest notice is >30 days old
    all_notices = db.get_notices(limit=1)
    if all_notices and all_notices[0].get("published_date"):
        try:
            from datetime import datetime
            latest_dt = datetime.strptime(all_notices[0]["published_date"][:10], "%Y-%m-%d")
            days_old = (datetime.now() - latest_dt).days
            if days_old > 30:
                st.warning(f"⚠️ **Notice Board Notice:** The latest archived notice is {days_old} days old. Please consult the physical college notice board or [examcell.gprec.ac.in](http://examcell.gprec.ac.in/) for live announcements.")
        except Exception:
            pass

    if not notices:
        st.info("No notices found matching the selected filters. Please adjust the filters or check back later.")
        return

    st.caption(f"Showing {len(notices)} notices (latest first):")
    st.divider()

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

        with st.container():
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
                        
            st.divider()

def render_deadlines_page(pipeline, db=None):
    st.title("⏳ Deadlines & Important Dates")
    st.markdown("Upcoming examination fee deadlines, revaluation last dates, and academic schedule deadlines.")
    
    # Collect deadlines from both database notices and pipeline metadata
    deadlines = []
    
    if db is not None:
        try:
            # Query notices that contain deadlines or dates
            with db.get_connection() as conn:
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

    if not deadlines and pipeline:
        deadlines = [m for m in pipeline.vstore.metadata if m.get("category") == "Deadlines"]
    
    if not deadlines:
        st.info("No upcoming deadlines found in the knowledge base. Please check official notifications.")
        return
        
    for item in deadlines:
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

        with st.container():
            st.markdown(f"**[{title}]({att_url})**")
            meta_line = ""
            if formatted_pub:
                meta_line += f"Published: {formatted_pub}  "
            if countdown_badge:
                meta_line += countdown_badge
            if meta_line:
                st.markdown(meta_line, unsafe_allow_html=True)
            if raw_text and raw_text != title:
                st.caption(raw_text[:180] + ('...' if len(raw_text) > 180 else ''))
            st.divider()

def render_topic_page(title, intro, questions):
    st.title(title)
    st.markdown(intro)
    st.markdown("#### Ask a quick question:")
    for q in questions:
        if st.button(q, use_container_width=True, key=f"topic_{title}_{q}"):
            st.session_state.prompt_trigger = q
            st.session_state.page = "Ask AI"
            st.rerun()

def render_academics_page(db):
    st.title("📚 Academics")
    st.markdown("View syllabus and subjects for your branch and semester.")
    
    col1, col2 = st.columns(2)
    with col1:
        branch = st.selectbox("Select Branch", ["CSE", "ECE", "EEE", "CE", "ME", "CST", "CSM", "CSB"])
    with col2:
        semester = st.selectbox("Select Semester", ["1", "2", "3", "4", "5", "6", "7", "8"])
        
    if st.button("View Subjects"):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT course_code, course_title, unit_number, topics, outcomes "
                    "FROM syllabus WHERE branch = ? AND semester = ? "
                    "ORDER BY course_code, unit_number", 
                    (branch, semester)
                )
                rows = cursor.fetchall()
        except Exception as e:
            st.error(f"Error loading syllabus: {e}")
            return
            
        if not rows:
            st.info(f"No syllabus data found for {branch} Semester {semester}.")
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
            st.markdown(f"""
                <div style="border: 1px solid #e5e7eb; border-left: 4px solid {color}; border-radius: 6px; padding: 10px; margin-bottom: 10px;">
                    <b style="font-size: 0.9rem;">{target_name}</b><br>
                    <span style="font-size: 0.8rem; color: {color}; font-weight: bold;">{data['status']}</span>
                    <span style="font-size: 0.75rem; color: #6b7280;">({data['pages_count']} pages, {data['total_content_bytes']} bytes)</span>
                </div>
            """, unsafe_allow_html=True)


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
        
    for idx, f in enumerate(faculty_records[:3]):
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


def render_faculty_directory_page(db):
    """Render full-featured Faculty Directory page with filters and 3-column card grid."""
    st.title("👨‍🏫 GPREC Faculty Directory")
    st.markdown("Search and browse official faculty profiles, qualifications, and department directories.")

    # 1. Department List
    all_depts = db.get_all_departments_with_faculty()
    dept_options = ["All Departments"] + all_depts

    # 2. Controls
    c_dept, c_search, c_filter = st.columns([1.5, 1.5, 1])
    with c_dept:
        selected_dept = st.selectbox("Department", dept_options, index=0)
    with c_search:
        search_query = st.text_input("Search by Name or Keyword", placeholder="e.g. Kishor, Praveen, Ph.D.")
    with c_filter:
        fac_type = st.selectbox("Type", ["All Faculty", "Regular Only", "Guest / Adjunct", "HODs Only"])

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

    # Fetch faculty from database
    faculty_list = db.get_faculty(
        department=dept_arg,
        search=search_query if search_query.strip() else None,
        is_guest=guest_arg,
        is_hod=hod_arg,
        is_active=1
    )

    # Status / Metrics Header
    last_updated = "Official Website"
    if faculty_list and faculty_list[0].get("last_checked"):
        last_updated = faculty_list[0]["last_checked"].split()[0]

    st.markdown(f"""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 18px; margin:15px 0 25px 0; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-size:1.1rem; font-weight:600; color:#1e293b;">Total Faculty Found: </span>
                <span style="font-size:1.2rem; font-weight:700; color:#2563eb;">{len(faculty_list)}</span>
            </div>
            <div style="font-size:0.85rem; color:#64748b;">
                📅 <b>Last Updated:</b> {last_updated}
            </div>
        </div>
    """, unsafe_allow_html=True)

    if not faculty_list:
        st.info("No faculty members found matching your search and filter criteria.")
        return

    # 3. Responsive 3-Column Grid
    cols_per_row = 3
    for i in range(0, len(faculty_list), cols_per_row):
        row_members = faculty_list[i:i + cols_per_row]
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
                    # Top Photo
                    if has_photo:
                        st.image(photo_path, use_container_width=True)
                    else:
                        initials = get_initials(name)
                        st.markdown(f"""
                            <div style="height:170px; background:#f1f5f9; border-radius:6px; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:3rem; color:#94a3b8; margin-bottom:10px;">
                                <span>👤</span>
                                <span style="font-size:0.82rem; font-weight:700; color:#64748b; margin-top:4px;">{initials}</span>
                            </div>
                        """, unsafe_allow_html=True)

                    # Info
                    hod_badge = " <span class='fac-badge-hod'>HOD</span>" if is_hod else ""

                    st.markdown(f"<div style='font-size:1.05rem; font-weight:700; line-height:1.3; min-height:45px; color:#0f172a;'>{name}{hod_badge}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin:4px 0;'><span class='fac-badge-desig'>{canonical_desig}</span></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:0.82rem; color:#64748b; margin-bottom:4px;'>🏛️ {dept}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:0.82rem; margin-bottom:6px; color:#334155;'>🎓 <b>Qual:</b> {qual}</div>", unsafe_allow_html=True)

                    if email:
                        st.markdown(f"""
                            <div style='font-size:0.8rem; margin-bottom:10px; display:flex; align-items:center; gap:4px;'>
                                <span>📧</span> 
                                <a href='mailto:{email}' style='color:#2563eb; text-decoration:none;'>{email}</a>
                                <button type='button' class='fac-copy-btn' 
                                    onclick="navigator.clipboard.writeText('{email}'); this.innerText='✓'; setTimeout(() => this.innerText='📋', 1500);" 
                                    title='Copy email'>📋</button>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-bottom:10px;'>📧 <i>Email not listed</i></div>", unsafe_allow_html=True)

                    if profile_url:
                        st.link_button("📄 View Profile", profile_url, key=f"grid_btn_{f['id']}_{i}_{j}", use_container_width=True)
                    else:
                        st.button("No Profile PDF", key=f"grid_dis_{f['id']}_{i}_{j}", disabled=True, use_container_width=True)



