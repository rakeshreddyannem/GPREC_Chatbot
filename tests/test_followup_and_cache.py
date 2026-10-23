import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.database import DatabaseManager
from src.rag_pipeline import rewrite_query, normalize_question, clear_answer_cache


# --- 1. Follow-up Rewriter Tests (5 cases without API key) ---

def test_rewriter_case1_department_shift():
    """Case 1: User shifts department (e.g. 'and for ECE?' following 'who is the hod of eee')."""
    history = [
        {"question": "who is the hod of eee", "answer": "The HOD of EEE is Dr. G. Kishor."}
    ]
    rewritten, was_rewritten = rewrite_query("and for ECE?", history)
    assert was_rewritten is True
    assert "ECE" in rewritten
    assert "hod" in rewritten.lower()


def test_rewriter_case2_missing_subject_fee():
    """Case 2: Missing subject with fee (e.g. 'what about the fee?' following 'admissions for B.Tech')."""
    history = [
        {"question": "admissions for B.Tech", "answer": "Admissions for B.Tech are conducted via EAPCET counseling."}
    ]
    rewritten, was_rewritten = rewrite_query("what about the fee?", history)
    assert was_rewritten is True
    assert "fee" in rewritten.lower()
    assert "b.tech" in rewritten.lower()


def test_rewriter_case3_pronoun_person_qualification():
    """Case 3: Pronoun referring to person's qualification (e.g. 'his qualification' following 'who is dr kishor')."""
    history = [
        {"question": "who is dr kishor", "answer": "Dr. G. Kishor is the Head of the EEE Department."}
    ]
    rewritten, was_rewritten = rewrite_query("his qualification", history)
    assert was_rewritten is True
    assert "qualification" in rewritten.lower()
    assert "kishor" in rewritten.lower()


def test_rewriter_case4_pronoun_person_email():
    """Case 4: Pronoun referring to person's email (e.g. 'what is his email?' following query on Dr. G. Kishor)."""
    history = [
        {"question": "profile of Dr. G. Kishor", "answer": "Dr. G. Kishor is Professor and HOD of EEE."}
    ]
    rewritten, was_rewritten = rewrite_query("what is his email?", history)
    assert was_rewritten is True
    assert "email" in rewritten.lower()
    assert "kishor" in rewritten.lower()


def test_rewriter_case5_conjunction_eligibility():
    """Case 5: Conjunction with missing subject (e.g. 'and eligibility?' following 'B.Tech ECE course')."""
    history = [
        {"question": "B.Tech ECE course", "answer": "B.Tech in Electronics and Communication Engineering has an intake of 180."}
    ]
    rewritten, was_rewritten = rewrite_query("and eligibility?", history)
    assert was_rewritten is True
    assert "eligibility" in rewritten.lower()
    assert "ece" in rewritten.lower()


def test_rewriter_standalone_query_unchanged():
    """Verify that a standalone complete query is not modified."""
    history = [
        {"question": "who is the principal", "answer": "The principal is Dr. B. Sreenivasa Reddy."}
    ]
    rewritten, was_rewritten = rewrite_query("What are the library timings and rules?", history)
    assert was_rewritten is False
    assert rewritten == "What are the library timings and rules?"


# --- 2. Answer Cache Tests (Hit, Miss, Expiry, Filter, Clear without API key) ---

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_cache.db"
    return DatabaseManager(db_path=db_file)


def test_cache_miss(temp_db):
    """Cache miss returns None."""
    norm_q = normalize_question("What is the cutoff for ECE?")
    cached = temp_db.get_cached_answer(norm_q)
    assert cached is None


def test_cache_hit(temp_db):
    """Cache hit returns stored answer."""
    norm_q = normalize_question("What is the cutoff for ECE?")
    sample_response = {
        "response_type": "ANSWERED",
        "answer": "The cutoff for ECE in 2026 was rank 15420.",
        "sources": [{"title": "Cutoff 2026", "source_url": "https://gprec.ac.in/cutoff"}],
        "confidence": "High"
    }
    temp_db.set_cached_answer(norm_q, sample_response)

    cached = temp_db.get_cached_answer(norm_q)
    assert cached is not None
    assert cached["from_cache"] is True
    assert cached["answer"] == sample_response["answer"]
    assert cached["confidence"] == "High"


def test_cache_expiry_24_hours(temp_db):
    """Answers older than 24 hours expire and are deleted."""
    norm_q = normalize_question("What are the hostel fees?")
    sample_response = {
        "response_type": "ANSWERED",
        "answer": "Hostel fee is ₹85,000 per year.",
        "sources": [],
        "confidence": "High"
    }
    # Insert with timestamp 25 hours ago (25 * 3600 = 90000s)
    old_time = time.time() - 90000.0
    temp_db.set_cached_answer(norm_q, sample_response, created_at=old_time)

    # Calling get_cached_answer should detect expiry, delete row, and return None
    cached = temp_db.get_cached_answer(norm_q)
    assert cached is None

    # Verify row was actually deleted from database
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM answer_cache WHERE normalized_query = ?", (norm_q,))
        assert cursor.fetchone()[0] == 0


def test_cache_does_not_cache_not_found_or_clarify(temp_db):
    """NOT_FOUND and CLARIFY responses must never be cached."""
    norm_q1 = normalize_question("nonexistent question 123")
    not_found_resp = {
        "response_type": "NOT_FOUND",
        "answer": "I couldn't find this information.",
        "sources": []
    }
    temp_db.set_cached_answer(norm_q1, not_found_resp)
    assert temp_db.get_cached_answer(norm_q1) is None

    norm_q2 = normalize_question("ambiguous query")
    clarify_resp = {
        "response_type": "CLARIFY",
        "answer": "Which department are you asking about?",
        "sources": []
    }
    temp_db.set_cached_answer(norm_q2, clarify_resp)
    assert temp_db.get_cached_answer(norm_q2) is None


def test_clear_answer_cache(temp_db):
    """clear_answer_cache deletes all rows in the cache."""
    q1 = normalize_question("query one")
    q2 = normalize_question("query two")
    temp_db.set_cached_answer(q1, {"response_type": "ANSWERED", "answer": "Ans 1"})
    temp_db.set_cached_answer(q2, {"response_type": "ANSWERED", "answer": "Ans 2"})

    assert temp_db.get_cached_answer(q1) is not None
    assert temp_db.get_cached_answer(q2) is not None

    deleted_count = temp_db.clear_answer_cache()
    assert deleted_count == 2
    assert temp_db.get_cached_answer(q1) is None
    assert temp_db.get_cached_answer(q2) is None
