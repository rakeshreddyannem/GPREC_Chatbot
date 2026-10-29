import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock, patch

from src.database import DatabaseManager
from src.subject_assistant import (
    VERIFICATION_LINE,
    OUTSIDE_SUBJECT_NOTE_PREFIX,
    COLLEGE_FACT_REDIRECT,
    PRACTICE_DISCLAIMER,
    split_topics,
    get_subject_cache_key,
    is_outside_subject,
    is_college_fact_query,
    generate_example_doubts,
    build_doubt_prompt,
    build_topic_explanation_prompt,
    build_practice_prompt,
    build_quick_revision_prompt,
    answer_subject_doubt,
    clean_subject_response
)


# ---------------------------------------------------------------------------
# 1. TOPICS SPLITTING ON 5 SAMPLE STRINGS
# ---------------------------------------------------------------------------

def test_topics_splitting_on_5_sample_strings():
    """Verify split_topics properly splits, cleans, and deduplicates across 5 sample strings."""
    # Sample 1: Mixed commas and semicolons
    s1 = "Stacks, Queues, Linked Lists; Trees, Graphs"
    t1 = split_topics(s1)
    assert t1 == ["Stacks", "Queues", "Linked Lists", "Trees", "Graphs"]

    # Sample 2: Algorithm topics with punctuation and whitespace
    s2 = "  Linear Search, Binary Search; Hashing Techniques; Linear Search  "
    t2 = split_topics(s2)
    assert t2 == ["Linear Search", "Binary Search", "Hashing Techniques"]

    # Sample 3: Electrical engineering laws
    s3 = "Ohm's Law; Kirchhoff's Voltage Law, Kirchhoff's Current Law; Thevenin's Theorem."
    t3 = split_topics(s3)
    assert t3 == ["Ohm's Law", "Kirchhoff's Voltage Law", "Kirchhoff's Current Law", "Thevenin's Theorem"]

    # Sample 4: Unit labels, bullet points and semicolons
    s4 = "- Unit 1: Introduction, 1. Basic Concepts; 2. Syntax and Semantics; Grammar"
    t4 = split_topics(s4)
    assert "Introduction" in t4
    assert "Syntax and Semantics" in t4
    assert "Grammar" in t4

    # Sample 5: Single topic without commas or semicolons
    s5 = "Single Topic Without Delimiters"
    t5 = split_topics(s5)
    assert t5 == ["Single Topic Without Delimiters"]


# ---------------------------------------------------------------------------
# 2. CACHE KEY STABILITY
# ---------------------------------------------------------------------------

def test_cache_key_stability():
    """Cache keys must be deterministic, lowercase, and stable."""
    k1 = get_subject_cache_key("ADVANCED DATA STRUCTURES", "Unit 1", "Stacks", "explain")
    k2 = get_subject_cache_key("advanced data structures ", "unit 1", "stacks", "explain")
    assert k1 == k2
    assert k1 == "subassist:explain:advanced_data_structures:unit_1:stacks"

    k3 = get_subject_cache_key("DBS", "Unit 2", "SQL", "practice", "5_mcq")
    assert k3 == "subassist:practice:dbs:unit_2:sql:5_mcq"


# ---------------------------------------------------------------------------
# 3. PROMPT BUILDERS INCLUDE SUBJECT, UNITS, AND VERIFICATION LINE
# ---------------------------------------------------------------------------

def test_prompt_builders_include_subject_units_verification():
    """Prompt builders must embed subject name, unit details, and mandatory verification line."""
    subject = "ADVANCED DATA STRUCTURES (ADS)"
    units_data = [
        {"unit_number": 1, "unit_title": "Linear Data Structures", "topics": "Stacks, Queues", "textbooks": "Horowitz & Sahni"},
        {"unit_number": 2, "unit_title": "Trees", "topics": "BST, AVL Trees", "textbooks": "Weiss"}
    ]

    # a. Doubt Prompt
    sys_p, usr_p = build_doubt_prompt(subject, units_data, "How does an AVL rotation work?")
    assert subject in sys_p or subject in usr_p
    assert "Linear Data Structures" in usr_p
    assert "Trees" in usr_p
    assert VERIFICATION_LINE in sys_p

    # b. Topic Explanation Prompt
    sys_exp, usr_exp = build_topic_explanation_prompt(subject, "Unit 1: Linear Data Structures", "Stacks")
    assert subject in usr_exp
    assert "Unit 1: Linear Data Structures" in usr_exp
    assert "Stacks" in usr_exp
    assert VERIFICATION_LINE in sys_exp

    # c. Quick Revision Prompt
    sys_rev, usr_rev = build_quick_revision_prompt(subject, "Unit 2: Trees", unit_topics="BST, AVL Trees")
    assert subject in usr_rev
    assert "Unit 2: Trees" in usr_rev
    assert VERIFICATION_LINE in sys_rev


# ---------------------------------------------------------------------------
# 4. PRACTICE PROMPT CONTAINS COUNT, TYPE, AND DISCLAIMER
# ---------------------------------------------------------------------------

def test_practice_prompt_count_and_type():
    """Practice prompt must include requested count, question type, disclaimer, and verification line."""
    subject = "DATABASE SYSTEMS (DBS)"
    unit = "Unit 3: Relational Database Design"

    # Multiple Choice with count 5
    sys_mcq, usr_mcq = build_practice_prompt(subject, unit, 5, "Multiple Choice")
    assert "5" in usr_mcq
    assert "Multiple Choice" in usr_mcq
    assert PRACTICE_DISCLAIMER in sys_mcq
    assert VERIFICATION_LINE in sys_mcq

    # Short Answer with count 8
    sys_sa, usr_sa = build_practice_prompt(subject, unit, 8, "Short Answer")
    assert "8" in usr_sa
    assert "Short Answer" in usr_sa
    assert PRACTICE_DISCLAIMER in sys_sa
    assert VERIFICATION_LINE in sys_sa

    # Clamping test (e.g. 1 clamped to 3, 20 clamped to 10)
    _, usr_clamp_min = build_practice_prompt(subject, unit, 1, "Multiple Choice")
    assert "3" in usr_clamp_min
    _, usr_clamp_max = build_practice_prompt(subject, unit, 25, "Multiple Choice")
    assert "10" in usr_clamp_max


# ---------------------------------------------------------------------------
# 5. EMPTY SYLLABUS GIVES "TYPE THE SUBJECT" PATH
# ---------------------------------------------------------------------------

def test_empty_syllabus_gives_type_the_subject_path():
    """Empty database rows for a branch/semester must allow typed custom subjects smoothly."""
    db = DatabaseManager()
    
    # CIVIL Semester 3 has no syllabus rows in current database
    courses = db.get_syllabus_courses("CIVIL", 3)
    assert courses == []

    # Units for unindexed subject return empty list
    units = db.get_syllabus_units_for_course("CIVIL", 3, "Nonexistent Subject XYZ")
    assert units == []

    # Prompt builders function properly with empty/custom subject
    custom_subject = "Power Systems - Transmission & Distribution"
    sys_p, usr_p = build_doubt_prompt(custom_subject, [], "Explain Ferranti effect.")
    assert custom_subject in sys_p or custom_subject in usr_p
    assert "No specific unit breakdown" in usr_p
    assert VERIFICATION_LINE in sys_p


# ---------------------------------------------------------------------------
# 6. MOCK LLM CALL AND OUTSIDE-SUBJECT DETECTION
# ---------------------------------------------------------------------------

def test_mock_llm_outside_subject_adds_line():
    """A doubt about an outside subject adds the outside-subject notification line."""
    subject = "ADVANCED DATA STRUCTURES (ADS)"
    units = [
        {"unit_number": 1, "unit_title": "Linear Data Structures", "topics": "Stacks, Queues"}
    ]
    
    # Heuristic test directly
    doubt_outside = "Explain the working principle of a 3-phase induction motor."
    assert is_outside_subject(doubt_outside, subject, units) is True

    # Inside subject query
    doubt_inside = "How do I implement a stack using linked lists?"
    assert is_outside_subject(doubt_inside, subject, units) is False

    # Mock call_subject_llm to simulate LLM answering the question
    with patch("src.subject_assistant.call_subject_llm") as mock_llm:
        mock_llm.return_value = (
            "A 3-phase induction motor operates on the principle of electromagnetic induction. "
            "When 3-phase supply is given to stator, a rotating magnetic field is produced.\n\n"
            f"{VERIFICATION_LINE}"
        )
        
        answer = answer_subject_doubt(
            doubt_outside, 
            subject, 
            units_data=units, 
            client=MagicMock(),
            db=None
        )
        
        # Verify that the outside subject line is added
        assert OUTSIDE_SUBJECT_NOTE_PREFIX.lower() in answer.lower()
        assert subject.lower() in answer.lower()
        assert VERIFICATION_LINE in answer


# ---------------------------------------------------------------------------
# 7. COLLEGE FACT REDIRECT
# ---------------------------------------------------------------------------

def test_college_fact_redirect():
    """Administrative and college fact queries are redirected to Ask AI page without LLM calls."""
    assert is_college_fact_query("What is the B.Tech tuition fee for CSE?") is True
    assert is_college_fact_query("Who is the principal of GPREC?") is True
    assert is_college_fact_query("When will semester exam timetables be released?") is True
    assert is_college_fact_query("Explain binary search algorithm.") is False

    ans = answer_subject_doubt("What is the college fee?", "Database Systems", None)
    assert COLLEGE_FACT_REDIRECT in ans
    assert VERIFICATION_LINE in ans


# ---------------------------------------------------------------------------
# 8. FOLLOW-UP HISTORY IN DOUBT PROMPT
# ---------------------------------------------------------------------------

def test_followup_history_in_doubt_prompt():
    """Last 3 turns of conversation history are formatted into the prompt."""
    history = [
        {"role": "user", "content": "What is a binary search tree?"},
        {"role": "assistant", "content": "A BST is a node-based binary tree."},
        {"role": "user", "content": "What about AVL tree?"},
        {"role": "assistant", "content": "An AVL tree is a self-balancing BST."},
        {"role": "user", "content": "How does balancing work?"},
        {"role": "assistant", "content": "Balancing uses tree rotations."}
    ]
    
    _, usr_p = build_doubt_prompt("Data Structures", [], "Give me a numerical example.", history=history)
    assert "LAST 3 TURNS" in usr_p
    assert "What is a binary search tree?" in usr_p
    assert "What about AVL tree?" in usr_p
    assert "How does balancing work?" in usr_p
    assert "Give me a numerical example." in usr_p


# ---------------------------------------------------------------------------
# 9. REASONING SCRATCHPAD STRIPPING
# ---------------------------------------------------------------------------

def test_clean_subject_response_strips_scratchpad():
    """Verify that internal reasoning, planning steps, and constraint reviews are cleanly stripped."""
    leaked_cot_output = """Analyze the Request:

Role: Patient BTech engineering tutor.
Task: Create a concise, high-yield one-page quick revision sheet.
Subject: ADVANCED DATA STRUCTURES (ADS), Unit 4: Hashing Techniques.
Structure Requirements: Exactly 4 sections:

Drafting Section 1: Key Points
- Hashing maps keys to indices using a hash function.
- Open hashing uses separate chaining with linked lists.
- Closed hashing stores entries directly in the table.

Drafting Section 2: Formulas & Governing Equations
- Linear Probing: $h(k,i) = (h'(k) + i) \\bmod m$
- Quadratic Probing: $h(k,i) = (h'(k) + c_1 i^2) \\bmod m$
- Load factor: $\\alpha = \\frac{n}{m}$

Drafting Section 3: Essential Definitions
- Hash Function: A mapping from keys to integer slots.
- Collision: Multiple keys hashing to the same slot.

Drafting Section 4: 5-Line Recap
1. Hashing provides fast $O(1)$ average search.
2. Separate chaining handles collisions with external lists.
3. Open addressing probes alternate table slots.
4. Rehashing expands table when load factor exceeds limit.
5. Extendible hashing dynamically grows directories.

Review against constraints:
Tone? Yes. One page? Yes.
AI explanation. Verify important results with your textbook.
"""
    cleaned = clean_subject_response(leaked_cot_output)

    # 1. Preamble and meta-analysis stripped
    assert "Analyze the Request" not in cleaned
    assert "Role: Patient BTech" not in cleaned
    assert "Review against constraints" not in cleaned

    # 2. Drafting sections converted to clean markdown headers
    assert "### 1. Key Points" in cleaned
    assert "### 2. Formulas & Governing Equations" in cleaned
    assert "### 3. Essential Definitions" in cleaned
    assert "### 4. 5-Line Recap" in cleaned

    # 3. Content preserved accurately
    assert "Hashing maps keys to indices" in cleaned
    assert "$h(k,i) = (h'(k) + i) \\bmod m$" in cleaned

    # 4. Mandatory verification line present
    assert VERIFICATION_LINE in cleaned


# ---------------------------------------------------------------------------
# 10. ALL 10 DEPARTMENTS PRESENT IN CONFIGS AND DATABASE
# ---------------------------------------------------------------------------

def test_all_10_departments_present():
    """All 10 canonical engineering departments must be present in DEPARTMENT_CONFIGS."""
    from src.faculty_parser import DEPARTMENT_CONFIGS
    dept_codes = [d["short_code"] for d in DEPARTMENT_CONFIGS]
    expected_10 = ["CE", "CSE", "EEE", "ECE", "ME", "H&S", "CSM", "CSD", "CSB", "CST"]
    for code in expected_10:
        assert code in dept_codes, f"Expected {code} in DEPARTMENT_CONFIGS"
    assert len(DEPARTMENT_CONFIGS) == 10

    db = DatabaseManager()
    branches = db.get_syllabus_branches()
    for code in expected_10:
        assert code in branches, f"Expected {code} in get_syllabus_branches()"


# ---------------------------------------------------------------------------
# 11. YEAR 1 COMMON SUBJECTS SHOW FOR EVERY BRANCH
# ---------------------------------------------------------------------------

def test_year_1_common_subjects_show_for_every_branch():
    """Year 1 uses the common I B.Tech syllabus for every branch."""
    from src.faculty_parser import DEPARTMENT_CONFIGS
    db = DatabaseManager()
    dept_codes = [d["short_code"] for d in DEPARTMENT_CONFIGS]

    for branch in dept_codes:
        # Semester 1 courses for this branch (should include COMMON year 1 subjects)
        sem1_courses = db.get_syllabus_courses(branch, semester=1)
        assert len(sem1_courses) > 0, f"Expected Year 1 Sem 1 common subjects for {branch}"
        
        # Verify courses contain common first-year subjects (e.g. Mathematics, Physics, Chemistry, C Programming)
        titles = [c["course_title"].lower() for c in sem1_courses]
        assert any("linear algebra" in t or "calculus" in t or "mathematics" in t or "physics" in t or "chemistry" in t or "programming" in t for t in titles), (
            f"Expected common foundational course for {branch} in Sem 1, got: {titles}"
        )

        # Semesters list must include 1 and 2
        sems = db.get_syllabus_semesters(branch)
        assert 1 in sems, f"Expected Semester 1 in semesters for {branch}"
        assert 2 in sems, f"Expected Semester 2 in semesters for {branch}"


# ---------------------------------------------------------------------------
# 12. CACHE KEY WITH BRANCH AND SCHEME
# ---------------------------------------------------------------------------

def test_cache_key_with_branch_and_scheme():
    """Cache key must incorporate branch, scheme, subject, unit, topic, and type deterministically."""
    k1 = get_subject_cache_key(
        subject="Switching Theory & Logic Design",
        unit="Unit 2: Combinational Logic",
        topic="Karnaugh Maps",
        content_type="explain",
        branch="CSE",
        scheme="2023"
    )
    k2 = get_subject_cache_key(
        subject="switching theory & logic design ",
        unit="unit 2: combinational logic",
        topic="karnaugh maps",
        content_type="explain",
        branch="cse",
        scheme="2023"
    )
    assert k1 == k2
    assert "cse" in k1
    assert "2023" in k1
    assert "explain" in k1
    assert "karnaugh_maps" in k1


# ---------------------------------------------------------------------------
# 13. TIMETABLE SUBJECTS ORDERED FIRST WITH RUNNING MARKER
# ---------------------------------------------------------------------------

def test_timetable_subjects_ordered_first_with_marker():
    """Subjects running this semester from timetable_subjects appear first marked '[Running this semester]'."""
    db = DatabaseManager()
    subjects = db.get_subject_assistance_subjects("CSE", semester=3, scheme="2023")
    assert len(subjects) > 0

    # First subjects must be running timetable subjects
    running_flags = [s["is_running"] for s in subjects]
    assert running_flags[0] is True, "First subject must be running timetable subject"
    
    # Running subjects must have the display marker
    running_labels = [s["display_label"] for s in subjects if s["is_running"]]
    for label in running_labels:
        assert "[Running this semester]" in label


