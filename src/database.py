import sys
import sqlite3
import json
import re
import difflib
from typing import Dict, Any, List, Optional
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Creates the required tables for pages, notices, deadlines, and reports."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Pages / Documents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT UNIQUE,
                    title TEXT,
                    category TEXT,
                    department TEXT,
                    source_type TEXT,
                    published_date TEXT,
                    last_modified TEXT,
                    last_checked TEXT,
                    content_hash TEXT,
                    version INTEGER DEFAULT 1,
                    is_current INTEGER DEFAULT 1,
                    status TEXT,
                    superseded_by INTEGER,
                    filepath TEXT,
                    error TEXT,
                    clean_text TEXT
                )
            """)
            
            # 1.5 Documents Table (For hyperlinked PDFs and Docs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_url TEXT UNIQUE,
                    link_text TEXT,
                    parent_page_url TEXT,
                    nearby_text TEXT,
                    category TEXT,
                    department TEXT,
                    published_date TEXT,
                    date_source TEXT,
                    file_size INTEGER,
                    content_hash TEXT,
                    version INTEGER DEFAULT 1,
                    last_checked TEXT,
                    title TEXT,
                    clean_text TEXT,
                    status TEXT,
                    filepath TEXT,
                    ocr_flag INTEGER DEFAULT 0,
                    needs_review INTEGER DEFAULT 0
                )
            """)

            # 2. Deadlines Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deadlines (
                    deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    category TEXT,
                    deadline_date TEXT,
                    published_date TEXT,
                    department TEXT,
                    source_url TEXT,
                    status TEXT,
                    last_checked TEXT
                )
            """)

            # 3. Notices Table (Structured Schema for Step 3)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notices (
                    notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    notice_type TEXT,
                    program TEXT,
                    semester TEXT,
                    scheme_regulation TEXT,
                    exam_month_year TEXT,
                    published_date TEXT,
                    attachment_urls TEXT,
                    source_page TEXT,
                    raw_text TEXT,
                    is_active INTEGER DEFAULT 1,
                    department TEXT,
                    important_date TEXT,
                    required_action TEXT,
                    venue TEXT,
                    contact TEXT,
                    source_url TEXT
                )
            """)

            # 4. Crawl Reports Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawl_reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    total_discovered INTEGER,
                    total_processed INTEGER,
                    total_failed INTEGER,
                    total_skipped INTEGER,
                    total_pdfs INTEGER,
                    new_count INTEGER,
                    modified_count INTEGER,
                    unchanged_count INTEGER,
                    removed_count INTEGER,
                    details_json TEXT
                )
            """)

            # 5. Syllabus Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS syllabus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_url TEXT,
                    regulation TEXT,
                    branch TEXT,
                    year INTEGER,
                    semester INTEGER,
                    academic_year TEXT,
                    course_code TEXT,
                    course_title TEXT,
                    category TEXT,
                    credits TEXT,
                    ltp TEXT,
                    unit_number INTEGER,
                    unit_title TEXT,
                    topics TEXT,
                    textbooks TEXT,
                    outcomes TEXT,
                    exam_scheme TEXT,
                    needs_review INTEGER DEFAULT 0,
                    page_num INTEGER
                )
            """)

            # 6. Acronyms Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS acronyms (
                    acronym TEXT PRIMARY KEY,
                    expansion TEXT,
                    source_url TEXT,
                    is_curated INTEGER DEFAULT 0
                )
            """)

            # 7. Data Quality Warnings Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_quality_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    warning_type TEXT,
                    details TEXT,
                    source_url TEXT,
                    timestamp TEXT
                )
            """)

            # 8. Verified Facts Table (Ground Truth with highest priority)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verified_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_key TEXT,
                    category TEXT,
                    entity TEXT,
                    attribute TEXT,
                    value TEXT,
                    source_url TEXT,
                    verified_by TEXT,
                    verified_date TEXT,
                    updated_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE(category, entity, attribute)
                )
            """)

            # 9. Entity Directory Table (Structured leadership, HODs, offices)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_directory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    department TEXT,
                    name TEXT,
                    designation TEXT,
                    qualification TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    source_url TEXT,
                    needs_review INTEGER DEFAULT 0,
                    updated_at TEXT,
                    UNIQUE(role, department, name)
                )
            """)

            # 10. Faculty Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faculty (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    designation TEXT,
                    qualification TEXT,
                    department TEXT NOT NULL,
                    email TEXT,
                    photo_url TEXT,
                    photo_path TEXT,
                    profile_url TEXT,
                    is_guest INTEGER DEFAULT 0,
                    is_hod INTEGER DEFAULT 0,
                    source_url TEXT,
                    last_checked TEXT,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE(name, department)
                )
            """)

            # 11. Answer Cache Table (SQLite cache with 24-hour expiry)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS answer_cache (
                    normalized_query TEXT PRIMARY KEY,
                    response_json TEXT,
                    created_at REAL
                )
            """)

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_faculty_dept ON faculty(department)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_faculty_name ON faculty(name)")
            except Exception:
                pass

            # Migrate any missing columns in verified_facts
            for col, ctype in [("question_key", "TEXT"), ("verified_by", "TEXT"), ("verified_date", "TEXT")]:
                try:
                    cursor.execute(f"ALTER TABLE verified_facts ADD COLUMN {col} {ctype}")
                except Exception:
                    pass

            # Migrate any missing columns in notices
            notice_cols = [
                ("notice_type", "TEXT"),
                ("program", "TEXT"),
                ("semester", "TEXT"),
                ("scheme_regulation", "TEXT"),
                ("exam_month_year", "TEXT"),
                ("attachment_urls", "TEXT"),
                ("source_page", "TEXT"),
                ("parent_page_url", "TEXT"),
                ("document_url", "TEXT"),
                ("raw_text", "TEXT"),
                ("is_active", "INTEGER DEFAULT 1"),
                ("category", "TEXT"),
                ("department", "TEXT"),
                ("date_source", "TEXT"),
                ("deadline_date", "TEXT"),
                ("last_checked", "TEXT")
            ]
            for col, ctype in notice_cols:
                try:
                    cursor.execute(f"ALTER TABLE notices ADD COLUMN {col} {ctype}")
                except Exception:
                    pass

            # Create unique indexes so document_url / source_url never produce duplicates
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_notices_document_url ON notices(document_url)")
            except Exception:
                pass

            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_deadlines_source_url ON deadlines(source_url)")
            except Exception:
                pass

            conn.commit()

        # One-time cleanup for old seeded demo rows
        self._cleanup_old_seed()

        # Seed curated acronyms, entity directory, verified facts, and default notices
        self._seed_curated_acronyms()
        self._seed_verified_facts()
        self._seed_entity_directory()
        self._seed_default_notices()

    def _cleanup_old_seed(self):
        """One-time cleanup: deletes any rows whose source is the old demo seed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            removed_total = 0

            # 1. Clean old seeded notices
            cursor.execute("""
                DELETE FROM notices 
                WHERE attachment_urls LIKE '%/pdf/exam_cell/%'
                   OR source_page = 'http://examcell.gprec.ac.in/'
                   OR attachment_urls = 'https://gprec.ac.in/pdf/admissions/APHERMC_Tuition_Fee_Notification_GPREC.pdf'
            """)
            removed_notices = cursor.rowcount
            if removed_notices > 0:
                removed_total += removed_notices

            # 2. Clean old seeded verified_facts
            cursor.execute("""
                DELETE FROM verified_facts 
                WHERE verified_by = 'admin' 
                   OR question_key IN ('principal', 'placements', 'hod_eee', 'central_library', 'library_eee', 'boys_hostel', 'fee_structure')
            """)
            removed_facts = cursor.rowcount
            if removed_facts > 0:
                removed_total += removed_facts

            # 3. Clean old seeded entity_directory
            old_entity_names = [
                "Dr. B. Sreenivasa Reddy", "Dr. G. Kishor", "Dr. S. Nagaraja Rao",
                "Dr. N. Kasiviswanath", "Dr. K. Devaki Devi", "Dr. E. Sanjeeva Rayudu",
                "Dr. K. Venkata Ramana", "Dr. K. Govardhan Reddy", "Dr. G. S. Kumar",
                "Sri. P. Gopinath", "Dr. C. Harinatha Reddy"
            ]
            placeholders = ",".join(["?"] * len(old_entity_names))
            cursor.execute(f"""
                DELETE FROM entity_directory 
                WHERE name IN ({placeholders})
            """, old_entity_names)
            removed_entities = cursor.rowcount
            if removed_entities > 0:
                removed_total += removed_entities

            conn.commit()

            if removed_total > 0:
                print(f"[DatabaseManager] Cleaned up {removed_total} rows from old demo seed (notices: {removed_notices}, verified_facts: {removed_facts}, entity_directory: {removed_entities}).")

    def _seed_curated_acronyms(self):
        if not getattr(config, "SEED_DEMO_DATA", False):
            return
        default_acronyms = {
            "GPREC": ("G. Pulla Reddy Engineering College", "https://gprec.ac.in", 1),
            "EEE": ("Electrical and Electronics Engineering", "https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/", 1),
            "ECE": ("Electronics and Communication Engineering", "https://gprec.ac.in/programs-offered/electronics-and-communication-engineering/", 1),
            "CSE": ("Computer Science and Engineering", "https://gprec.ac.in/programs-offered/computer-science-and-engineering/", 1),
            "CSM": ("Computer Science and Machine Learning", "https://gprec.ac.in/programs-offered/artificial-intelligence-and-machine-learning/", 1),
            "CSD": ("Computer Science and Data Science", "https://gprec.ac.in/programs-offered/data-science/", 1),
            "CE": ("Civil Engineering", "https://gprec.ac.in/programs-offered/civil-engineering/", 1),
            "ME": ("Mechanical Engineering", "https://gprec.ac.in/programs-offered/mechanical-engineering/", 1),
            "H&S": ("Humanities and Basic Sciences", "https://gprec.ac.in/humanities-basic-sciences/", 1),
            "HBS": ("Humanities and Basic Sciences", "https://gprec.ac.in/humanities-basic-sciences/", 1),
            "T&P": ("Training and Placement", "https://gprec.ac.in/training-placements/", 1),
            "COE": ("Controller of Examinations", "https://gprec.ac.in/examinations/", 1),
            "BOS": ("Board of Studies", "https://gprec.ac.in", 1),
            "ITCA": ("Intensive Training Program for Career Advancement", "http://examcell.gprec.ac.in/studentserviceslogin.aspx", 1)
        }
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for acr, (exp, src, cur) in default_acronyms.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO acronyms (acronym, expansion, source_url, is_curated)
                    VALUES (?, ?, ?, ?)
                """, (acr, exp, src, cur))
            conn.commit()

    def _seed_verified_facts(self):
        if not getattr(config, "SEED_DEMO_DATA", False):
            return
        from datetime import datetime
        now = datetime.now().isoformat()
        date_str = datetime.now().strftime("%Y-%m-%d")
        default_facts = [
            ("principal", "leadership", "Principal", "name", "Dr. B. Sreenivasa Reddy", "https://gprec.ac.in", "admin", date_str),
            ("principal", "leadership", "College Head", "title", "Principal: Dr. B. Sreenivasa Reddy, M.Tech., Ph.D.", "https://gprec.ac.in", "admin", date_str),
            ("placements", "leadership", "Training and Placement Officer", "name", "Dr. K. Govardhan Reddy", "https://gprec.ac.in/training-placements/", "admin", date_str),
            ("hod_eee", "leadership", "EEE Head of Department", "name", "Dr. G. Kishor", "https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/", "admin", date_str),
            ("central_library", "library", "Central Library", "timings", "Monday to Saturday: 8:00 AM to 8:00 PM; Sunday & Holidays: 9:00 AM to 1:00 PM", "https://gprec.ac.in/library/", "admin", date_str),
            ("library_eee", "library", "EEE Department Library", "head", "The EEE Department Library is maintained under the supervision of the Head of the Department (Dr. G. Kishor) and designated faculty library in-charge.", "https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/", "admin", date_str),
            ("boys_hostel", "hostel", "Boys Hostel", "facilities", "On-campus boys hostel accommodation with dining mess, high-speed Wi-Fi, 24/7 security, power backup, study halls, and residential warden.", "https://gprec.ac.in/hostel/", "admin", date_str),
            ("fee_structure", "fees", "Fee Structure", "status", "Tuition fee structure is prescribed by the Andhra Pradesh Higher Education Regulatory and Monitoring Commission (APHERMC) / Government of Andhra Pradesh for Autonomous Engineering Colleges.", "https://gprec.ac.in/admissions/", "admin", date_str),
            ("fee_structure", "fees", "Fee Structure", "tuition_fee", "As per APHERMC / Government of Andhra Pradesh notifications for Autonomous Engineering Colleges (Academic Year 2024-25 & 2025-26), the tuition fee for B.Tech programs (including EEE, CSE, ECE, ME, CE) under Category-A (Convenor Quota through EAPCET) is ₹70,000 per annum. Category-B (Management/NRI Quota) fees are governed by AP State Govt guidelines. Additional university, examination, and hostel fees apply separately.", "https://gprec.ac.in/admissions/", "admin", date_str)
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for qk, cat, ent, attr, val, src, vb, vd in default_facts:
                cursor.execute("""
                    INSERT OR IGNORE INTO verified_facts (question_key, category, entity, attribute, value, source_url, verified_by, verified_date, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (qk, cat, ent, attr, val, src, vb, vd, now))
            conn.commit()

    def _seed_entity_directory(self):
        if not getattr(config, "SEED_DEMO_DATA", False):
            return
        from datetime import datetime
        now = datetime.now().isoformat()
        default_entities = [
            ("Principal", "Administration", "Dr. B. Sreenivasa Reddy", "Principal & Professor", "M.Tech., Ph.D.", "principal@gprec.ac.in", "", "https://gprec.ac.in", 0),
            ("Head of Department", "EEE", "Dr. G. Kishor", "Professor & Head of Department", "Ph.D.", "eee@gprec.ac.in", "", "https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/", 0),
            ("Head of Department", "ECE", "Dr. S. Nagaraja Rao", "Professor & Head of Department", "Ph.D.", "ece@gprec.ac.in", "", "https://gprec.ac.in/programs-offered/electronics-and-communication-engineering/", 0),
            ("Head of Department", "CSE", "Dr. N. Kasiviswanath", "Professor & Head of Department", "Ph.D.", "cse@gprec.ac.in", "", "https://gprec.ac.in/programs-offered/computer-science-and-engineering/", 0),
            ("Head of Department", "ME", "Dr. K. Devaki Devi", "Professor & Head of Department", "Ph.D.", "me@gprec.ac.in", "", "https://gprec.ac.in/programs-offered/mechanical-engineering/", 0),
            ("Head of Department", "CE", "Dr. E. Sanjeeva Rayudu", "Professor & Head of Department", "Ph.D.", "ce@gprec.ac.in", "", "https://gprec.ac.in/programs-offered/civil-engineering/", 0),
            ("Head of Department", "H&S", "Dr. K. Venkata Ramana", "Professor & Head of Department", "Ph.D.", "hns@gprec.ac.in", "", "https://gprec.ac.in/humanities-basic-sciences/", 0),
            ("Training & Placement Officer", "T&P", "Dr. K. Govardhan Reddy", "Professor of CSE(AIML) & TPO", "Ph.D.", "tpo@gprec.ac.in", "", "https://gprec.ac.in/training-placements/", 0),
            ("Controller of Examinations", "Examinations", "Dr. G. S. Kumar", "Professor & COE", "Ph.D.", "coe@gprec.ac.in", "", "https://gprec.ac.in/examinations/", 0),
            ("Librarian", "Central Library", "Sri. P. Gopinath", "Librarian", "M.L.I.Sc.", "library@gprec.ac.in", "", "https://gprec.ac.in/library/", 0),
            ("Chief Warden", "Hostel", "Dr. C. Harinatha Reddy", "Chief Warden (Boys Hostel)", "Ph.D.", "hostel@gprec.ac.in", "", "https://gprec.ac.in/hostel/", 0)
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for role, dept, name, desig, qual, email, phone, src, nr in default_entities:
                cursor.execute("""
                    INSERT OR IGNORE INTO entity_directory (role, department, name, designation, qualification, contact_email, contact_phone, source_url, needs_review, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (role, dept, name, desig, qual, email, phone, src, nr, now))
            conn.commit()

    def upsert_entity(self, entity_data: Dict[str, Any]):
        from datetime import datetime
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO entity_directory (role, department, name, designation, qualification, contact_email, contact_phone, source_url, needs_review, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(role, department, name) DO UPDATE SET
                    designation = excluded.designation,
                    qualification = excluded.qualification,
                    contact_email = excluded.contact_email,
                    contact_phone = excluded.contact_phone,
                    source_url = excluded.source_url,
                    needs_review = excluded.needs_review,
                    updated_at = excluded.updated_at
            """, (
                entity_data.get("role"),
                entity_data.get("department"),
                entity_data.get("name"),
                entity_data.get("designation"),
                entity_data.get("qualification"),
                entity_data.get("contact_email"),
                entity_data.get("contact_phone"),
                entity_data.get("source_url"),
                entity_data.get("needs_review", 0),
                now
            ))
            conn.commit()

    def get_all_entities(self, needs_review_only: bool = False) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if needs_review_only:
                cursor.execute("SELECT * FROM entity_directory WHERE needs_review = 1 ORDER BY department, role")
            else:
                cursor.execute("SELECT * FROM entity_directory ORDER BY department, role")
            return [dict(row) for row in cursor.fetchall()]

    def search_entity_directory(self, query: str) -> List[Dict[str, Any]]:
        q_lower = query.lower()
        entities = self.get_all_entities()
        matched = []
        for e in entities:
            role = e.get("role", "").lower()
            dept = e.get("department", "").lower()
            name = e.get("name", "").lower()
            
            # Specific queries
            if ("principal" in q_lower or "head of college" in q_lower or "head of the college" in q_lower) and "principal" in role:
                matched.append(e)
            elif ("hod" in q_lower or "head of department" in q_lower or "head of the department" in q_lower) and "head of department" in role:
                if dept in q_lower or (dept == "eee" and "electrical" in q_lower) or (dept == "ece" and "electronics" in q_lower) or (dept == "cse" and "computer" in q_lower):
                    matched.append(e)
            elif ("library" in q_lower and ("head" in q_lower or "librarian" in q_lower or "in charge" in q_lower)) and ("librarian" in role or "library" in dept):
                matched.append(e)
            elif ("hostel" in q_lower and ("warden" in q_lower or "in charge" in q_lower)) and "warden" in role:
                matched.append(e)
            elif ("placement" in q_lower or "tpo" in q_lower) and "placement" in role:
                matched.append(e)
            elif ("exam" in q_lower and ("coe" in q_lower or "controller" in q_lower)) and "controller" in role:
                matched.append(e)
            elif name in q_lower:
                matched.append(e)
        return matched

    def _seed_default_notices(self):
        if not getattr(config, "SEED_DEMO_DATA", False):
            return
        default_notices = [
            {
                "title": "B.Tech IV Sem (R20) Regular & Supplementary Examinations Timetable - April 2026",
                "notice_type": "timetable",
                "program": "B.Tech",
                "semester": "IV Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-03-20",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/BTech_IV_Sem_R20_Timetable_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "B.Tech IV Semester (R20 Regulations) Regular and Supplementary End Examinations Schedule April 2026. All branches: EEE, ECE, CSE, ME, CE, CST, CSM, CSD.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "B.Tech II Sem (R23) Regular Examinations Timetable - May 2026",
                "notice_type": "timetable",
                "program": "B.Tech",
                "semester": "II Sem",
                "scheme_regulation": "R23",
                "exam_month_year": "May 2026",
                "published_date": "2026-03-18",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/BTech_II_Sem_R23_Timetable_May_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "B.Tech II Semester (R23 Regulations) Regular End Examinations Timetable May 2026. Timings: 10:00 AM to 1:00 PM.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "B.Tech VI Sem (R20) Supplementary Examinations Timetable - April 2026",
                "notice_type": "timetable",
                "program": "B.Tech",
                "semester": "VI Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-03-15",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/BTech_VI_Sem_R20_Supple_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "B.Tech VI Semester (R20 Regulations) Supplementary End Examinations Schedule April 2026.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "B.Tech VIII Sem (R20) Advanced Supplementary Examinations Timetable - April 2026",
                "notice_type": "timetable",
                "program": "B.Tech",
                "semester": "VIII Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-03-10",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/BTech_VIII_Sem_R20_Timetable_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "B.Tech VIII Semester (R20 Regulations) Advanced Supplementary End Examinations Timetable April 2026.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "M.Tech II Sem (R20) Regular & Supplementary Examinations Timetable - April 2026",
                "notice_type": "timetable",
                "program": "M.Tech",
                "semester": "II Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-03-05",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/MTech_II_Sem_R20_Timetable_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "M.Tech II Semester (R20 Regulations) Regular & Supplementary Examinations Schedule April 2026.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "Seating Plan & Hall Allocation for B.Tech End Examinations April 2026",
                "notice_type": "seating plan",
                "program": "B.Tech",
                "semester": "IV Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-03-25",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/Seating_Plan_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "Seating arrangement and room allocation list for candidates appearing for B.Tech End Examinations April 2026.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "Notification for Revaluation & Script Verification of B.Tech III & V Sem Examinations",
                "notice_type": "revaluation",
                "program": "B.Tech",
                "semester": "III Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "December 2025",
                "published_date": "2026-02-28",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/Revaluation_Notice_Dec_2025.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "Last date for applying for Revaluation and Personal Script Verification of B.Tech III & V Sem December 2025 examinations.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "Hall Tickets Issuance for April 2026 Regular and Supplementary Examinations",
                "notice_type": "hall ticket",
                "program": "B.Tech",
                "semester": "IV Sem",
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-03-22",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/Hall_Ticket_Notice_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "Students can collect or download their Hall Tickets for April 2026 examinations through student login portal.",
                "is_active": 1,
                "department": "Examinations"
            },
            {
                "title": "Official Notification: B.Tech Tuition Fee Structure Prescribed by APHERMC for 2024-25 & 2025-26",
                "notice_type": "fee notification",
                "program": "B.Tech",
                "semester": None,
                "scheme_regulation": None,
                "exam_month_year": None,
                "published_date": "2025-08-10",
                "attachment_urls": "https://gprec.ac.in/pdf/admissions/APHERMC_Tuition_Fee_Notification_GPREC.pdf",
                "source_page": "https://gprec.ac.in/admissions/",
                "raw_text": "Government of Andhra Pradesh & APHERMC Tuition fee notification for G. Pulla Reddy Engineering College (Autonomous). Category-A Convenor quota fee: ₹70,000 per annum.",
                "is_active": 1,
                "department": "Admissions"
            },
            {
                "title": "Semester End Examination Fee Notification - April/May 2026 Examinations",
                "notice_type": "fee notification",
                "program": "B.Tech",
                "semester": None,
                "scheme_regulation": "R20",
                "exam_month_year": "April 2026",
                "published_date": "2026-02-15",
                "attachment_urls": "https://gprec.ac.in/pdf/exam_cell/Exam_Fee_Notification_April_2026.pdf",
                "source_page": "http://examcell.gprec.ac.in/",
                "raw_text": "Notification for payment of Examination Fee for B.Tech End Examinations April/May 2026. Last date without fine: 10-03-2026; with late fee of ₹500: 18-03-2026.",
                "is_active": 1,
                "department": "Examinations"
            }
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for n in default_notices:
                cursor.execute("SELECT notice_id FROM notices WHERE title = ?", (n["title"],))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO notices (
                            title, notice_type, program, semester, scheme_regulation, 
                            exam_month_year, published_date, attachment_urls, source_page, 
                            raw_text, is_active, department, source_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        n["title"], n["notice_type"], n["program"], n["semester"],
                        n["scheme_regulation"], n["exam_month_year"], n["published_date"],
                        n["attachment_urls"], n["source_page"], n["raw_text"],
                        n["is_active"], n["department"], n.get("attachment_urls", "")
                    ))
            conn.commit()

    def upsert_notice(self, notice_data: Dict[str, Any]) -> int:
        from src.notice_parser import NoticeParser
        title = notice_data.get("title", "")
        ntype = notice_data.get("notice_type") or NoticeParser.classify_notice_type(title, notice_data.get("raw_text", ""))
        prog = notice_data.get("program") or NoticeParser.extract_program(title, notice_data.get("raw_text", ""))
        sem = notice_data.get("semester") or NoticeParser.extract_semester(title, notice_data.get("raw_text", ""))
        reg = notice_data.get("scheme_regulation") or NoticeParser.extract_regulation(title, notice_data.get("raw_text", ""))
        month_yr = notice_data.get("exam_month_year") or NoticeParser.extract_exam_month_year(title, notice_data.get("raw_text", ""))
        pub_date = notice_data.get("published_date")
        att_urls = notice_data.get("attachment_urls") or ""
        if isinstance(att_urls, list):
            att_urls = ",".join(att_urls)
            
        doc_url = notice_data.get("document_url") or notice_data.get("source_url") or ""
        parent_page = notice_data.get("parent_page_url") or notice_data.get("source_page") or ""
        category = notice_data.get("category") or ""
        department = notice_data.get("department") or ""
        date_src = notice_data.get("date_source")
        deadline_date = notice_data.get("deadline_date")
        last_checked = notice_data.get("last_checked")
        is_act = notice_data.get("is_active", 1)
        raw_text = notice_data.get("raw_text") or title

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if doc_url:
                cursor.execute("SELECT notice_id FROM notices WHERE document_url = ?", (doc_url,))
                existing = cursor.fetchone()
                if existing:
                    nid = existing["notice_id"]
                    cursor.execute("""
                        UPDATE notices SET
                            title = ?,
                            notice_type = ?,
                            program = ?,
                            semester = ?,
                            scheme_regulation = ?,
                            exam_month_year = ?,
                            published_date = ?,
                            date_source = ?,
                            attachment_urls = ?,
                            source_page = ?,
                            parent_page_url = ?,
                            raw_text = ?,
                            is_active = ?,
                            category = ?,
                            department = ?,
                            deadline_date = ?,
                            last_checked = ?
                        WHERE notice_id = ?
                    """, (
                        title, ntype, prog, sem, reg, month_yr, pub_date, date_src,
                        att_urls, parent_page, parent_page, raw_text, is_act,
                        category, department, deadline_date, last_checked, nid
                    ))
                    conn.commit()
                    return nid

            cursor.execute("""
                INSERT INTO notices (
                    title, notice_type, program, semester, scheme_regulation, 
                    exam_month_year, published_date, date_source, attachment_urls,
                    source_page, parent_page_url, document_url, raw_text,
                    is_active, category, department, deadline_date, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, ntype, prog, sem, reg, month_yr, pub_date, date_src, att_urls,
                parent_page, parent_page, doc_url, raw_text, is_act,
                category, department, deadline_date, last_checked
            ))
            conn.commit()
            return cursor.lastrowid

    def upsert_deadline(self, deadline_data: Dict[str, Any]) -> int:
        title = deadline_data.get("title", "")
        category = deadline_data.get("category", "")
        deadline_date = deadline_data.get("deadline_date")
        published_date = deadline_data.get("published_date")
        department = deadline_data.get("department", "")
        source_url = deadline_data.get("source_url") or deadline_data.get("document_url") or ""
        status = deadline_data.get("status", "ACTIVE")
        last_checked = deadline_data.get("last_checked")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if source_url:
                cursor.execute("SELECT deadline_id FROM deadlines WHERE source_url = ?", (source_url,))
                existing = cursor.fetchone()
                if existing:
                    did = existing["deadline_id"]
                    cursor.execute("""
                        UPDATE deadlines SET
                            title = ?,
                            category = ?,
                            deadline_date = ?,
                            published_date = ?,
                            department = ?,
                            status = ?,
                            last_checked = ?
                        WHERE deadline_id = ?
                    """, (title, category, deadline_date, published_date, department, status, last_checked, did))
                    conn.commit()
                    return did

            cursor.execute("""
                INSERT INTO deadlines (
                    title, category, deadline_date, published_date, department,
                    source_url, status, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, category, deadline_date, published_date, department, source_url, status, last_checked))
            conn.commit()
            return cursor.lastrowid

    def get_notices(
        self, 
        notice_type: Optional[str] = None, 
        program: Optional[str] = None, 
        semester: Optional[str] = None, 
        active_only: bool = True, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM notices WHERE 1=1"
            params = []
            if active_only:
                query += " AND is_active = 1"
            if notice_type and notice_type.lower() != "all":
                query += " AND LOWER(notice_type) = LOWER(?)"
                params.append(notice_type)
            if program and program.lower() != "all":
                query += " AND LOWER(program) = LOWER(?)"
                params.append(program)
            if semester and semester.lower() != "all":
                query += " AND LOWER(semester) = LOWER(?)"
                params.append(semester)
            query += " ORDER BY CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC, notice_id DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_notices(self, notice_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        return self.get_notices(notice_type=notice_type, limit=limit)

    def search_notices(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        q_lower = f"%{query.lower()}%"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notices 
                WHERE is_active = 1 AND (
                    LOWER(title) LIKE ? OR 
                    LOWER(raw_text) LIKE ? OR 
                    LOWER(notice_type) LIKE ? OR
                    LOWER(program) LIKE ? OR
                    LOWER(scheme_regulation) LIKE ?
                )
                ORDER BY CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC, notice_id DESC LIMIT ?
            """, (q_lower, q_lower, q_lower, q_lower, q_lower, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_deadlines(self, active_only: bool = True, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM deadlines WHERE 1=1"
            if active_only:
                query += " AND (status = 'ACTIVE' OR status IS NULL)"
            query += " ORDER BY CASE WHEN deadline_date IS NOT NULL AND deadline_date != '' THEN deadline_date ELSE '9999-12-31' END ASC, deadline_id DESC LIMIT ?"
            cursor.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def upsert_verified_fact(self, category: str, entity: str, attribute: str, value: str, source_url: str = "", question_key: str = "", verified_by: str = "", is_active: int = 1):
        if not verified_by or verified_by.strip().lower() == "admin":
            raise ValueError("verified_by must hold the admin name that was typed in, never a hard-coded 'admin'.")
        from datetime import datetime
        now = datetime.now().isoformat()
        date_str = datetime.now().strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO verified_facts (question_key, category, entity, attribute, value, source_url, verified_by, verified_date, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category, entity, attribute) DO UPDATE SET
                    question_key = excluded.question_key,
                    value = excluded.value,
                    source_url = excluded.source_url,
                    verified_by = excluded.verified_by,
                    verified_date = excluded.verified_date,
                    updated_at = excluded.updated_at,
                    is_active = excluded.is_active
            """, (question_key, category, entity, attribute, value, source_url, verified_by.strip(), date_str, now, is_active))
            conn.commit()

    def get_all_verified_facts(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT * FROM verified_facts WHERE is_active = 1 ORDER BY category, entity")
            else:
                cursor.execute("SELECT * FROM verified_facts ORDER BY category, entity")
            return [dict(row) for row in cursor.fetchall()]

    def get_matching_verified_facts(self, query: str) -> List[Dict[str, Any]]:
        q_lower = query.lower()
        facts = self.get_all_verified_facts(active_only=True)
        matched = []
        for f in facts:
            ent = f["entity"].lower()
            cat = f["category"].lower()
            attr = f["attribute"].lower()
            qk = (f.get("question_key") or "").lower()

            # Keyword matching rules
            if ("principal" in q_lower or "head of college" in q_lower or "head of the college" in q_lower) and ("principal" in ent or qk == "principal"):
                matched.append(f)
            elif ("placement" in q_lower or "t&p" in q_lower) and ("placement officer" in ent or qk == "placements"):
                matched.append(f)
            elif ("eee" in q_lower and ("hod" in q_lower or "head" in q_lower)) and ("eee head" in ent or qk == "hod_eee"):
                matched.append(f)
            elif ("eee" in q_lower and "library" in q_lower and "head" in q_lower) and ("eee department library" in ent or qk == "library_eee"):
                matched.append(f)
            elif ("library" in q_lower and ("timing" in q_lower or "hour" in q_lower or "time" in q_lower)) and ("central library" in ent or qk == "central_library"):
                matched.append(f)
            elif ("boys hostel" in q_lower or "hostel" in q_lower) and ("boys hostel" in ent or qk == "boys_hostel"):
                matched.append(f)
            elif ("fee" in q_lower or "tuition" in q_lower) and qk == "fee_structure":
                matched.append(f)
            elif qk and qk in q_lower:
                matched.append(f)
            elif ent in q_lower or (len(ent) > 3 and ent in q_lower):
                matched.append(f)
        return matched

    def get_acronym(self, acronym: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM acronyms WHERE UPPER(acronym) = ?", (acronym.upper(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def upsert_acronym(self, acronym: str, expansion: str, source_url: str = "", is_curated: int = 0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO acronyms (acronym, expansion, source_url, is_curated)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(acronym) DO UPDATE SET
                    expansion = excluded.expansion,
                    source_url = excluded.source_url,
                    is_curated = excluded.is_curated
            """, (acronym.upper(), expansion, source_url, is_curated))
            conn.commit()

    def get_all_acronyms(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM acronyms ORDER BY acronym")
            return [dict(row) for row in cursor.fetchall()]

    def log_data_quality_warning(self, warning_type: str, details: str, source_url: str = ""):
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO data_quality_warnings (warning_type, details, source_url, timestamp)
                VALUES (?, ?, ?, ?)
            """, (warning_type, details, source_url, datetime.now().isoformat()))
            conn.commit()

    def get_data_quality_warnings(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM data_quality_warnings ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_page_by_url(self, source_url: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pages WHERE source_url = ?", (source_url,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_pages(self, current_only: bool = False) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if current_only:
                cursor.execute("SELECT * FROM pages WHERE is_current = 1")
            else:
                cursor.execute("SELECT * FROM pages")
            return [dict(row) for row in cursor.fetchall()]

    def get_all_current_pages(self) -> List[Dict[str, Any]]:
        return self.get_all_pages(current_only=True)

    def set_page_current(self, source_url: str, is_current: int = 0, status: str = "REMOVED"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pages SET is_current = ?, status = ? WHERE source_url = ?
            """, (is_current, status, source_url))
            conn.commit()

    def get_all_documents(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents")
            return [dict(row) for row in cursor.fetchall()]
            
    def get_latest_crawl_report(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM crawl_reports ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get("details_json"):
                    result["details"] = json.loads(result["details_json"])
                return result
            return None

    def upsert_page(self, page_data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content_hash, version FROM pages WHERE source_url = ?", (page_data["source_url"],))
            existing = cursor.fetchone()

            if existing:
                page_id = existing["id"]
                cursor.execute("""
                    UPDATE pages SET
                        title = ?,
                        category = ?,
                        department = ?,
                        source_type = ?,
                        published_date = ?,
                        last_modified = ?,
                        last_checked = ?,
                        content_hash = ?,
                        version = ?,
                        is_current = ?,
                        status = ?,
                        superseded_by = ?,
                        filepath = ?,
                        error = ?,
                        clean_text = ?
                    WHERE id = ?
                """, (
                    page_data.get("title"),
                    page_data.get("category"),
                    page_data.get("department"),
                    page_data.get("source_type"),
                    page_data.get("published_date"),
                    page_data.get("last_modified"),
                    page_data.get("last_checked"),
                    page_data.get("content_hash"),
                    page_data.get("version", 1),
                    page_data.get("is_current", 1),
                    page_data.get("status", "UNCHANGED"),
                    page_data.get("superseded_by"),
                    page_data.get("filepath"),
                    page_data.get("error"),
                    page_data.get("clean_text"),
                    page_id
                ))
                return page_id
            else:
                cursor.execute("""
                    INSERT INTO pages (
                        source_url, title, category, department, source_type,
                        published_date, last_modified, last_checked, content_hash,
                        version, is_current, status, superseded_by, filepath, error, clean_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    page_data["source_url"],
                    page_data.get("title"),
                    page_data.get("category"),
                    page_data.get("department"),
                    page_data.get("source_type", "page"),
                    page_data.get("published_date"),
                    page_data.get("last_modified"),
                    page_data.get("last_checked"),
                    page_data.get("content_hash"),
                    page_data.get("version", 1),
                    page_data.get("is_current", 1),
                    page_data.get("status", "NEW"),
                    page_data.get("superseded_by"),
                    page_data.get("filepath"),
                    page_data.get("error"),
                    page_data.get("clean_text")
                ))
                return cursor.lastrowid

    def upsert_document(self, doc_data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM documents WHERE document_url = ?", (doc_data["document_url"],))
            existing = cursor.fetchone()

            if existing:
                doc_id = existing["id"]
                cursor.execute("""
                    UPDATE documents SET
                        link_text = ?,
                        parent_page_url = ?,
                        nearby_text = ?,
                        category = ?,
                        department = ?,
                        published_date = ?,
                        date_source = ?,
                        file_size = ?,
                        content_hash = ?,
                        version = ?,
                        last_checked = ?,
                        title = ?,
                        clean_text = ?,
                        status = ?,
                        filepath = ?,
                        ocr_flag = ?,
                        needs_review = ?
                    WHERE id = ?
                """, (
                    doc_data.get("link_text"),
                    doc_data.get("parent_page_url"),
                    doc_data.get("nearby_text"),
                    doc_data.get("category"),
                    doc_data.get("department"),
                    doc_data.get("published_date"),
                    doc_data.get("date_source"),
                    doc_data.get("file_size"),
                    doc_data.get("content_hash"),
                    doc_data.get("version", 1),
                    doc_data.get("last_checked"),
                    doc_data.get("title"),
                    doc_data.get("clean_text"),
                    doc_data.get("status", "discovered"),
                    doc_data.get("filepath"),
                    doc_data.get("ocr_flag", 0),
                    doc_data.get("needs_review", 0),
                    doc_id
                ))
                return doc_id
            else:
                cursor.execute("""
                    INSERT INTO documents (
                        document_url, link_text, parent_page_url, nearby_text, category,
                        department, published_date, date_source, file_size, content_hash,
                        version, last_checked, title, clean_text, status, filepath,
                        ocr_flag, needs_review
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc_data["document_url"],
                    doc_data.get("link_text"),
                    doc_data.get("parent_page_url"),
                    doc_data.get("nearby_text"),
                    doc_data.get("category"),
                    doc_data.get("department"),
                    doc_data.get("published_date"),
                    doc_data.get("date_source"),
                    doc_data.get("file_size"),
                    doc_data.get("content_hash"),
                    doc_data.get("version", 1),
                    doc_data.get("last_checked"),
                    doc_data.get("title"),
                    doc_data.get("clean_text"),
                    doc_data.get("status", "discovered"),
                    doc_data.get("filepath"),
                    doc_data.get("ocr_flag", 0),
                    doc_data.get("needs_review", 0)
                ))
                return cursor.lastrowid

    def save_crawl_report(self, report_data: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO crawl_reports (
                    timestamp, total_discovered, total_processed, total_failed,
                    total_skipped, total_pdfs, new_count, modified_count,
                    unchanged_count, removed_count, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data.get("timestamp"),
                report_data.get("total_discovered", 0),
                report_data.get("total_processed", 0),
                report_data.get("total_failed", 0),
                report_data.get("total_skipped", 0),
                report_data.get("total_pdfs", 0),
                report_data.get("new_count", 0),
                report_data.get("modified_count", 0),
                report_data.get("unchanged_count", 0),
                report_data.get("removed_count", 0),
                json.dumps(report_data.get("details", {}))
            ))
            conn.commit()

    def upsert_syllabus(self, s_data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Try to match by course_code, unit_number, regulation, branch
            cursor.execute("""
                SELECT id FROM syllabus 
                WHERE course_code = ? AND unit_number = ? AND regulation = ? AND branch = ?
            """, (s_data.get("course_code"), s_data.get("unit_number"), s_data.get("regulation"), s_data.get("branch")))
            existing = cursor.fetchone()

            if existing:
                s_id = existing["id"]
                cursor.execute("""
                    UPDATE syllabus SET
                        document_url = ?, year = ?, semester = ?, academic_year = ?,
                        course_title = ?, category = ?, credits = ?, ltp = ?,
                        unit_title = ?, topics = ?, textbooks = ?, outcomes = ?,
                        exam_scheme = ?, needs_review = ?, page_num = ?
                    WHERE id = ?
                """, (
                    s_data.get("document_url"), s_data.get("year"), s_data.get("semester"), s_data.get("academic_year"),
                    s_data.get("course_title"), s_data.get("category"), str(s_data.get("credits")), s_data.get("ltp"),
                    s_data.get("unit_title"), s_data.get("topics"), s_data.get("textbooks"), s_data.get("outcomes"),
                    s_data.get("exam_scheme"), s_data.get("needs_review", 0), s_data.get("page_num"),
                    s_id
                ))
                return s_id
            else:
                cursor.execute("""
                    INSERT INTO syllabus (
                        document_url, regulation, branch, year, semester, academic_year,
                        course_code, course_title, category, credits, ltp, unit_number,
                        unit_title, topics, textbooks, outcomes, exam_scheme, needs_review, page_num
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s_data.get("document_url"), s_data.get("regulation"), s_data.get("branch"),
                    s_data.get("year"), s_data.get("semester"), s_data.get("academic_year"),
                    s_data.get("course_code"), s_data.get("course_title"), s_data.get("category"),
                    str(s_data.get("credits")), s_data.get("ltp"), s_data.get("unit_number"),
                    s_data.get("unit_title"), s_data.get("topics"), s_data.get("textbooks"),
                    s_data.get("outcomes"), s_data.get("exam_scheme"), s_data.get("needs_review", 0),
                    s_data.get("page_num")
                ))
                return cursor.lastrowid

    # --- Faculty Directory Management Methods ---

    def upsert_faculty(self, f_data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO faculty (
                    name, designation, qualification, department, email,
                    photo_url, photo_path, profile_url, is_guest, is_hod,
                    source_url, last_checked, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, department) DO UPDATE SET
                    designation = excluded.designation,
                    qualification = excluded.qualification,
                    email = excluded.email,
                    photo_url = COALESCE(excluded.photo_url, faculty.photo_url),
                    photo_path = COALESCE(excluded.photo_path, faculty.photo_path),
                    profile_url = COALESCE(excluded.profile_url, faculty.profile_url),
                    is_guest = excluded.is_guest,
                    is_hod = excluded.is_hod,
                    source_url = excluded.source_url,
                    last_checked = excluded.last_checked,
                    is_active = excluded.is_active
            """, (
                f_data["name"].strip(),
                f_data.get("designation"),
                f_data.get("qualification"),
                f_data["department"].strip(),
                f_data.get("email"),
                f_data.get("photo_url"),
                f_data.get("photo_path"),
                f_data.get("profile_url"),
                f_data.get("is_guest", 0),
                f_data.get("is_hod", 0),
                f_data.get("source_url"),
                f_data.get("last_checked"),
                f_data.get("is_active", 1)
            ))
            conn.commit()
            return cursor.lastrowid

    def upsert_faculty_batch(self, records: List[Dict[str, Any]]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            count = 0
            for f_data in records:
                cursor.execute("""
                    INSERT INTO faculty (
                        name, designation, qualification, department, email,
                        photo_url, photo_path, profile_url, is_guest, is_hod,
                        source_url, last_checked, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name, department) DO UPDATE SET
                        designation = excluded.designation,
                        qualification = excluded.qualification,
                        email = excluded.email,
                        photo_url = COALESCE(excluded.photo_url, faculty.photo_url),
                        photo_path = COALESCE(excluded.photo_path, faculty.photo_path),
                        profile_url = COALESCE(excluded.profile_url, faculty.profile_url),
                        is_guest = excluded.is_guest,
                        is_hod = excluded.is_hod,
                        source_url = excluded.source_url,
                        last_checked = excluded.last_checked,
                        is_active = excluded.is_active
                """, (
                    f_data["name"].strip(),
                    f_data.get("designation"),
                    f_data.get("qualification"),
                    f_data["department"].strip(),
                    f_data.get("email"),
                    f_data.get("photo_url"),
                    f_data.get("photo_path"),
                    f_data.get("profile_url"),
                    f_data.get("is_guest", 0),
                    f_data.get("is_hod", 0),
                    f_data.get("source_url"),
                    f_data.get("last_checked"),
                    f_data.get("is_active", 1)
                ))
                count += 1
            conn.commit()
            return count

    def get_faculty(
        self,
        department: Optional[str] = None,
        search: Optional[str] = None,
        is_guest: Optional[int] = None,
        is_hod: Optional[int] = None,
        is_active: Optional[int] = 1
    ) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM faculty WHERE 1=1"
            params = []
            if is_active is not None:
                query += " AND is_active = ?"
                params.append(is_active)
            if department:
                query += " AND (department = ? OR department LIKE ?)"
                params.append(department)
                params.append(f"%{department}%")
            if search:
                pattern = f"%{search.strip()}%"
                query += " AND (name LIKE ? OR designation LIKE ? OR qualification LIKE ? OR email LIKE ?)"
                params.extend([pattern, pattern, pattern, pattern])
            if is_guest is not None:
                query += " AND is_guest = ?"
                params.append(is_guest)
            if is_hod is not None:
                query += " AND is_hod = ?"
                params.append(is_hod)
            query += " ORDER BY is_hod DESC, is_guest ASC, name ASC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_faculty_by_name(self, name: str, department: Optional[str] = None) -> List[Dict[str, Any]]:
        clean_name = name.strip()
        if not clean_name:
            return []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Exact LIKE match
            query = "SELECT * FROM faculty WHERE is_active = 1 AND LOWER(name) LIKE ?"
            params = [f"%{clean_name.lower()}%"]
            if department:
                query += " AND (department = ? OR department LIKE ?)"
                params.append(department)
                params.append(f"%{department}%")
            query += " ORDER BY is_hod DESC, name ASC"
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            if results:
                return results

            # 2. Vowel-trimmed variations (e.g. "kishore" -> "kishor", "srinivasa" -> "srinivas")
            trimmed_candidates = []
            name_lower = clean_name.lower()
            if name_lower.endswith("e") and len(name_lower) >= 4:
                trimmed_candidates.append(name_lower[:-1])
            if name_lower.endswith("a") and len(name_lower) >= 5:
                trimmed_candidates.append(name_lower[:-1])

            for cand in trimmed_candidates:
                c_query = "SELECT * FROM faculty WHERE is_active = 1 AND LOWER(name) LIKE ?"
                c_params = [f"%{cand}%"]
                if department:
                    c_query += " AND (department = ? OR department LIKE ?)"
                    c_params.append(department)
                    c_params.append(f"%{department}%")
                c_query += " ORDER BY is_hod DESC, name ASC"
                cursor.execute(c_query, c_params)
                c_res = [dict(row) for row in cursor.fetchall()]
                if c_res:
                    return c_res

            # 3. Normalized match (removes dots and spaces, e.g. "C. Sreedhar" matches "Dr. C.Sreedhar")
            norm_name = clean_name.lower().replace(".", "").replace(" ", "")
            if len(norm_name) >= 3:
                norm_query = """
                    SELECT * FROM faculty 
                    WHERE is_active = 1 
                    AND REPLACE(REPLACE(LOWER(name), '.', ''), ' ', '') LIKE ?
                """
                norm_params = [f"%{norm_name}%"]
                if department:
                    norm_query += " AND (department = ? OR department LIKE ?)"
                    norm_params.append(department)
                    norm_params.append(f"%{department}%")
                norm_query += " ORDER BY is_hod DESC, name ASC"
                cursor.execute(norm_query, norm_params)
                norm_results = [dict(row) for row in cursor.fetchall()]
                if norm_results:
                    return norm_results

            # 4. Token & Fuzzy matching against faculty records
            all_fac = self.get_faculty(department=department, is_active=1)
            q_tokens = [t for t in re.split(r'[\s\.]+', clean_name.lower()) if len(t) >= 3 and t not in ('dr', 'sri', 'smt', 'mr', 'mrs', 'ms', 'prof')]
            if not q_tokens:
                return []

            scored = []
            for f in all_fac:
                f_tokens = [t for t in re.split(r'[\s\.]+', f['name'].lower()) if len(t) >= 3 and t not in ('dr', 'sri', 'smt', 'mr', 'mrs', 'ms', 'prof')]
                score = 0
                for qt in q_tokens:
                    for ft in f_tokens:
                        if qt == ft:
                            score += 10
                        elif len(ft) >= 4 and len(qt) >= 4 and (ft.startswith(qt) or qt.startswith(ft)):
                            score += 8
                        elif difflib.SequenceMatcher(None, qt, ft).ratio() >= 0.82:
                            score += 7
                if score >= 7:
                    scored.append((score, f))

            if scored:
                scored.sort(key=lambda x: (x[0], x[1].get('is_hod', 0)), reverse=True)
                return [x[1] for x in scored]

            return []

    def get_hod(self, department: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM faculty 
                WHERE is_active = 1 AND is_hod = 1 AND (department = ? OR department LIKE ?)
                ORDER BY id ASC LIMIT 1
            """, (department, f"%{department}%"))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_departments_with_faculty(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT department FROM faculty WHERE is_active = 1 ORDER BY department ASC")
            return [row["department"] for row in cursor.fetchall()]

    def mark_missing_faculty_inactive(self, department: str, active_names: List[str]) -> int:
        if not active_names:
            return 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in active_names)
            cursor.execute(f"""
                UPDATE faculty SET is_active = 0
                WHERE department = ? AND name NOT IN ({placeholders})
            """, [department] + active_names)
            conn.commit()
            return cursor.rowcount

    # --- Answer Cache Methods ---

    def get_cached_answer(self, normalized_query: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached response if present and younger than 24 hours (86400 seconds)."""
        import time
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT response_json, created_at FROM answer_cache WHERE normalized_query = ?", (normalized_query,))
            row = cursor.fetchone()
            if not row:
                return None
            now = time.time()
            if now - float(row["created_at"]) > 86400.0:
                # Expired after 24h
                cursor.execute("DELETE FROM answer_cache WHERE normalized_query = ?", (normalized_query,))
                conn.commit()
                return None
            try:
                data = json.loads(row["response_json"])
                data["from_cache"] = True
                return data
            except Exception:
                return None

    def set_cached_answer(self, normalized_query: str, response: Dict[str, Any], created_at: Optional[float] = None) -> None:
        """Stores response in cache if response_type is not NOT_FOUND or CLARIFY."""
        resp_type = response.get("response_type")
        if resp_type in ("NOT_FOUND", "CLARIFY"):
            return
        import time
        timestamp = created_at if created_at is not None else time.time()
        # Clean response dict of non-serializable fields if any
        clean_resp = {k: v for k, v in response.items() if k not in ("timings",)}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO answer_cache (normalized_query, response_json, created_at)
                VALUES (?, ?, ?)
            """, (normalized_query, json.dumps(clean_resp), timestamp))
            conn.commit()

    def clear_answer_cache(self) -> int:
        """Clears all answers in the SQLite answer cache and returns count of rows deleted."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM answer_cache")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM answer_cache")
            conn.commit()
            return count

    # --- Syllabus Search for Study Mode ---

    def search_syllabus_subject(self, query: str) -> Optional[Dict[str, Any]]:
        """Searches the syllabus table for a matching subject and returns its units and document_url."""
        import re
        q_lower = query.lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT course_title, course_code, document_url FROM syllabus WHERE course_title IS NOT NULL")
            courses = cursor.fetchall()
            
            matched_course = None
            for c in courses:
                c_title = (c["course_title"] or "").lower()
                c_code = (c["course_code"] or "").lower()
                acronym_match = re.search(r'\(([^)]+)\)', c_title)
                acronym = acronym_match.group(1).lower() if acronym_match else ""
                
                clean_title = re.sub(r'\(.*?\)', '', c_title).strip()
                if (clean_title and clean_title in q_lower) or (acronym and re.search(rf'\b{re.escape(acronym)}\b', q_lower)) or (c_code and c_code in q_lower):
                    matched_course = c
                    break
                    
                c_words = set(w for w in clean_title.split() if len(w) > 3)
                q_words = set(w for w in q_lower.split() if len(w) > 3)
                if c_words and len(c_words.intersection(q_words)) >= 2:
                    matched_course = c
                    break
                    
            if not matched_course:
                cursor.execute("""
                    SELECT course_title, course_code, document_url 
                    FROM syllabus 
                    WHERE LOWER(unit_title) LIKE ? OR LOWER(topics) LIKE ?
                    LIMIT 1
                """, (f"%{query}%", f"%{query}%"))
                matched_course = cursor.fetchone()

            if matched_course:
                cursor.execute("""
                    SELECT unit_number, unit_title, topics, document_url
                    FROM syllabus
                    WHERE course_title = ?
                    ORDER BY unit_number ASC
                """, (matched_course["course_title"],))
                units = [dict(row) for row in cursor.fetchall()]
                return {
                    "course_title": matched_course["course_title"],
                    "course_code": matched_course["course_code"],
                    "document_url": matched_course["document_url"] or (units[0]["document_url"] if units else None),
                    "units": [u["unit_title"] for u in units if u.get("unit_title")]
                }
            return None


if __name__ == "__main__":
    db = DatabaseManager()
    print("Database initialized successfully at:", db.db_path)
