import pytest
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from tests.regression.check_rules import evaluate_result

def test_questions_json_exists_and_valid():
    questions_file = Path(__file__).resolve().parent / "questions.json"
    assert questions_file.exists(), "questions.json does not exist"
    with open(questions_file, "r") as f:
        questions = json.load(f)
    assert len(questions) == 13, f"Expected 13 questions, found {len(questions)}"
    for q in questions:
        assert "id" in q
        assert "query" in q
        assert "expected_behavior" in q

def test_baseline_recorded_results():
    results_file = Path(__file__).resolve().parent / "before_results.json"
    if not results_file.exists():
        pytest.skip("before_results.json not yet generated. Run run_regression.py first.")
    
    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    assert len(results) == 13, f"Expected 13 recorded results, found {len(results)}"
    
    # Verify every result has required schema
    for r in results:
        assert "id" in r
        assert "query" in r
        assert "answer" in r
        assert "confidence" in r
        assert "check_passed" in r
