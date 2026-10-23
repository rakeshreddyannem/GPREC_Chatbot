import sys
import tempfile
import sqlite3
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database import DatabaseManager
from src.notice_parser import NoticeParser
from src.notice_ingest import extract_deadline_date, clean_notice_title, ingest_notices_from_documents
from src.rag_pipeline import RAGPipeline


@pytest.fixture
def temp_db():
    """Provides a fresh isolated database for notice ingestion testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    db = DatabaseManager(db_path=db_path)
    yield db
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass


SAMPLE_DOCUMENTS = [
    # 1. Standard notice with published date in text & metadata
    {
        "document_url": "https://www.gprec.ac.in/examsection/btech_iv_sem_tt_2026.pdf",
        "link_text": "B.Tech IV Sem Examination Timetable March 2026",
        "parent_page_url": "https://www.gprec.ac.in/notice-board/",
        "nearby_text": "Published on 15-02-2026. B.Tech IV Sem Examination Timetable March 2026 for regular students.",
        "category": "Examinations",
        "department": "General",
        "published_date": "2026-02-15T00:00:00",
        "date_source": "nearby_text",
        "last_checked": "2026-10-23T15:00:00"
    },
    # 2. Revaluation notice with deadline ("last date for submission is ...")
    {
        "document_url": "https://www.gprec.ac.in/examsection/revaluation_notification_nov2026.pdf",
        "link_text": "Revaluation Notification for B.Tech II Sem - 01-11-2026",
        "parent_page_url": "https://www.gprec.ac.in/notice-board/",
        "nearby_text": "Published on 01-11-2026. Last date for submission of revaluation application is 20-11-2026 with prescribed fee.",
        "category": "Examinations",
        "department": "General",
        "published_date": "2026-11-01T00:00:00",
        "date_source": "link_text",
        "last_checked": "2026-10-23T15:00:00"
    },
    # 3. Notice with NO DATE at all (missing date must stay NULL)
    {
        "document_url": "https://www.gprec.ac.in/examsection/malpractice_rules.pdf",
        "link_text": "Malpractice Examination Notification and Student Guidelines",
        "parent_page_url": "https://www.gprec.ac.in/academics/examinations/instructions-to-students/",
        "nearby_text": "General instructions and malpractice penalties during college examinations without any specified date.",
        "category": "Examinations",
        "department": "General",
        "published_date": None,
        "date_source": None,
        "last_checked": "2026-10-23T15:00:00"
    },
    # 4. Notice with deadline ("on or before ...")
    {
        "document_url": "https://www.gprec.ac.in/examsection/mtech_thesis_submission_circular.pdf",
        "link_text": "M.Tech Project Thesis Submission Circular",
        "parent_page_url": "https://www.gprec.ac.in/notice-board/",
        "nearby_text": "All final year M.Tech students must submit the project dissertation on or before 15-12-2026 to the HOD.",
        "category": "Circular",
        "department": "General",
        "published_date": "2026-10-10T00:00:00",
        "date_source": "nearby_text",
        "last_checked": "2026-10-23T15:00:00"
    },
    # 5. Notice with deadline ("due date ...")
    {
        "document_url": "https://www.gprec.ac.in/examsection/exam_fee_notification_nov_2026.pdf",
        "link_text": "Exam Fee Notification for I, III, V Semesters",
        "parent_page_url": "https://www.gprec.ac.in/notice-board/",
        "nearby_text": "Published on 20-10-2026. Regular and Supplementary exam fee due date is 05-11-2026 without late fee.",
        "category": "Fee Notification",
        "department": "General",
        "published_date": "2026-10-20T00:00:00",
        "date_source": "nearby_text",
        "last_checked": "2026-10-23T15:00:00"
    }
]


def test_notice_date_parsing_and_null_preservation(temp_db):
    """
    Assert that:
    1. Published dates are parsed correctly as YYYY-MM-DD.
    2. A missing date stays NULL (None) in SQLite and is never guessed or set to today.
    """
    for doc in SAMPLE_DOCUMENTS:
        temp_db.upsert_document(doc)

    report = ingest_notices_from_documents(temp_db)
    assert report["notices_found"] == 5
    assert report["notices_with_date"] == 4
    assert report["notices_without_date"] == 1
    assert report["notices_with_deadline"] == 3

    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check row 1
        cursor.execute("SELECT published_date, deadline_date FROM notices WHERE document_url = ?", (SAMPLE_DOCUMENTS[0]["document_url"],))
        r1 = cursor.fetchone()
        assert r1["published_date"] == "2026-02-15"
        assert r1["deadline_date"] is None

        # Check row 2 (has deadline)
        cursor.execute("SELECT published_date, deadline_date FROM notices WHERE document_url = ?", (SAMPLE_DOCUMENTS[1]["document_url"],))
        r2 = cursor.fetchone()
        assert r2["published_date"] == "2026-11-01"
        assert r2["deadline_date"] == "2026-11-20"

        # Check row 3 (NO DATE -> MUST BE NULL)
        cursor.execute("SELECT published_date, date_source, deadline_date FROM notices WHERE document_url = ?", (SAMPLE_DOCUMENTS[2]["document_url"],))
        r3 = cursor.fetchone()
        assert r3["published_date"] is None
        assert r3["date_source"] is None
        assert r3["deadline_date"] is None


def test_deadline_dates_parsing(temp_db):
    """
    Assert that:
    1. Deadlines next to 'last date', 'on or before', and 'due date' are parsed correctly.
    2. Deadlines table is populated.
    """
    for doc in SAMPLE_DOCUMENTS:
        temp_db.upsert_document(doc)

    ingest_notices_from_documents(temp_db)

    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deadlines ORDER BY deadline_date ASC")
        deadlines = [dict(r) for r in cursor.fetchall()]
        
        # We expect 3 deadlines: 2026-11-05 (Row 5), 2026-11-20 (Row 2), 2026-12-15 (Row 4)
        assert len(deadlines) == 3
        deadline_dates = [d["deadline_date"] for d in deadlines]
        assert "2026-11-05" in deadline_dates
        assert "2026-11-20" in deadline_dates
        assert "2026-12-15" in deadline_dates


def test_idempotent_ingestion_no_duplicates(temp_db):
    """
    Assert that:
    Re-running ingest multiple times never creates duplicate rows in notices or deadlines tables.
    """
    for doc in SAMPLE_DOCUMENTS:
        temp_db.upsert_document(doc)

    # First run
    ingest_notices_from_documents(temp_db)

    with temp_db.get_connection() as conn:
        c1 = conn.cursor().execute("SELECT COUNT(*) FROM notices").fetchone()[0]
        d1 = conn.cursor().execute("SELECT COUNT(*) FROM deadlines").fetchone()[0]
        assert c1 == 5
        assert d1 == 3

    # Second run (re-running)
    ingest_notices_from_documents(temp_db)

    with temp_db.get_connection() as conn:
        c2 = conn.cursor().execute("SELECT COUNT(*) FROM notices").fetchone()[0]
        d2 = conn.cursor().execute("SELECT COUNT(*) FROM deadlines").fetchone()[0]
        assert c2 == 5, "Duplicate notices were created!"
        assert d2 == 3, "Duplicate deadlines were created!"

    # Third run (re-running)
    ingest_notices_from_documents(temp_db)

    with temp_db.get_connection() as conn:
        c3 = conn.cursor().execute("SELECT COUNT(*) FROM notices").fetchone()[0]
        d3 = conn.cursor().execute("SELECT COUNT(*) FROM deadlines").fetchone()[0]
        assert c3 == 5
        assert d3 == 3


def test_pipeline_retrieval_from_notices(temp_db):
    """
    Assert that questions about deadlines, timetables, and latest notices:
    1. Answer from the notices table first, sorted by published_date.
    2. Include 'based on the notice dated D'.
    3. If nothing matches, return NOT_FOUND without falling back to old chunks.
    """
    for doc in SAMPLE_DOCUMENTS:
        temp_db.upsert_document(doc)

    ingest_notices_from_documents(temp_db)

    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline.db = temp_db

    # 1. Timetable question
    ans_tt = pipeline.answer_question("What is the B.Tech IV Sem exam timetable?")
    assert ans_tt["response_type"] == "ANSWERED"
    assert "based on the notice dated" in ans_tt["answer"].lower()
    assert "2026-02-15" in ans_tt["answer"]
    assert "b.tech iv sem examination timetable" in ans_tt["answer"].lower()

    # 2. Revaluation deadline question
    ans_dl = pipeline.answer_question("What is the deadline for revaluation?")
    assert ans_dl["response_type"] == "ANSWERED"
    assert "based on the notice dated" in ans_dl["answer"].lower()
    assert "2026-11-20" in ans_dl["answer"]

    # 3. Query for a notice topic that does not exist in the notices table
    ans_nf = pipeline.answer_question("What is the latest exam notice for Marine Engineering?")
    assert ans_nf["response_type"] == "NOT_FOUND"
    assert "i couldn't find this information" in ans_nf["answer"].lower() or "not available" in ans_nf["answer"].lower()
