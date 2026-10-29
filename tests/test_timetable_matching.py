"""
Tests for Timetable Parser and Syllabus Matching.
Covers:
1. Matching function with 8 fixture test pairs:
   - exact code
   - exact code case/spacing
   - abbreviation matching
   - normalized title matching
   - spacing differences
   - punctuation differences
   - minor typo/variation
   - pair that must NOT match (below threshold)
2. DatabaseManager.get_current_subjects() functionality and 'Current semester' flag.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import sqlite3
from typing import Dict, Any, List

from src.timetable_parser import normalize_title, match_subject_with_syllabus
from src.database import DatabaseManager


@pytest.fixture
def sample_syllabus_fixture() -> List[Dict[str, Any]]:
    """Fixture with a curated short sample of syllabus courses across branches."""
    return [
        {
            "course_code": "CS202",
            "course_title": "ADVANCED DATA STRUCTURES (ADS)",
            "branch": "CSE",
            "semester": 3
        },
        {
            "course_code": "CS203",
            "course_title": "DATABASE SYSTEMS (DBS)",
            "branch": "CSE",
            "semester": 3
        },
        {
            "course_code": "EC201",
            "course_title": "ELECTRONIC DEVICES AND CIRCUITS (EDC)",
            "branch": "ECE",
            "semester": 3
        },
        {
            "course_code": "EE205",
            "course_title": "CONTROL SYSTEMS ENGINEERING (CSE)",
            "branch": "EEE",
            "semester": 4
        },
        {
            "course_code": "BS101",
            "course_title": "LINEAR ALGEBRA & CALCULUS (LAC)",
            "branch": "COMMON",
            "semester": 1
        },
        {
            "course_code": "CE303",
            "course_title": "TRANSPORTATION ENGINEERING (TE)",
            "branch": "CE",
            "semester": 5
        }
    ]


def test_matching_pair_1_exact_code(sample_syllabus_fixture):
    """Pair 1: Exact course code provided in timetable."""
    code, score, title = match_subject_with_syllabus(
        subject_name="Advanced Data Structures",
        course_code="CS202",
        branch="CSE",
        semester=3,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "CS202"
    assert score == 1.0


def test_matching_pair_2_exact_code_lower_space(sample_syllabus_fixture):
    """Pair 2: Course code with lowercase and internal spacing."""
    code, score, title = match_subject_with_syllabus(
        subject_name="Database Systems",
        course_code="cs 203",
        branch="CSE",
        semester=3,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "CS203"
    assert score == 1.0


def test_matching_pair_3_normalized_title_case(sample_syllabus_fixture):
    """Pair 3: Normalized title match (mixed case without code)."""
    code, score, title = match_subject_with_syllabus(
        subject_name="advanced data structures",
        course_code=None,
        branch="CSE",
        semester=3,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "CS202"
    assert score >= 0.85


def test_matching_pair_4_title_punctuation_differences(sample_syllabus_fixture):
    """Pair 4: Title with punctuation differences (ampersand, exclamation, lower)."""
    code, score, title = match_subject_with_syllabus(
        subject_name="electronic devices & circuits!",
        course_code=None,
        branch="ECE",
        semester=3,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "EC201"
    assert score >= 0.85


def test_matching_pair_5_spacing_differences(sample_syllabus_fixture):
    """Pair 5: Title with irregular tab/spacing differences."""
    code, score, title = match_subject_with_syllabus(
        subject_name="Control   Systems    Engineering",
        course_code=None,
        branch="EEE",
        semester=4,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "EE205"
    assert score >= 0.85


def test_matching_pair_6_abbreviation_parenthetical(sample_syllabus_fixture):
    """Pair 6: Subject matching through abbreviation parenthetical (e.g. DBS)."""
    code, score, title = match_subject_with_syllabus(
        subject_name="DBS",
        course_code=None,
        branch="CSE",
        semester=3,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "CS203"
    assert score >= 0.85


def test_matching_pair_7_minor_typo_variation(sample_syllabus_fixture):
    """Pair 7: Title with minor variation ('and' vs '&')."""
    code, score, title = match_subject_with_syllabus(
        subject_name="Linear Algebra and Calculus",
        course_code=None,
        branch="COMMON",
        semester=1,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code == "BS101"
    assert score >= 0.85


def test_matching_pair_8_must_not_match(sample_syllabus_fixture):
    """Pair 8: Pair that must NOT match (completely different subject below threshold)."""
    code, score, title = match_subject_with_syllabus(
        subject_name="Quantum Astrophysics and Relativistic Rocket Propulsion",
        course_code=None,
        branch="CSE",
        semester=3,
        syllabus_rows=sample_syllabus_fixture,
        threshold=0.85
    )
    assert code is None
    assert score < 0.85


def test_database_get_current_subjects_method():
    """Tests DatabaseManager.get_current_subjects with current semester flag."""
    db = DatabaseManager()
    
    # Insert a test subject into timetable_subjects
    test_entry = {
        "branch": "TEST_CSE",
        "year": 2,
        "semester": 3,
        "section": "A",
        "academic_year": "2023-2024",
        "course_code": "CS202",
        "subject_name": "Advanced Data Structures",
        "faculty": "Dr. Test Faculty",
        "source_file": "test_timetable.pdf",
        "page_num": 1,
        "needs_review": 0,
        "is_current_semester": 1
    }
    db.insert_timetable_subject(test_entry)

    # Query using branch and semester
    subjects = db.get_current_subjects(branch="TEST_CSE", year_or_semester=3)
    assert len(subjects) >= 1
    item = next((s for s in subjects if s["course_code"] == "CS202"), None)
    assert item is not None
    assert item["is_current_semester"] == 1
    assert item["branch"] == "TEST_CSE"
    assert item["subject_name"] == "Advanced Data Structures"

    # Clean up test entry
    with db.get_connection() as conn:
        conn.cursor().execute("DELETE FROM timetable_subjects WHERE branch = 'TEST_CSE'")
        conn.commit()
