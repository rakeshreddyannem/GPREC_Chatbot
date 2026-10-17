import streamlit as st
import config
from src.embeddings import Embedder
from src.vectorstore import VectorStore
from src.rag_pipeline import RAGPipeline
from src.database import DatabaseManager
from ui.components import (
    load_css, render_header, render_welcome_state, 
    render_source_card, render_not_found, render_clarify,
    render_notices_page, render_deadlines_page, render_topic_page, format_date,
    render_academics_page, render_admin_page
)
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
def get_pipeline_v2():
    embedder = Embedder()
    vstore = VectorStore(embedder.dimension)
    return RAGPipeline(embedder, vstore)

def main():
    load_css()
    
    pipeline = get_pipeline_v2()
    db = DatabaseManager()
    
    if pipeline.client is None:
        st.error("⚠️ GEMINI_API_KEY is not set in the `.env` file. The assistant cannot generate responses.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "prompt_trigger" not in st.session_state:
        st.session_state.prompt_trigger = None
        
    if "page" not in st.session_state:
        st.session_state.page = "Ask AI"
        
    if "admin_mode" not in st.session_state:
        st.session_state.admin_mode = False

    # Sidebar Navigation
    with st.sidebar:
        st.title("Navigation")
        pages = {
            "Ask AI": "💬", 
            "Academics": "📘",
            "Latest Notices": "📅", 
            "Deadlines": "⏳", 
            "Departments": "📚", 
            "Examination": "📝", 
            "Placements": "💼", 
            "Hostel": "🏢", 
            "Library": "📖", 
            "Contact": "📞", 
            "About": "ℹ️"
        }
        
        # Admin authentication toggle
        st.markdown("---")
        admin_pass = st.text_input("Admin Password", type="password")
        env_admin_pass = os.environ.get("ADMIN_PASSWORD", "")
        if env_admin_pass and admin_pass == env_admin_pass:
            st.session_state.admin_mode = st.checkbox("Enable Admin/Debug Mode", value=st.session_state.admin_mode)
        elif admin_pass:
            st.error("Incorrect password")
        else:
            st.session_state.admin_mode = False

        if st.session_state.admin_mode:
            pages["Admin"] = "⚙️"
        
        selected_page = st.radio("Go to", list(pages.keys()), format_func=lambda x: f"{pages[x]} {x}", index=list(pages.keys()).index(st.session_state.page), label_visibility="collapsed")
        if selected_page != st.session_state.page:
            st.session_state.page = selected_page
            st.rerun()
            
        st.markdown("---")
        
        latest_report = get_latest_report()
        if latest_report:
            last_checked = format_date(latest_report.get("timestamp", ""))
            update_text = f"Last checked: {last_checked}"
        else:
            last_checked = "Not checked yet"
            update_text = f"Last checked: {last_checked}"
            
        st.markdown(f"""
            <div class="kb-card" style="padding:10px; background:#f9fafb; border-radius:8px; font-size:0.9rem;">
                <b>Knowledge Base Status</b><br>
                {update_text}<br>
                <small>Note: Data may not be perfectly current. Verify critical deadlines.</small>
            </div>
        """, unsafe_allow_html=True)
        
    # Routing based on selected page
    if st.session_state.page == "Ask AI":
        render_header()
        
        # Show welcome state if no messages
        if not st.session_state.messages:
            render_welcome_state()
            
        # Display chat history
        for idx, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                resp_type = msg.get("response_type", "ANSWERED")
                if resp_type == "CLARIFY":
                    render_clarify(msg.get("clarify_question") or msg["content"], msg.get("clarify_options", []), key_prefix=f"hist_{idx}")
                elif resp_type == "NOT_FOUND":
                    render_not_found(msg.get("suggested_questions"))
                else:
                    st.markdown(msg["content"])
                    if "sources" in msg and msg["sources"]:
                        render_source_card(
                            msg["sources"], 
                            msg.get("confidence", "Medium"), 
                            msg.get("is_recent_query", False), 
                            st.session_state.admin_mode,
                            confidence_reason=msg.get("confidence_reason", "")
                        )

        # Handle user input from sticky chat input or trigger
        chat_input_val = st.chat_input("Ask about GPREC...")

        prompt = st.session_state.prompt_trigger or chat_input_val
        
        # Clear trigger so it doesn't loop
        if st.session_state.prompt_trigger:
            st.session_state.prompt_trigger = None
            
        if prompt:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Generating answer..."):
                    res = pipeline.answer_question(prompt)
                    resp_type = res.get("response_type", "ANSWERED")
                    answer = res.get("answer", "")
                    sources = res.get("sources", [])
                    confidence = res.get("confidence", "Medium")
                    confidence_reason = res.get("confidence_reason", "")
                    is_recent_query = any(word in prompt.lower() for word in ["latest", "current", "deadline", "recent", "upcoming"])
                    
                    if resp_type == "CLARIFY":
                        render_clarify(res.get("clarify_question", answer), res.get("clarify_options", []))
                    elif resp_type == "NOT_FOUND":
                        render_not_found(res.get("suggested_questions"))
                    else:
                        st.markdown(answer)
                        if sources:
                            render_source_card(sources, confidence, is_recent_query, st.session_state.admin_mode, confidence_reason=confidence_reason)
                            
            # Save assistant message
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "response_type": resp_type,
                "clarify_question": res.get("clarify_question"),
                "clarify_options": res.get("clarify_options", []),
                "suggested_questions": res.get("suggested_questions", []),
                "sources": sources if resp_type in ["ANSWERED", "PARTIAL"] else [],
                "confidence": confidence,
                "confidence_reason": confidence_reason,
                "is_recent_query": is_recent_query
            })
            
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
    elif st.session_state.page == "Departments":
        render_topic_page("📚 Departments", "Learn about the various departments at GPREC.", [
            "What courses are offered in the CSE department?",
            "Who is the HOD of ECE?",
            "What are the research facilities in Mechanical Engineering?",
            "Tell me about the Civil Engineering department."
        ])
    elif st.session_state.page == "Examination":
        render_topic_page("📝 Examination", "Information about exams, results, and academic regulations.", [
            "When is the next end semester exam?",
            "What is the passing criteria for B.Tech?",
            "How can I apply for re-evaluation?",
            "Where can I find the exam timetable?"
        ])
    elif st.session_state.page == "Placements":
        render_topic_page("💼 Placements", "Details about placement drives, training, and statistics.", [
            "What is the highest package offered last year?",
            "Which companies visit the campus for recruitment?",
            "What is the eligibility criteria for placements?",
            "Does the college provide placement training?"
        ])
    elif st.session_state.page == "Hostel":
        render_topic_page("🏢 Hostel", "Information about student accommodation and facilities.", [
            "What are the hostel fees for this year?",
            "What are the hostel timings and rules?",
            "Are AC rooms available in the hostel?",
            "What is the process to apply for a hostel room?"
        ])
    elif st.session_state.page == "Library":
        render_topic_page("📖 Library", "Resources, timings, and rules for the central library.", [
            "What are the library timings?",
            "How many books can a student borrow?",
            "Is there a digital library facility?",
            "What is the fine for late return of books?"
        ])
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
    elif st.session_state.page == "Admin" and st.session_state.admin_mode:
        render_admin_page(db)

if __name__ == "__main__":
    main()
