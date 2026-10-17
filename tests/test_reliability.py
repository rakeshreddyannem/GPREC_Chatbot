import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.reliability import (
    ResponseType, AmbiguityDetector, AnswerVerifier,
    SensitiveInfoFilter, DateValidator, ResponseFormatter
)
from src.database import DatabaseManager

def test_ambiguity_detection_case3():
    # Case 3: "list the PhD faculties" has no department
    ambiguity = AmbiguityDetector.check_ambiguity("list the PhD faculties")
    assert ambiguity is not None
    assert ambiguity["response_type"] == ResponseType.CLARIFY
    assert "Which department" in ambiguity["question"]
    assert "EEE" in ambiguity["options"]
    assert "CSE" in ambiguity["options"]

    # When department is specified, ambiguity should not trigger
    no_ambiguity = AmbiguityDetector.check_ambiguity("list the phd faculties of eee department")
    assert no_ambiguity is None

def test_exam_timetable_ambiguity():
    # Ambiguous exam timetable query without branch or year
    amb = AmbiguityDetector.check_ambiguity("detail information about the exam time table")
    assert amb is not None
    assert amb["response_type"] == ResponseType.CLARIFY
    assert "timetable" in amb["question"].lower()
    assert "B.Tech I Year" in amb["options"]

    # Specific exam timetable query should not trigger CLARIFY
    no_amb = AmbiguityDetector.check_ambiguity("EEE 4th year 2nd sem exam time table")
    assert no_amb is None

def test_forbid_inference_rules():
    # Rule: Never state someone holds a PhD because of jury/resource person role
    invalid_answer = "Sri. John is a jury member which implies he holds a Ph.D. degree."
    context = "Sri. John served as a jury member in the symposium."
    passed, errors = AnswerVerifier.verify_phd_claims(invalid_answer, context)
    assert not passed
    assert any("jury" in err.lower() for err in errors)

    # Valid PhD statement with Dr. in context
    valid_answer = "Dr. G. Kishor is the Head of the Department."
    valid_context = "Dr. G. Kishor, Professor & Head, Department of EEE."
    passed_valid, errors_valid = AnswerVerifier.verify_phd_claims(valid_answer, valid_context)
    assert passed_valid
    assert len(errors_valid) == 0

def test_sensitive_info_filtering():
    # 1. Personal Indian 10-digit mobile number must be scrubbed
    raw_text = "For details contact Dr. Ishthaq Ahmed, Associate Professor – 9866776244."
    scrubbed = SensitiveInfoFilter.scrub(raw_text)
    assert "9866776244" not in scrubbed
    assert "office" in scrubbed.lower()

    # 2. Password patterns must be scrubbed
    pwd_text = "Log in with your roll number and default password: Changeme123!"
    scrubbed_pwd = SensitiveInfoFilter.scrub(pwd_text)
    assert "Changeme123!" not in scrubbed_pwd
    assert "PROTECTED" in scrubbed_pwd

def test_date_plausibility():
    assert DateValidator.is_plausible_date("2026-03-15") is True
    assert DateValidator.is_plausible_date("1995-01-01") is False  # Older than year 2000
    assert DateValidator.is_plausible_date("2050-10-10") is False  # Far future year

def test_response_formatter_not_found():
    nf = ResponseFormatter.format_not_found(["Q1", "Q2"])
    assert nf["response_type"] == ResponseType.NOT_FOUND
    assert "I couldn't find this information" in nf["answer"]
    assert len(nf["suggested_questions"]) == 2
    assert nf["confidence"] == "Low"

def test_response_formatter_partial():
    part = ResponseFormatter.format_partial(
        available="Available staff: 4 Professors.",
        missing="Designations for Assistant Professors.",
        where_to_look="Check official EEE faculty page."
    )
    assert part["response_type"] == ResponseType.PARTIAL
    assert "Missing Information:" in part["answer"]
    assert "Where to Look:" in part["answer"]
    assert part["confidence"] == "Medium"

def test_acronym_table_curated():
    db = DatabaseManager()
    acr = db.get_acronym("ITCA")
    assert acr is not None
    assert "Intensive Training" in acr["expansion"]
    assert acr["is_curated"] == 1
