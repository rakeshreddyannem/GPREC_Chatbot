import streamlit as st
import base64
import os
import json
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
            <div>
                <h1>AI Student Assistant</h1>
                <p>G. Pulla Reddy Engineering College</p>
                <div class="badge">Answers from official GPREC sources only</div>
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

    for notice in notices:
        title = notice.get("title") or "College Notice"
        ntype = notice.get("notice_type") or "circular"
        prog = notice.get("program") or ""
        sem = notice.get("semester") or ""
        reg = notice.get("scheme_regulation") or ""
        date_str = format_date(notice.get("published_date") or "")
        att_urls = notice.get("attachment_urls") or ""
        urls_list = [u.strip() for u in att_urls.split(",") if u.strip()] if att_urls else []
        primary_link = urls_list[0] if urls_list else (notice.get("source_page") or "http://examcell.gprec.ac.in/")
        raw_text = notice.get("raw_text") or ""
        
        badge_color = type_colors.get(ntype.lower(), "#4b5563")

        with st.container():
            st.markdown(f"#### [{title}]({primary_link})")
            
            # Tags row
            tags_html = f"<span style='background-color:{badge_color}; color:white; padding:3px 8px; border-radius:12px; font-size:0.78rem; font-weight:600;'>{ntype.title()}</span>"
            if prog:
                tags_html += f" <span style='background-color:#E0E7FF; color:#3730A3; padding:3px 8px; border-radius:12px; font-size:0.78rem; font-weight:500;'>{prog}</span>"
            if sem:
                tags_html += f" <span style='background-color:#F3F4F6; color:#1F2937; padding:3px 8px; border-radius:12px; font-size:0.78rem;'>{sem}</span>"
            if reg:
                tags_html += f" <span style='background-color:#FEF3C7; color:#92400E; padding:3px 8px; border-radius:12px; font-size:0.78rem;'>{reg}</span>"
            if date_str:
                tags_html += f" <span style='color:#6B7280; font-size:0.8rem; margin-left:8px;'>Published: {date_str}</span>"
            
            st.markdown(tags_html, unsafe_allow_html=True)
            
            if raw_text and raw_text != title:
                st.caption(raw_text[:200] + ('...' if len(raw_text) > 200 else ''))
                
            if urls_list:
                cols = st.columns(min(len(urls_list), 3))
                for idx, u in enumerate(urls_list[:3]):
                    with cols[idx]:
                        st.markdown(f"[📄 Download Document PDF]({u})")
                        
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
            submitted = st.form_submit_button("Save Verified Fact", type="primary")
            if submitted and entity and val:
                db.upsert_verified_fact(cat, entity, attr, val, src)
                st.success(f"Saved verified fact for {entity} ({attr})!")
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


