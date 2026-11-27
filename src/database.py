import sys
import os
import sqlite3
import json
import re
import difflib
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    _initialized_paths = set()

    def __init__(self, db_path: Optional[Path] = None, force_init: bool = False, require_exists: bool = False):
        self.db_path = Path(db_path or config.DB_PATH)
        if require_exists and (not self.db_path.exists() or self.db_path.stat().st_size == 0):
            raise FileNotFoundError(f"Database file missing or empty at: {self.db_path}")
        resolved_key = str(self.db_path.resolve())
        if force_init or resolved_key not in DatabaseManager._initialized_paths:
            self.init_db()
            DatabaseManager._initialized_paths.add(resolved_key)

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

            # 12. Syllabus Sources Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS syllabus_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT,
                    program TEXT,
                    scheme TEXT,
                    kind TEXT,
                    link_text TEXT,
                    url TEXT,
                    local_path TEXT,
                    content_hash TEXT,
                    status TEXT,
                    reason TEXT,
                    last_checked TEXT,
                    UNIQUE(branch, url)
                )
            """)

            # 13. Timetable Subjects Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS timetable_subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT,
                    year INTEGER,
                    semester INTEGER,
                    section TEXT,
                    academic_year TEXT,
                    course_code TEXT,
                    subject_name TEXT,
                    faculty TEXT,
                    source_file TEXT,
                    page_num INTEGER,
                    needs_review INTEGER DEFAULT 0,
                    is_current_semester INTEGER DEFAULT 1
                )
            """)

            # 14. Feedback Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    message_idx INTEGER,
                    question TEXT,
                    answer TEXT,
                    rating INTEGER,
                    feedback_text TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 15. Chat Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_query TEXT,
                    response_text TEXT,
                    response_type TEXT,
                    confidence TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 16. Subject Notes Table (Semester-wise study materials, lecture PDFs, question banks)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subject_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT NOT NULL,
                    semester INTEGER NOT NULL,
                    subject_folder TEXT NOT NULL,
                    course_title TEXT NOT NULL,
                    unit_number INTEGER,
                    title TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    file_type TEXT,
                    category TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(branch, semester, subject_folder, filename)
                )
            """)

            try:
                cursor.execute("ALTER TABLE syllabus_sources ADD COLUMN content_hash TEXT")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE timetable_subjects ADD COLUMN is_current_semester INTEGER DEFAULT 1")
            except Exception:
                pass

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_faculty_dept ON faculty(department)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_faculty_name ON faculty(name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_sources_branch ON syllabus_sources(branch)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_sources_status ON syllabus_sources(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_upsert_lookup ON syllabus(branch, regulation, course_code, unit_number)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_timetable_lookup ON timetable_subjects(branch, semester, course_code)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON chat_logs(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subject_notes_lookup ON subject_notes(branch, semester, course_title)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_subject_notes_unit ON subject_notes(branch, semester, unit_number)")
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

            try:
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to commit database table migrations (read-mostly mode): {e}")

        # Seeding and cleanup: wrap in try-except so read-only/reset disks don't crash
        try:
            self._cleanup_old_seed()
            self._seed_curated_acronyms()
            self._seed_verified_facts()
            self._seed_entity_directory()
            self._seed_default_notices()
            self.sync_subject_notes()
        except Exception as e:
            logger.warning(f"Database seed initialization skipped (read-mostly mode): {e}")

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

            # 4. Fix branch-specific upper semester syllabus rows incorrectly tagged as 'COMMON'
            try:
                cursor.execute("UPDATE syllabus SET branch = 'CSM' WHERE branch = 'COMMON' AND document_url LIKE '%AI&ML%'")
                cursor.execute("UPDATE syllabus SET branch = 'CSD' WHERE branch = 'COMMON' AND document_url LIKE '%CSE(DS)%'")
                cursor.execute("UPDATE syllabus SET branch = 'CE' WHERE branch = 'COMMON' AND (document_url LIKE '%CE-S-23%' OR document_url LIKE '%S-20-CE%')")
                cursor.execute("UPDATE syllabus SET branch = 'ECE' WHERE branch = 'COMMON' AND (document_url LIKE '%ECE S-23%' OR document_url LIKE '%S-20-ECE%')")
                cursor.execute("UPDATE syllabus SET branch = 'EEE' WHERE branch = 'COMMON' AND (document_url LIKE '%EEE S-23%' OR document_url LIKE '%EEE-S23%' OR (document_url LIKE '%S-20-EEE%' AND year > 1))")
                cursor.execute("UPDATE syllabus SET branch = 'CSB' WHERE branch = 'COMMON' AND (document_url LIKE '%CSBS%' OR document_url LIKE '%CSB%')")
                cursor.execute("UPDATE syllabus SET branch = 'CSE' WHERE branch = 'COMMON' AND (document_url LIKE '%S-20-CSE%' OR document_url LIKE '%CSE-S23%')")
                cursor.execute("UPDATE syllabus SET branch = 'ME' WHERE branch = 'COMMON' AND (document_url LIKE '%S-20-ME%' OR document_url LIKE '%ME S-23%' OR document_url LIKE '%ME-S23%')")
                cursor.execute("UPDATE syllabus SET branch = 'CST' WHERE branch = 'COMMON' AND document_url LIKE '%CST%'")
            except Exception:
                pass

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
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT response_json, created_at FROM answer_cache WHERE normalized_query = ?", (normalized_query,))
                row = cursor.fetchone()
                if not row:
                    return None
                now = time.time()
                if now - float(row["created_at"]) > 86400.0:
                    # Expired after 24h
                    try:
                        cursor.execute("DELETE FROM answer_cache WHERE normalized_query = ?", (normalized_query,))
                        conn.commit()
                    except Exception as de:
                        logger.warning(f"Failed to delete expired cache entry (ignored): {de}")
                    return None
                try:
                    data = json.loads(row["response_json"])
                    data["from_cache"] = True
                    return data
                except Exception:
                    return None
        except Exception as e:
            logger.warning(f"Failed to read from answer_cache (ignored): {e}")
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
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO answer_cache (normalized_query, response_json, created_at)
                    VALUES (?, ?, ?)
                """, (normalized_query, json.dumps(clean_resp), timestamp))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to write to answer_cache (disk read-only/reset mode): {e}")

    def clear_answer_cache(self) -> int:
        """Clears all answers in the SQLite answer cache and returns count of rows deleted."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM answer_cache")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM answer_cache")
                conn.commit()
                return count
        except Exception as e:
            logger.warning(f"Failed to clear answer_cache (ignored): {e}")
            return 0

    # --- Syllabus Search for Study Mode ---

    def search_syllabus_subject(self, query: str) -> Optional[Dict[str, Any]]:
        """Searches the syllabus table for a matching subject and returns its units and document_url."""
        import re
        from src.curated_links import get_branch_latest_syllabus_pdf, is_cross_branch_url
        q_lower = query.lower()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT course_title, course_code, branch, semester, document_url FROM syllabus WHERE course_title IS NOT NULL")
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
                    SELECT course_title, course_code, branch, semester, document_url 
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
                c_branch = matched_course["branch"]
                c_sem = matched_course["semester"]
                raw_url = matched_course["document_url"] or (units[0]["document_url"] if units else None)
                if c_branch and c_branch != "COMMON" and (not raw_url or is_cross_branch_url(raw_url, c_branch)):
                    raw_url = get_branch_latest_syllabus_pdf(c_branch, c_sem)

                return {
                    "course_title": matched_course["course_title"],
                    "course_code": matched_course["course_code"],
                    "branch": c_branch,
                    "document_url": raw_url,
                    "units": [u["unit_title"] for u in units if u.get("unit_title")]
                }
            return None

    def get_syllabus_branches(self) -> List[str]:
        """Returns all 10 canonical branch codes from faculty_parser DEPARTMENT_CONFIGS."""
        from src.faculty_parser import DEPARTMENT_CONFIGS
        return [d["short_code"] for d in DEPARTMENT_CONFIGS]

    def get_syllabus_schemes(self, branch: str) -> List[str]:
        """
        Returns distinct schemes/regulations for a branch from syllabus table,
        defaulting to the newest one that has data. Year 1 uses COMMON syllabus schemes.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            target_b = 'COMMON' if branch.upper() == 'H&S' else branch
            cursor.execute("""
                SELECT DISTINCT regulation 
                FROM syllabus 
                WHERE (branch = ? OR (branch = 'COMMON' AND semester IN (1, 2)))
                  AND regulation IS NOT NULL AND TRIM(regulation) != ''
            """, (target_b,))
            rows = [r["regulation"] for r in cursor.fetchall()]
            if not rows:
                cursor.execute("""
                    SELECT DISTINCT regulation FROM syllabus 
                    WHERE regulation IS NOT NULL AND TRIM(regulation) != ''
                """)
                rows = [r["regulation"] for r in cursor.fetchall()]

            def scheme_sort_key(s: str) -> int:
                nums = re.findall(r'\d+', str(s))
                if nums:
                    for n in nums:
                        if len(n) == 4:
                            return int(n)
                    return int(nums[0])
                return 0

            # Sort newest first, with 2023 preferred as primary active scheme if present
            unique_schemes = list(set(rows))
            # Sort descending by year
            sorted_schemes = sorted(unique_schemes, key=scheme_sort_key, reverse=True)
            # If 2023 is present, ensure 2023 is default if 2026 only has drafts
            if "2023" in sorted_schemes and sorted_schemes[0] == "2026":
                # Check if 2023 has significantly more rows for this branch
                cursor.execute("SELECT COUNT(*) FROM syllabus WHERE (branch = ? OR branch = 'COMMON') AND regulation = '2023'", (target_b,))
                c_2023 = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM syllabus WHERE (branch = ? OR branch = 'COMMON') AND regulation = '2026'", (target_b,))
                c_2026 = cursor.fetchone()[0]
                if c_2023 > c_2026:
                    sorted_schemes.remove("2023")
                    sorted_schemes.insert(0, "2023")

            return sorted_schemes

    def get_syllabus_semesters(self, branch: str, scheme: Optional[str] = None) -> List[int]:
        """Returns distinct semesters for a branch (and scheme) that actually have rows."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            target_b = 'COMMON' if branch.upper() == 'H&S' else branch
            if scheme:
                cursor.execute("""
                    SELECT DISTINCT semester 
                    FROM syllabus 
                    WHERE (branch = ? OR (branch = 'COMMON' AND semester IN (1, 2)))
                      AND regulation = ?
                      AND semester IS NOT NULL 
                    ORDER BY semester ASC
                """, (target_b, scheme))
                sems = [int(row["semester"]) for row in cursor.fetchall() if row["semester"] is not None]
                if sems:
                    return sems

            cursor.execute("""
                SELECT DISTINCT semester 
                FROM syllabus 
                WHERE (branch = ? OR (branch = 'COMMON' AND semester IN (1, 2))) 
                  AND semester IS NOT NULL 
                ORDER BY semester ASC
            """, (target_b,))
            return [int(row["semester"]) for row in cursor.fetchall() if row["semester"] is not None]

    def get_syllabus_courses(
        self, 
        branch: str, 
        semester: Optional[int] = None,
        scheme: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns distinct courses for given branch, semester, and scheme (including COMMON year 1 courses)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            target_b = 'COMMON' if (branch.upper() == 'H&S' or (semester is not None and semester in (1, 2))) else branch
            
            conditions = ["course_title IS NOT NULL"]
            params = []
            if semester is not None and semester in (1, 2):
                conditions.append("branch = 'COMMON'")
            elif branch.upper() == 'H&S':
                conditions.append("(branch = 'COMMON' OR branch = 'H&S')")
            else:
                conditions.append("(branch = ? OR (branch = 'COMMON' AND semester IN (1, 2)))")
                params.append(branch)

            if semester is not None:
                conditions.append("semester = ?")
                params.append(semester)

            if scheme:
                conditions.append("regulation = ?")
                params.append(scheme)

            where_sql = " AND ".join(conditions)
            cursor.execute(f"""
                SELECT DISTINCT course_code, course_title, credits, ltp, document_url, regulation, needs_review
                FROM syllabus 
                WHERE {where_sql}
                ORDER BY course_code ASC, course_title ASC
            """, tuple(params))
            rows = [dict(row) for row in cursor.fetchall()]

            if not rows and scheme:
                # Try without scheme restriction if empty
                conditions_no_scheme = [c for c in conditions if "regulation = ?" not in c]
                params_no_scheme = params[:-1] if scheme in params else params
                cursor.execute(f"""
                    SELECT DISTINCT course_code, course_title, credits, ltp, document_url, regulation, needs_review
                    FROM syllabus 
                    WHERE {" AND ".join(conditions_no_scheme)}
                    ORDER BY course_code ASC, course_title ASC
                """, tuple(params_no_scheme))
                rows = [dict(row) for row in cursor.fetchall()]

            from src.curated_links import get_branch_latest_syllabus_pdf, is_cross_branch_url
            for r in rows:
                doc_u = r.get("document_url")
                if not doc_u or is_cross_branch_url(doc_u, branch):
                    r["document_url"] = get_branch_latest_syllabus_pdf(branch, semester)
            return rows

    def get_syllabus_units_for_course(
        self, 
        branch: Optional[str] = None, 
        semester: Optional[int] = None, 
        course_title: Optional[str] = None, 
        course_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns all unit rows for the specified course."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params = []
            if course_code:
                conditions.append("course_code = ?")
                params.append(course_code)
            elif course_title:
                conditions.append("LOWER(course_title) = LOWER(?)")
                params.append(course_title)
            if branch:
                if semester is not None and semester > 2:
                    conditions.append("branch = ?")
                    params.append(branch)
                else:
                    conditions.append("(branch = ? OR (branch = 'COMMON' AND (semester IN (1, 2) OR semester IS NULL)))")
                    params.append(branch)
            if semester is not None:
                conditions.append("semester = ?")
                params.append(semester)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"""
                SELECT id, regulation, branch, year, semester, course_code, course_title,
                       category, credits, ltp, unit_number, unit_title, topics,
                       textbooks, outcomes, exam_scheme, needs_review, document_url, page_num
                FROM syllabus
                {where_clause}
                ORDER BY unit_number ASC
            """
            rows = [dict(row) for row in cursor.fetchall()]

            # Fallback 1: If no rows found with branch & semester, search by course_code
            if not rows and course_code and course_code not in ("OTHER", "CUSTOM", ""):
                if branch:
                    cursor.execute("""
                        SELECT id, regulation, branch, year, semester, course_code, course_title,
                               category, credits, ltp, unit_number, unit_title, topics,
                               textbooks, outcomes, exam_scheme, needs_review, document_url, page_num
                        FROM syllabus
                        WHERE UPPER(course_code) = UPPER(?) AND (branch = ? OR (branch = 'COMMON' AND (semester IN (1, 2) OR semester IS NULL)))
                        ORDER BY unit_number ASC
                    """, (course_code, branch))
                else:
                    cursor.execute("""
                        SELECT id, regulation, branch, year, semester, course_code, course_title,
                               category, credits, ltp, unit_number, unit_title, topics,
                               textbooks, outcomes, exam_scheme, needs_review, document_url, page_num
                        FROM syllabus
                        WHERE UPPER(course_code) = UPPER(?)
                        ORDER BY unit_number ASC
                    """, (course_code,))
                all_code_rows = [dict(row) for row in cursor.fetchall()]
                if all_code_rows:
                    units_by_num = {}
                    for r in all_code_rows:
                        u_num = r.get("unit_number")
                        if u_num not in units_by_num or len(r.get("topics") or "") > len(units_by_num[u_num].get("topics") or ""):
                            units_by_num[u_num] = r
                    rows = [units_by_num[k] for k in sorted(units_by_num.keys(), key=lambda x: (x is None, x or 0))]

            # Fallback 2: If still no rows, search by normalized course_title within branch
            if not rows and course_title:
                clean_t = re.sub(r'([A-Za-z]{3,})(of|through|and|for)([A-Z])', r'\1 \2 \3', course_title)
                clean_t = re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', clean_t)
                clean_t = re.sub(r'([A-Za-z])([&])', r'\1 & ', clean_t)
                clean_t = re.sub(r'([&])([A-Za-z])', r' & \1', clean_t)
                clean_t = re.sub(r'\s+', ' ', clean_t).strip()
                norm_target = re.sub(r'[^a-z0-9]', '', clean_t.lower())

                if branch:
                    if semester is not None and semester > 2:
                        cursor.execute("""
                            SELECT id, regulation, branch, year, semester, course_code, course_title,
                                   category, credits, ltp, unit_number, unit_title, topics,
                                   textbooks, outcomes, exam_scheme, needs_review, document_url, page_num
                            FROM syllabus
                            WHERE branch = ?
                            ORDER BY unit_number ASC
                        """, (branch,))
                    else:
                        cursor.execute("""
                            SELECT id, regulation, branch, year, semester, course_code, course_title,
                                   category, credits, ltp, unit_number, unit_title, topics,
                                   textbooks, outcomes, exam_scheme, needs_review, document_url, page_num
                            FROM syllabus
                            WHERE branch = ? OR (branch = 'COMMON' AND (semester IN (1, 2) OR semester IS NULL))
                            ORDER BY unit_number ASC
                        """, (branch,))
                else:
                    cursor.execute("""
                        SELECT id, regulation, branch, year, semester, course_code, course_title,
                               category, credits, ltp, unit_number, unit_title, topics,
                               textbooks, outcomes, exam_scheme, needs_review, document_url, page_num
                        FROM syllabus
                        ORDER BY unit_number ASC
                    """)
                all_syl = [dict(row) for row in cursor.fetchall()]
                matching = []
                for r in all_syl:
                    s_norm = re.sub(r'[^a-z0-9]', '', (r.get("course_title") or "").lower())
                    if len(s_norm) >= 3 and len(norm_target) >= 3:
                        if norm_target == s_norm:
                            matching.append(r)
                        elif len(norm_target) >= 5 and norm_target in s_norm:
                            matching.append(r)
                        elif len(s_norm) >= 5 and s_norm in norm_target:
                            matching.append(r)
                if matching:
                    units_by_num = {}
                    for r in matching:
                        u_num = r.get("unit_number")
                        if u_num not in units_by_num or len(r.get("topics") or "") > len(units_by_num[u_num].get("topics") or ""):
                            units_by_num[u_num] = r
                    rows = [units_by_num[k] for k in sorted(units_by_num.keys(), key=lambda x: (x is None, x or 0))]

            if branch:
                from src.curated_links import get_branch_latest_syllabus_pdf, is_cross_branch_url
                for r in rows:
                    doc_u = r.get("document_url")
                    if not doc_u or is_cross_branch_url(doc_u, branch):
                        r["document_url"] = get_branch_latest_syllabus_pdf(branch, semester)
            return rows

    # --- Syllabus Sources & Upsert Helpers ---

    def upsert_syllabus_source(self, data: Dict[str, Any]) -> int:
        """Upserts a row into syllabus_sources table keyed by (branch, url)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO syllabus_sources (
                    branch, program, scheme, kind, link_text, url, local_path, content_hash, status, reason, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(branch, url) DO UPDATE SET
                    program = excluded.program,
                    scheme = excluded.scheme,
                    kind = excluded.kind,
                    link_text = excluded.link_text,
                    local_path = COALESCE(excluded.local_path, syllabus_sources.local_path),
                    content_hash = COALESCE(excluded.content_hash, syllabus_sources.content_hash),
                    status = CASE 
                        WHEN syllabus_sources.status IN ('parsed', 'downloaded') AND excluded.status = 'found' 
                        THEN syllabus_sources.status 
                        ELSE excluded.status 
                    END,
                    reason = CASE 
                        WHEN syllabus_sources.status IN ('parsed', 'downloaded') AND excluded.status = 'found' 
                        THEN syllabus_sources.reason 
                        ELSE excluded.reason 
                    END,
                    last_checked = excluded.last_checked
            """, (
                data.get("branch"),
                data.get("program"),
                data.get("scheme"),
                data.get("kind"),
                data.get("link_text"),
                data.get("url"),
                data.get("local_path"),
                data.get("content_hash"),
                data.get("status"),
                data.get("reason"),
                data.get("last_checked")
            ))
            conn.commit()
            return cursor.lastrowid

    def get_syllabus_sources(self, branch: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns syllabus_sources rows filtered optionally by branch and/or status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params = []
            if branch:
                conditions.append("branch = ?")
                params.append(branch)
            if status:
                conditions.append("status = ?")
                params.append(status)
            where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
            cursor.execute(f"SELECT * FROM syllabus_sources{where_sql} ORDER BY id ASC", params)
            return [dict(row) for row in cursor.fetchall()]

    def upsert_syllabus_entry(self, entry: Dict[str, Any]) -> int:
        """Upserts a course/unit row into the syllabus table keyed by (branch, regulation, course_code, unit_number)."""
        branch = entry.get("branch")
        regulation = entry.get("regulation")
        course_code = entry.get("course_code")
        unit_number = entry.get("unit_number")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if unit_number is not None:
                cursor.execute("""
                    SELECT id FROM syllabus 
                    WHERE branch = ? AND regulation = ? AND course_code = ? AND unit_number = ?
                """, (branch, regulation, course_code, unit_number))
            else:
                cursor.execute("""
                    SELECT id FROM syllabus 
                    WHERE branch = ? AND regulation = ? AND course_code = ? AND unit_number IS NULL
                """, (branch, regulation, course_code))
            row = cursor.fetchone()

            if row:
                row_id = row["id"]
                cursor.execute("""
                    UPDATE syllabus SET
                        document_url = ?, year = ?, semester = ?, academic_year = ?,
                        course_title = ?, category = ?, credits = ?, ltp = ?,
                        unit_title = ?, topics = ?, textbooks = ?, outcomes = ?,
                        exam_scheme = ?, needs_review = ?, page_num = ?
                    WHERE id = ?
                """, (
                    entry.get("document_url"), entry.get("year"), entry.get("semester"), entry.get("academic_year"),
                    entry.get("course_title"), entry.get("category"), entry.get("credits"), entry.get("ltp"),
                    entry.get("unit_title"), entry.get("topics"), entry.get("textbooks"), entry.get("outcomes"),
                    entry.get("exam_scheme"), entry.get("needs_review", 0), entry.get("page_num"),
                    row_id
                ))
                conn.commit()
                return row_id
            else:
                cursor.execute("""
                    INSERT INTO syllabus (
                        document_url, regulation, branch, year, semester, academic_year,
                        course_code, course_title, category, credits, ltp,
                        unit_number, unit_title, topics, textbooks, outcomes,
                        exam_scheme, needs_review, page_num
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.get("document_url"), entry.get("regulation"), entry.get("branch"),
                    entry.get("year"), entry.get("semester"), entry.get("academic_year"),
                    entry.get("course_code"), entry.get("course_title"), entry.get("category"),
                    entry.get("credits"), entry.get("ltp"), entry.get("unit_number"),
                    entry.get("unit_title"), entry.get("topics"), entry.get("textbooks"),
                    entry.get("outcomes"), entry.get("exam_scheme"), entry.get("needs_review", 0),
                    entry.get("page_num")
                ))
                conn.commit()
                return cursor.lastrowid

    def insert_timetable_subject(self, entry: Dict[str, Any]) -> int:
        """Inserts a subject record into timetable_subjects."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO timetable_subjects (
                    branch, year, semester, section, academic_year,
                    course_code, subject_name, faculty, source_file,
                    page_num, needs_review, is_current_semester
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("branch"),
                entry.get("year"),
                entry.get("semester"),
                entry.get("section"),
                entry.get("academic_year"),
                entry.get("course_code"),
                entry.get("subject_name"),
                entry.get("faculty"),
                entry.get("source_file"),
                entry.get("page_num"),
                entry.get("needs_review", 0),
                entry.get("is_current_semester", 1)
            ))
            conn.commit()
            return cursor.lastrowid

    def get_current_subjects(self, branch: Optional[str] = None, year_or_semester: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Retrieves current semester subjects from timetable_subjects for Subject Assistance.
        Filters by branch and year/semester, only returning rows where is_current_semester = 1.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, branch, year, semester, section, academic_year,
                       course_code, subject_name, faculty, source_file, page_num,
                       needs_review, is_current_semester
                FROM timetable_subjects
                WHERE is_current_semester = 1
            """
            params = []
            if branch:
                query += " AND UPPER(branch) = UPPER(?)"
                params.append(branch.strip())

            if year_or_semester is not None:
                val_str = str(year_or_semester).strip()
                sem_match = re.search(r'\b(?:sem|semester)?\s*([1-8])\b', val_str, re.IGNORECASE)
                yr_match = re.search(r'\b(?:year|yr)?\s*([1-4])\b', val_str, re.IGNORECASE)

                try:
                    num = int(val_str)
                    if num > 4:
                        query += " AND semester = ?"
                        params.append(num)
                    else:
                        query += " AND (semester = ? OR year = ?)"
                        params.extend([num, num])
                except ValueError:
                    if "sem" in val_str.lower() and sem_match:
                        query += " AND semester = ?"
                        params.append(int(sem_match.group(1)))
                    elif "year" in val_str.lower() and yr_match:
                        query += " AND year = ?"
                        params.append(int(yr_match.group(1)))
                    elif sem_match:
                        query += " AND (semester = ? OR year = ?)"
                        params.extend([int(sem_match.group(1)), int(sem_match.group(1))])

            query += " ORDER BY branch, semester, course_code, subject_name"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_timetable_subjects(self) -> List[Dict[str, Any]]:
        """Returns all rows from timetable_subjects."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, branch, year, semester, section, academic_year,
                       course_code, subject_name, faculty, source_file, page_num,
                       needs_review, is_current_semester
                FROM timetable_subjects
                ORDER BY branch, semester, section, subject_name
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_subject_assistance_subjects(
        self, 
        branch: str, 
        semester: int, 
        scheme: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves running subjects from timetable_subjects first (marked '[Running this semester]'),
        followed by remaining subjects for that semester from the syllabus table.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Running timetable subjects for this branch and semester
            tt_query = """
                SELECT DISTINCT course_code, subject_name, faculty, needs_review
                FROM timetable_subjects
                WHERE is_current_semester = 1
            """
            tt_params = []
            if branch.upper() == "H&S":
                tt_query += " AND (year = 1 OR semester IN (1, 2))"
            else:
                tt_query += " AND UPPER(branch) = UPPER(?)"
                tt_params.append(branch)
                
            if semester in (1, 2):
                tt_query += " AND (semester = ? OR year = 1)"
                tt_params.append(semester)
            else:
                yr = (semester + 1) // 2
                tt_query += " AND (semester = ? OR (semester IS NULL AND year = ?))"
                tt_params.extend([semester, yr])
                
            tt_query += " ORDER BY course_code, subject_name"
            cursor.execute(tt_query, tuple(tt_params))
            tt_rows = [dict(r) for r in cursor.fetchall()]

            # 2. Syllabus subjects
            syl_courses = self.get_syllabus_courses(branch, semester, scheme)

            # Combine and deduplicate
            combined = []
            seen_codes = set()
            seen_titles = set()

            def normalize_title(t: str) -> str:
                return re.sub(r'[^a-z0-9]', '', (t or '').lower())

            # A. Timetable subjects first (running this semester)
            for r in tt_rows:
                code = (r.get("course_code") or "").strip()
                name = (r.get("subject_name") or "").strip()
                norm_name = normalize_title(name)
                
                # Check for syllabus match to pull metadata
                matched_syl = None
                if code:
                    matched_syl = next((c for c in syl_courses if (c.get("course_code") or "").upper() == code.upper()), None)
                if not matched_syl and norm_name:
                    matched_syl = next((c for c in syl_courses if normalize_title(c.get("course_title", "")) == norm_name or norm_name in normalize_title(c.get("course_title", ""))), None)
                
                # Global syllabus match fallback for audit/institutional courses (e.g. AC402, HSM202)
                if not matched_syl and code and code not in ("OTHER", "CUSTOM", ""):
                    cursor.execute("""
                        SELECT course_code, course_title, credits, ltp, document_url, regulation
                        FROM syllabus
                        WHERE UPPER(course_code) = UPPER(?) AND course_title IS NOT NULL
                        LIMIT 1
                    """, (code,))
                    g_row = cursor.fetchone()
                    if g_row:
                        matched_syl = dict(g_row)

                clean_name = re.sub(r'([A-Za-z]{3,})(of|through|and|for)([A-Z])', r'\1 \2 \3', name)
                clean_name = re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', clean_name)
                clean_name = re.sub(r'([A-Za-z])([&])', r'\1 & ', clean_name)
                clean_name = re.sub(r'([&])([A-Za-z])', r' & \1', clean_name)
                clean_name = re.sub(r'\s+', ' ', clean_name).strip()

                credits = matched_syl.get("credits") if matched_syl else ""
                ltp = matched_syl.get("ltp") if matched_syl else ""
                doc_url = matched_syl.get("document_url") if matched_syl else ""
                regulation = matched_syl.get("regulation") if matched_syl else (scheme or "")
                actual_title = matched_syl.get("course_title") if matched_syl else clean_name
                actual_code = matched_syl.get("course_code") if (matched_syl and matched_syl.get("course_code")) else code

                label_code = f"{actual_code} - " if actual_code else ""
                display_label = f"{label_code}{actual_title}"

                if actual_code and actual_code.upper() in seen_codes:
                    continue
                if norm_name and norm_name in seen_titles:
                    continue
                if matched_syl and normalize_title(matched_syl.get("course_title", "")) in seen_titles:
                    continue

                if actual_code:
                    seen_codes.add(actual_code.upper())
                if norm_name:
                    seen_titles.add(norm_name)
                if matched_syl:
                    seen_titles.add(normalize_title(matched_syl.get("course_title", "")))

                combined.append({
                    "course_code": actual_code,
                    "course_title": actual_title,
                    "credits": credits,
                    "ltp": ltp,
                    "document_url": doc_url,
                    "regulation": regulation,
                    "is_running": True,
                    "display_label": display_label,
                    "needs_review": r.get("needs_review", 0)
                })

            # B. If no timetable entries exist for this semester, fall back to syllabus subjects
            if not combined:
                for sc in syl_courses:
                    c_code = (sc.get("course_code") or "").strip()
                    c_title = (sc.get("course_title") or "").strip()
                    norm_title = normalize_title(c_title)

                    if c_code and c_code.upper() in seen_codes:
                        continue
                    if norm_title and norm_title in seen_titles:
                        continue

                    label_code = f"{c_code} - " if c_code else ""
                    display_label = f"{label_code}{c_title}"

                    combined.append({
                        "course_code": c_code,
                        "course_title": c_title,
                        "credits": sc.get("credits", ""),
                        "ltp": sc.get("ltp", ""),
                        "document_url": sc.get("document_url", ""),
                        "regulation": sc.get("regulation", scheme or ""),
                        "is_running": False,
                        "display_label": display_label,
                        "needs_review": sc.get("needs_review", 0)
                    })

            return combined

    def save_feedback(
        self, 
        question: str, 
        answer: str, 
        rating: int, 
        message_idx: int = 0, 
        session_id: str = "",
        feedback_text: str = ""
    ) -> Optional[int]:
        """Saves user rating (+1 or -1) and feedback for a generated response without crashing if disk is reset/read-only."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO feedback (session_id, message_idx, question, answer, rating, feedback_text)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, message_idx, question, answer, rating, feedback_text))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.warning(f"Failed to save feedback to database (read-mostly/disk-reset mode): {e}")
            return None

    def log_chat(
        self,
        query: str,
        response: str,
        response_type: str = "ANSWERED",
        confidence: str = "High",
        session_id: str = ""
    ) -> Optional[int]:
        """Safely logs a chat interaction without crashing if disk is reset or read-only."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chat_logs (session_id, user_query, response_text, response_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, query, response, response_type, confidence))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.warning(f"Failed to log chat interaction (disk read-only/reset mode): {e}")
            return None

    def get_last_data_update_date(self) -> str:
        """Returns the most recent data update date from crawl reports, notices, or documents."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 1. Check latest crawl report timestamp
                cursor.execute("SELECT timestamp FROM crawl_reports ORDER BY report_id DESC LIMIT 1")
                row = cursor.fetchone()
                if row and row[0]:
                    dt_str = str(row[0])
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        return dt.strftime("%B %d, %Y")
                    except Exception:
                        return dt_str[:10]

                # 2. Check notices published date
                cursor.execute("SELECT MAX(published_date) FROM notices WHERE published_date IS NOT NULL AND published_date != ''")
                row = cursor.fetchone()
                if row and row[0]:
                    dt_str = str(row[0])
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(dt_str)
                        return dt.strftime("%B %d, %Y")
                    except Exception:
                        return dt_str[:10]

                # 3. Check pages last checked
                cursor.execute("SELECT MAX(last_checked) FROM pages WHERE last_checked IS NOT NULL AND last_checked != ''")
                row = cursor.fetchone()
                if row and row[0]:
                    return str(row[0])[:10]
        except Exception as e:
            logger.warning(f"Could not retrieve last data update date: {e}")
        return "October 2026"

    def get_feedback_count(self) -> Dict[str, int]:
        """Returns aggregate positive and negative feedback counts."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating")
                counts = {1: 0, -1: 0}
                for row in cursor.fetchall():
                    counts[row["rating"]] = row["cnt"]
                return counts
        except Exception as e:
            logger.warning(f"Failed to get feedback counts: {e}")
            return {1: 0, -1: 0}

    # -------------------------------------------------------------
    # SUBJECT NOTES & STUDY MATERIALS
    # -------------------------------------------------------------

    def sync_subject_notes(self, notes_dir: Optional[Path] = None) -> int:
        """
        Scans Subject_notes_pdfs_semester_Wise directory and indexes all semester-wise
        subject notes, lecture PDFs, and question banks into the subject_notes table.
        """
        target_dir = Path(notes_dir or getattr(config, "NOTES_DIR", config.BASE_DIR / "Subject_notes_pdfs_semester_Wise"))
        if not target_dir.exists():
            return 0

        folder_map = {
            # 3rd Sem
            ("EEE", 3, "electromagnetic field"): {
                "primary_title": "ELECTROMAGNETIC FIELD THEORY (EMF)",
                "aliases": ["ELECTROMAGNETIC FIELDS (EMF)", "ELECTROMAGNETIC FIELD THEORY", "EMF"]
            },
            ("EEE", 3, "universal human values"): {
                "primary_title": "UNIVERSAL HUMAN VALUES",
                "aliases": ["UNIVERSAL HUMAN VALUES - 2 (UHV2)", "UHV", "UHV2"]
            },
            # 4th Sem
            ("EEE", 4, "analog circuits"): {
                "primary_title": "ANALOG CIRCUITS (AC)",
                "aliases": ["ANALOG CIRCUITS", "AC", "ANALOG AND DIGITAL CIRCUITS LAB (ADC (P))"]
            },
            ("EEE", 4, "control systems"): {
                "primary_title": "CONTROL SYSTEMS ENGINEERING (CSE)",
                "aliases": ["CONTROL SYSTEMS DESIGN (CSD)", "CONTROL SYSTEMS", "CS", "CSE", "DIGITAL CONTROL SYSTEMS (DCS)"]
            },
            ("EEE", 4, "induction and synchronous machines"): {
                "primary_title": "INDUCTION AND SYNCHRONOUS MACHINES (ISM)",
                "aliases": ["ELECTRICAL MACHINES - II (EMC-II)", "ELECTRICAL MACHINES-II", "ISM", "ELECTRICAL MACHINES-I"]
            },
            # 5th Sem
            ("EEE", 5, "power systems-2"): {
                "primary_title": "POWER SYSTEMS - II (PS-II)",
                "aliases": ["POWER SYSTEMS-II (PS2)", "POWER SYSTEMS-II", "POWER SYSTEMS-I (PS-I)", "POWER SYSTEMS-I (PS1)", "PS-II", "PS2", "PS1"]
            },
            ("EEE", 5, "introduction to python programming"): {
                "primary_title": "INTRODUCTION TO PYTHON PROGRAMMING (IPP)",
                "aliases": ["INTRODUCTION TO PYTHON PROGRAMMING (IPP(P))", "PYTHON PROGRAMMING", "IPP", "SPY"]
            },
            ("EEE", 5, "introduction to quantum technologies"): {
                "primary_title": "INTRODUCTION TO QUANTUM MECHANICS (IQM)",
                "aliases": ["MATHEMATICAL FOUNDATION OF QUANTUM TECHNOLOGIES (MFQT)", "QUANTUM COMPUTING (QC)", "QUANTUM TECHNOLOGIES", "IQTA", "IQM"]
            },
            # 6th Sem
            ("EEE", 6, "electical measuring instruments"): {
                "primary_title": "ELECTRICAL MEASUREMENTS AND INSTRUMENTATION (EMI)",
                "aliases": ["ELECTRICAL & ELECTRONIC MEASURING INSTRUMENTS (EEMI)", "EMI", "EEMI", "MEASURING INSTRUMENTS"]
            },
            ("EEE", 6, "switch gear and protection"): {
                "primary_title": "SWITCHGEAR AND PROTECTION (SGP)",
                "aliases": ["SWITCHGEAR AND PROTECTION", "SGP"]
            },
            # 7th Sem
            ("EEE", 7, "elements of digital signal processing"): {
                "primary_title": "ELEMENTS OF DIGITAL SIGNAL PROCESSING (EDSP)",
                "aliases": ["DIGITAL SIGNAL PROCESSING (DSP)", "EDSP", "DSP"]
            },
            ("EEE", 7, "management science"): {
                "primary_title": "MANAGEMENT SCIENCE (MS)",
                "aliases": ["MANAGEMENT SCIENCE", "MS"]
            },
            ("EEE", 7, "power systems operation and control"): {
                "primary_title": "POWER SYSTEM OPERATION AND CONTROL (PSOC)",
                "aliases": ["POWER SYSTEM OPERATION AND CONTROL", "PSOC", "SMART GRID TECHNOLOGIES (SGT)", "SMART GRIDS"]
            },
            ("EEE", 7, "utilization of electrical energy(uee)"): {
                "primary_title": "UTILIZATION OF ELECTRICAL ENERGY (UEE)",
                "aliases": ["UTILIZATION OF ELECRICAL POWER (UEP)", "UEE", "UEP"]
            }
        }

        roman_map = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5}

        def _extract_unit(fname: str) -> Optional[int]:
            m = re.search(r'\bunit[\s\-_]*([1-5]|i{1,3}|iv|v)\b', fname, re.IGNORECASE)
            if m:
                val = m.group(1).lower()
                return roman_map.get(val, int(val) if val.isdigit() else None)
            m_digit = re.search(r'\bunit[\s\-_]*([1-5])', fname, re.IGNORECASE)
            if m_digit:
                return int(m_digit.group(1))
            return None

        def _get_category(fname: str) -> str:
            fl = fname.lower()
            if any(k in fl for k in ['question', 'model', 'bank', 'important']):
                return "Question Bank / Model Paper"
            if any(k in fl for k in ['text book', 'textbook']):
                return "Textbook / Reference Book"
            if any(k in fl for k in ['code', 'matplot', 'numpy', 'ex codes']):
                return "Practical / Code Examples"
            if any(k in fl for k in ['unit', 'notes', 'meterial', 'material', 'lecture']):
                return "Unit Lecture Notes"
            return "Topic Notes / Reference"

        count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for root, dirs, files in os.walk(target_dir):
                    for f in files:
                        full_p = Path(root) / f
                        try:
                            rel_p = full_p.relative_to(target_dir)
                        except Exception:
                            continue
                        parts = rel_p.parts
                        if len(parts) < 3:
                            continue
                        branch = parts[0].upper()
                        sem_str = parts[1]
                        sem_num_m = re.search(r'\d+', sem_str)
                        sem_num = int(sem_num_m.group(0)) if sem_num_m else 1
                        subject_folder = parts[2]

                        map_key = (branch, sem_num, subject_folder.lower().strip())
                        info = folder_map.get(map_key, {})
                        course_title = info.get("primary_title", subject_folder.upper())

                        unit_num = _extract_unit(f)
                        category = _get_category(f)
                        ext = os.path.splitext(f)[1].lower().lstrip(".")
                        size_bytes = full_p.stat().st_size
                        title = os.path.splitext(f)[0].replace('_', ' ').replace('-', ' ').strip()

                        # Store relative posix path for portability
                        rel_to_base = full_p.relative_to(config.BASE_DIR).as_posix() if config.BASE_DIR in full_p.parents else str(full_p.as_posix())

                        cursor.execute("""
                            INSERT INTO subject_notes (
                                branch, semester, subject_folder, course_title, unit_number,
                                title, filename, filepath, file_size, file_type, category, description
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(branch, semester, subject_folder, filename) DO UPDATE SET
                                course_title=excluded.course_title,
                                unit_number=excluded.unit_number,
                                title=excluded.title,
                                filepath=excluded.filepath,
                                file_size=excluded.file_size,
                                file_type=excluded.file_type,
                                category=excluded.category
                        """, (
                            branch, sem_num, subject_folder, course_title, unit_num,
                            title, f, rel_to_base, size_bytes, ext, category,
                            f"Official {branch} study notes and lecture materials for {course_title} (Semester {sem_num})"
                        ))
                        count += 1
                conn.commit()
        except Exception as e:
            logger.warning(f"Error syncing subject notes: {e}")
        return count

    def get_subject_notes(
        self, 
        branch: str, 
        semester: int, 
        course_title: Optional[str] = None, 
        unit_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves indexed subject notes, lecture PDFs, and question banks for a branch and semester.
        Matches canonical course titles, folder names, and subject abbreviations.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM subject_notes WHERE branch = ? AND semester = ?"
                params = [branch.upper(), int(semester)]

                if unit_number is not None:
                    query += " AND unit_number = ?"
                    params.append(int(unit_number))

                query += " ORDER BY CASE WHEN unit_number IS NULL THEN 999 ELSE unit_number END ASC, title ASC"
                cursor.execute(query, params)
                rows = [dict(r) for r in cursor.fetchall()]

                # Add formatted file size and absolute path
                for r in rows:
                    sb = r.get("file_size", 0)
                    if sb >= 1024 * 1024:
                        r["formatted_size"] = f"{sb / (1024 * 1024):.1f} MB"
                    else:
                        r["formatted_size"] = f"{max(1, sb // 1024)} KB"

                    r["file_type"] = (r.get("file_type") or "").lstrip(".")

                    # Resolve absolute path with robust fallbacks
                    fp = r.get("filepath", "")
                    p = Path(fp)
                    if not p.is_absolute():
                        candidates = [
                            config.BASE_DIR / p,
                            Path.cwd() / p,
                            config.BASE_DIR / "Subject_notes_pdfs_semester_Wise" / Path(fp).name,
                        ]
                        p = next((cand for cand in candidates if cand.exists()), config.BASE_DIR / p)
                    r["abs_filepath"] = str(p.resolve())
                    r["file_exists"] = p.exists()

                if not course_title:
                    return rows

                # Filter matching course_title
                ct_clean = course_title.lower().replace("-", " ").replace("(", " ").replace(")", " ")
                ct_tokens = [w for w in ct_clean.split() if len(w) > 2]

                matched = []
                for r in rows:
                    row_ct = r["course_title"].lower().replace("-", " ").replace("(", " ").replace(")", " ")
                    row_sf = r["subject_folder"].lower().replace("-", " ").replace("(", " ").replace(")", " ")

                    # 1. Direct equality or substring containment
                    if r["course_title"].lower() == course_title.lower() or row_sf in ct_clean or ct_clean in row_sf:
                        matched.append(r)
                        continue

                    # 2. Token overlap
                    overlap = [t for t in ct_tokens if t in row_ct or t in row_sf]
                    if len(overlap) >= 2 or (len(ct_tokens) == 1 and len(overlap) == 1):
                        matched.append(r)

                return matched
        except Exception as e:
            logger.warning(f"Error querying subject_notes: {e}")
            return []

    def get_available_note_courses_for_semester(self, branch: str, semester: int) -> List[Dict[str, Any]]:
        """Returns distinct courses that have notes uploaded in this semester."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT course_title, subject_folder, COUNT(*) as note_count,
                           SUM(file_size) as total_size,
                           GROUP_CONCAT(DISTINCT category) as categories
                    FROM subject_notes
                    WHERE branch = ? AND semester = ?
                    GROUP BY course_title, subject_folder
                    ORDER BY course_title ASC
                """, (branch.upper(), int(semester)))
                results = []
                for r in cursor.fetchall():
                    item = dict(r)
                    ts = item.get("total_size", 0) or 0
                    item["formatted_size"] = f"{ts / (1024 * 1024):.1f} MB" if ts >= 1024 * 1024 else f"{max(1, ts // 1024)} KB"
                    results.append(item)
                return results
        except Exception as e:
            logger.warning(f"Error querying available note courses: {e}")
            return []

    def get_note_by_id(self, note_id: int) -> Optional[Dict[str, Any]]:
        """Fetches a single note record by its ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM subject_notes WHERE id = ?", (int(note_id),))
                row = cursor.fetchone()
                if row:
                    res = dict(row)
                    sb = res.get("file_size", 0)
                    res["formatted_size"] = f"{sb / (1024 * 1024):.1f} MB" if sb >= 1024 * 1024 else f"{max(1, sb // 1024)} KB"
                    p = Path(res.get("filepath", ""))
                    if not p.is_absolute():
                        candidates = [
                            config.BASE_DIR / p,
                            Path.cwd() / p,
                            config.BASE_DIR / "Subject_notes_pdfs_semester_Wise" / Path(res.get("filepath", "")).name,
                        ]
                        p = next((cand for cand in candidates if cand.exists()), config.BASE_DIR / p)
                    res["abs_filepath"] = str(p.resolve())
                    res["file_exists"] = p.exists()
                    return res
        except Exception as e:
            logger.warning(f"Error fetching note by id {note_id}: {e}")
        return None


if __name__ == "__main__":
    db = DatabaseManager()
    print("Database initialized successfully at:", db.db_path)
    print("Last update date:", db.get_last_data_update_date())
