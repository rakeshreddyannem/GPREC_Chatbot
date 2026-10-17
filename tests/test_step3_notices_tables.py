import pytest
import sys
from pathlib import Path
import fitz

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.pdf_loader import PDFProcessor
from src.notice_parser import NoticeParser
from src.database import DatabaseManager
from src.reliability import AmbiguityDetector, ResponseType

def test_pdf_table_extraction_formatting():
    """Verify that table extractor produces clean pipe-delimited rows without mushing columns."""
    processor = PDFProcessor()
    
    # Create a synthetic PDF with tabular data
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Subject\tDate\tSession\nPower Systems-II\t15-04-2026\t10:00 AM to 1:00 PM\nControl Systems\t18-04-2026\t10:00 AM to 1:00 PM")
    
    extracted_rows = processor.extract_tables_from_page(page)
    doc.close()
    
    assert len(extracted_rows) >= 2
    # Check pipe-separated format
    for row in extracted_rows:
        assert "|" in row
    # Check header and content rows
    assert any("Subject" in row for row in extracted_rows)
    assert any("15-04-2026" in row or "Power Systems" in row for row in extracted_rows)

def test_scanned_pdf_needs_manual_review_flag(tmp_path):
    """Verify that a scanned PDF with no text layer sets needs_manual_review = True."""
    processor = PDFProcessor(download_dir=tmp_path)
    
    # Create a blank/scanned PDF without text
    pdf_path = tmp_path / "scanned_doc.pdf"
    doc = fitz.open()
    doc.new_page()  # blank page
    doc.save(str(pdf_path))
    doc.close()
    
    pages = processor.extract_document_data(
        pdf_path, 
        parent_url="https://gprec.ac.in/circulars", 
        link_text="Scanned Notice Circular",
        nearby_heading="Examination Announcements"
    )
    
    assert len(pages) == 1
    assert pages[0]["needs_manual_review"] is True
    assert pages[0]["is_scanned"] is True
    assert pages[0]["parent_url"] == "https://gprec.ac.in/circulars"
    assert pages[0]["link_text"] == "Scanned Notice Circular"
    assert pages[0]["nearby_heading"] == "Examination Announcements"

def test_notice_parser_classification():
    """Verify rule-based regex parsing for notice types, program, semester, and regulation."""
    # 1. Timetable notice
    t_notice = NoticeParser.parse_notice(
        title="B.Tech IV Sem (R20) Regular & Supplementary Examinations Timetable - April 2026",
        text="Schedule of End Examinations for April 2026.",
        source_page="http://examcell.gprec.ac.in/",
        published_date="2026-03-20"
    )
    assert t_notice["notice_type"] == "timetable"
    assert t_notice["program"] == "B.Tech"
    assert t_notice["semester"] == "IV Sem"
    assert t_notice["scheme_regulation"] == "R20"
    assert t_notice["exam_month_year"] == "April 2026"
    assert t_notice["published_date"] == "2026-03-20"

    # 2. Seating plan
    s_notice = NoticeParser.parse_notice(
        title="Seating Arrangement and Hall Allocation for End Examinations April 2026",
        text="Room numbers and roll numbers allocation list."
    )
    assert s_notice["notice_type"] == "seating plan"

    # 3. Revaluation
    r_notice = NoticeParser.parse_notice(
        title="Notification for Revaluation and Script Verification of B.Tech End Exams",
        text="Last date for revaluation is 15-03-2026."
    )
    assert r_notice["notice_type"] == "revaluation"

    # 4. Hall ticket
    h_notice = NoticeParser.parse_notice(
        title="Hall Tickets Issuance for April 2026 Examinations"
    )
    assert h_notice["notice_type"] == "hall ticket"

    # 5. Fee notification
    f_notice = NoticeParser.parse_notice(
        title="B.Tech Tuition Fee Structure Prescribed by APHERMC for 2024-25 & 2025-26",
        text="Tuition fee details for Convenor and Management quota."
    )
    assert f_notice["notice_type"] == "fee notification"

def test_database_notices_operations(tmp_path):
    """Verify database notices schema, seeding, filtering, and retrieval."""
    test_db_path = tmp_path / "test_gprec.db"
    db = DatabaseManager(db_path=test_db_path)
    
    # 1. Check default seeded notices
    notices = db.get_notices()
    assert len(notices) >= 10
    
    # 2. Filter by timetable
    timetables = db.get_notices(notice_type="timetable")
    assert len(timetables) >= 4
    for t in timetables:
        assert t["notice_type"] == "timetable"
        
    # 3. Filter by program and semester
    iv_sem = db.get_notices(program="B.Tech", semester="IV Sem")
    assert len(iv_sem) >= 1
    assert iv_sem[0]["semester"] == "IV Sem"
    
    # 4. Search notices
    results = db.search_notices("APHERMC")
    assert len(results) >= 1
    assert "Tuition Fee" in results[0]["title"]

def test_exam_timetable_ambiguity_step3():
    """Verify that generic timetable queries trigger CLARIFY with program/semester options."""
    amb = AmbiguityDetector.check_ambiguity("detail information about the exam time table")
    assert amb is not None
    assert amb["response_type"] == ResponseType.CLARIFY
    assert "timetable" in amb["question"].lower()
    assert "B.Tech I Year" in amb["options"]
    assert any("IV Sem" in opt or "IV Year" in opt for opt in amb["options"])

def test_fee_structure_verified_facts():
    """Verify that verified_facts contains APHERMC tuition fee structure with academic year."""
    db = DatabaseManager()
    facts = db.get_matching_verified_facts("what is fee structure of EEE department")
    assert len(facts) >= 1
    
    # Combine values
    combined_val = " ".join([f["value"] for f in facts])
    assert "APHERMC" in combined_val
    assert "70,000" in combined_val or "Convenor Quota" in combined_val
    assert "2024-25" in combined_val or "2025-26" in combined_val
