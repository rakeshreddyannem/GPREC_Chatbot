import sys
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest
from src.database import DatabaseManager
from src.reliability import ResponseType
from src.rag_pipeline import (
    has_instruction_echo,
    get_instruction_leak_count,
    increment_instruction_leak_count,
    reset_instruction_leak_count,
    handle_notices_query,
    is_notices_query,
    compute_confidence,
    SAFE_FALLBACK_TEXT,
    RAGPipeline
)
from app import get_confidence_badge_html


# --- 1. Instruction Echo Leak Detection & Counter Tests ---

def test_has_instruction_echo_5_leaked_samples():
    """Verify that 5 distinct instruction-leaked responses are detected by has_instruction_echo."""
    sample_1 = "Analyze the Request: Role: GPREC AI Student Assistant. Constraints: Grounding only. User Question: Fee structure."
    sample_2 = "Constraints:\n1. Grounding\n2. Forbid Inference\nAnswer: Dr. Kishor is the head of the department."
    sample_3 = "Role: You are the GPREC student assistant.\nTask: Answer the student query about exam fees."
    sample_4 = "Grounding: Answer ONLY using the official GPREC sources.\nRule 1: Never infer details not present in context."
    sample_5 = "Verified Facts Priority: Verified by admin on 2026-10-12.\nRule 9 (Fee structure): ₹70,000 per academic year."

    assert has_instruction_echo(sample_1) is True
    assert has_instruction_echo(sample_2) is True
    assert has_instruction_echo(sample_3) is True
    assert has_instruction_echo(sample_4) is True
    assert has_instruction_echo(sample_5) is True


def test_has_instruction_echo_3_normal_answers():
    """Verify that 3 clean normal student-facing answers are NOT flagged as instruction echoes."""
    sample_1 = "The HOD of the Electrical and Electronics Engineering department is **Dr. G. Kishor**."
    sample_2 = "The tuition fee for B.Tech programmes is ₹70,000 per academic year as approved by APHERMC."
    sample_3 = "Semester examinations for Scheme-2023 will commence from 15 November 2026."

    assert has_instruction_echo(sample_1) is False
    assert has_instruction_echo(sample_2) is False
    assert has_instruction_echo(sample_3) is False


def test_instruction_leak_counter_operations():
    """Verify leak counter increments and resets properly."""
    reset_instruction_leak_count()
    assert get_instruction_leak_count() == 0

    increment_instruction_leak_count()
    increment_instruction_leak_count()
    assert get_instruction_leak_count() == 2

    reset_instruction_leak_count()
    assert get_instruction_leak_count() == 0


def test_rag_pipeline_retry_and_safe_fallback_on_repeated_leak(monkeypatch):
    """Verify that when the LLM returns instruction echo twice, the pipeline logs counter and returns SAFE_FALLBACK_TEXT."""
    reset_instruction_leak_count()

    mock_db = MagicMock()
    mock_db.get_cached_answer.return_value = None
    mock_db.search_entity_directory.return_value = []
    mock_db.get_matching_verified_facts.return_value = []

    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline.db = mock_db
    pipeline.retrieve = MagicMock(return_value=[{"title": "Doc", "content": "Sample content", "source_url": "https://gprec.ac.in", "score": 0.5}])
    pipeline.model_name = "mock_model"

    mock_client = MagicMock()
    # Mock LLM to return leaked text on both attempts
    leaked_resp = MagicMock()
    leaked_resp.choices = [MagicMock(message=MagicMock(content="Analyze the Request: Role: assistant. Constraints: grounding."))]
    mock_client.chat.completions.create.return_value = leaked_resp
    pipeline.client = mock_client

    import config
    monkeypatch.setattr(config, "LLM_PROVIDER", "openrouter")

    res = pipeline.answer_question("What is the admission procedure?")
    assert res["answer"] == SAFE_FALLBACK_TEXT
    assert res["confidence"] == "Low"
    assert get_instruction_leak_count() >= 2


# --- 2. Notice Query Direct Routing Tests ---

@pytest.fixture
def temp_notices_db(tmp_path):
    """Creates a temporary sqlite DB with a notices table for notice routing tests."""
    db_file = tmp_path / "test_notices.db"
    manager = DatabaseManager(db_path=db_file)
    with manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notices (title, notice_type, program, semester, published_date, department, attachment_urls, is_active)
            VALUES 
            ('M.Tech IV Sem Examination Circular', 'exam', 'M.Tech', 'IV Sem', '2026-10-23', 'Examination', 'https://www.gprec.ac.in/circulars/mtech_iv.pdf', 1),
            ('B.Tech End Exam Timetable Nov 2026', 'timetable', 'B.Tech', 'V Sem', '2026-10-15', 'General', 'https://www.gprec.ac.in/circulars/timetable_nov.pdf', 1)
        """)
        conn.commit()
    return manager


def test_is_notices_query_detector():
    """Verify is_notices_query matches exam notices, latest notices, timetable, and last date."""
    assert is_notices_query("List the latest exam notices")[0] is True
    assert is_notices_query("what are the latest notices?")[0] is True
    assert is_notices_query("show exam timetable for 3rd semester")[0] is True
    assert is_notices_query("what is the last date to pay exam fee?")[0] is True
    assert is_notices_query("Who is the HOD of Civil Engineering?")[0] is False


def test_handle_notices_query_returns_required_fields_without_llm(temp_notices_db):
    """Verify notice query returns (title, date, department, Open document link) with High confidence directly from table."""
    res = handle_notices_query("List the latest exam notices", temp_notices_db)
    assert res is not None
    assert res["response_type"] == ResponseType.ANSWERED
    assert res["confidence"] == "High"
    answer = res["answer"]

    # Must contain title, date, department, and [Open document](url)
    assert "M.Tech IV Sem Examination Circular" in answer
    assert "Date: 2026-10-23" in answer
    assert "Department: Examination" in answer
    assert "[Open document](https://www.gprec.ac.in/circulars/mtech_iv.pdf)" in answer


def test_handle_notices_query_no_match_returns_one_sentence(temp_notices_db):
    """Verify when the notices table has no match, it returns exactly one sentence."""
    res = handle_notices_query("timetable for astronomy department", temp_notices_db)
    assert res is not None
    assert res["response_type"] == ResponseType.NOT_FOUND
    assert res["confidence"] == "Low"
    assert res["answer"] == "No notices matching your query were found in the official notices records."
    # Ensure it is exactly one sentence
    sentences = [s.strip() for s in res["answer"].split(".") if s.strip()]
    assert len(sentences) == 1


# --- 3. Confidence Calculation Tests ---

def test_compute_confidence_high_structured_table():
    """Verify High confidence when answer comes from structured tables (faculty, notices, verified facts)."""
    conf, reason = compute_confidence(
        response_type=ResponseType.ANSWERED,
        answer_text="Dr. G. Kishor is the HOD of EEE.",
        is_structured_table=True
    )
    assert conf == "High"


def test_compute_confidence_high_strong_multi_chunk():
    """Verify High confidence when top retrieval score is strong and at least 2 chunks support it."""
    contexts = [
        {"score": 0.45, "content": "Chunk 1 content"},
        {"score": 0.28, "content": "Chunk 2 content"}
    ]
    conf, reason = compute_confidence(
        response_type=ResponseType.ANSWERED,
        answer_text="B.Tech tuition fee is ₹70,000 per academic year.",
        contexts=contexts,
        is_structured_table=False,
        verification_passed=True
    )
    assert conf == "High"


def test_compute_confidence_medium_single_or_weak_source():
    """Verify Medium confidence when there is only one chunk or weak/moderate match."""
    # Single chunk only
    contexts_single = [{"score": 0.50, "content": "Only one chunk"}]
    conf_1, _ = compute_confidence(
        response_type=ResponseType.ANSWERED,
        answer_text="Placement percentage was 85%.",
        contexts=contexts_single,
        is_structured_table=False
    )
    assert conf_1 == "Medium"

    # Weak multi chunks (< 0.38)
    contexts_weak = [{"score": 0.30}, {"score": 0.22}]
    conf_2, _ = compute_confidence(
        response_type=ResponseType.ANSWERED,
        answer_text="Campus canteen timings.",
        contexts=contexts_weak,
        is_structured_table=False
    )
    assert conf_2 == "Medium"


def test_compute_confidence_low_partial_not_found_missing_info():
    """Verify Low confidence for PARTIAL, NOT_FOUND, or when answer text says information is missing."""
    conf_partial, _ = compute_confidence(response_type=ResponseType.PARTIAL, answer_text="Some text")
    assert conf_partial == "Low"

    conf_not_found, _ = compute_confidence(response_type=ResponseType.NOT_FOUND, answer_text="Not found")
    assert conf_not_found == "Low"

    conf_missing, _ = compute_confidence(
        response_type=ResponseType.ANSWERED,
        answer_text="The official records do not specify the external examiner."
    )
    assert conf_missing == "Low"

    conf_only_confirm, _ = compute_confidence(
        response_type=ResponseType.ANSWERED,
        answer_text="The sources only confirm 10 of 15 faculty members."
    )
    assert conf_only_confirm == "Low"


# --- 4. Confidence Badge Display Tests ---

def test_confidence_badge_html_display():
    """Verify badge is NOT displayed for High confidence, and IS displayed for Medium and Low."""
    # High: No badge
    assert get_confidence_badge_html("High") is None
    assert get_confidence_badge_html("high") is None

    # Medium: Badge shown
    badge_med = get_confidence_badge_html("Medium")
    assert badge_med is not None
    assert "Check this on the official website" in badge_med
    assert "#fef3c7" in badge_med  # Amber background

    # Low: Badge shown
    badge_low = get_confidence_badge_html("Low")
    assert badge_low is not None
    assert "Check this on the official website" in badge_low
    assert "#fee2e2" in badge_low  # Red background
