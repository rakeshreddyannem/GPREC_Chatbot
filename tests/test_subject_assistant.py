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
    clean_subject_response,
    extract_mcq_json,
    generate_subject_mcqs,
    generate_subject_short_answers
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

def test_all_departments_present():
    """All active college departments from timetables must be present in DEPARTMENT_CONFIGS."""
    from src.faculty_parser import DEPARTMENT_CONFIGS
    dept_codes = [d["short_code"] for d in DEPARTMENT_CONFIGS]
    expected_depts = ["CE", "CSE", "EEE", "ECE", "ME", "H&S", "CSM"]
    for code in expected_depts:
        assert code in dept_codes, f"Expected {code} in DEPARTMENT_CONFIGS"
    assert len(DEPARTMENT_CONFIGS) == 7

    db = DatabaseManager()
    branches = db.get_syllabus_branches()
    for code in ["CE", "CSE", "EEE", "ECE", "ME", "CSM"]:
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
    """Subjects running this semester appear first, and display labels are clean without '[Running this semester]' prefix."""
    db = DatabaseManager()
    subjects = db.get_subject_assistance_subjects("CSE", semester=3, scheme="2023")
    assert len(subjects) > 0

    # First subjects must be running timetable subjects
    running_flags = [s["is_running"] for s in subjects]
    assert running_flags[0] is True, "First subject must be running timetable subject"
    
    # Running subjects must NOT have the prefix in display_label (per user request)
    running_labels = [s["display_label"] for s in subjects if s["is_running"]]
    for label in running_labels:
        assert "[Running this semester]" not in label


# ---------------------------------------------------------------------------
# 14. MCQ JSON EXTRACTION AND PARSING ROBUSTNESS
# ---------------------------------------------------------------------------

def test_extract_mcq_json_robustness():
    """Verify extract_mcq_json handles code blocks, bare arrays, LaTeX escapes, and trailing commas."""
    # 1. Standard markdown fenced code block
    fenced_output = """Here are the questions:
```json
[
  {
    "question_number": 1,
    "question": "What is an object in Java?",
    "options": {"A": "Instance of class", "B": "Primitive type", "C": "Method", "D": "Package"},
    "correct_option": "A",
    "explanation": "An object is an instance of a class."
  }
]
```
Verified against textbook."""
    mcqs = extract_mcq_json(fenced_output)
    assert mcqs is not None
    assert len(mcqs) == 1
    assert mcqs[0]["question_number"] == 1
    assert mcqs[0]["correct_option"] == "A"

    # 2. Bare array with trailing comma and unescaped LaTeX backslashes
    bare_with_latex = r"""[
  {
    "question_number": 1,
    "question": "Evaluate \frac{a}{b} where \alpha = 1 and \{x\} is set",
    "options": {"A": "Choice A", "B": "Choice B", "C": "Choice C", "D": "Choice D"},
    "correct_option": "Option B",
    "explanation": "Derived using formula \beta.",
  }
]"""
    mcqs_latex = extract_mcq_json(bare_with_latex)
    assert mcqs_latex is not None
    assert len(mcqs_latex) == 1
    assert mcqs_latex[0]["correct_option"] == "B"

    # 3. Model thought/scratchpad without JSON returns None
    scratchpad_only = """We need to generate 5 multiple choice questions for Unit 1 of OOPJ.
Let's craft:
Question 1: Define class vs object.
Question 2: Encapsulation.
We'll ensure each includes at least one LaTeX expression."""
    assert extract_mcq_json(scratchpad_only) is None


# ---------------------------------------------------------------------------
# 15. CLEAN SUBJECT RESPONSE STRIPS PRE-JSON REASONING
# ---------------------------------------------------------------------------

def test_clean_subject_response_strips_mcq_thinking():
    """Verify that reasoning preambles before ```json blocks are cleanly stripped."""
    leaked_mcq_reasoning = """We need to generate 5 multiple choice questions for Unit 1 of OOPJ (Object Oriented Programming Through Java).
Let's craft 5 MCQs.
```json
[
  {
    "question_number": 1,
    "question": "Which keyword instantiates an object in Java?",
    "options": {"A": "new", "B": "create", "C": "make", "D": "alloc"},
    "correct_option": "A",
    "explanation": "The 'new' operator dynamically allocates memory on the heap."
  }
]
```
AI explanation. Verify important results with your textbook."""
    cleaned = clean_subject_response(leaked_mcq_reasoning)
    assert "We need to generate" not in cleaned
    assert "Let's craft" not in cleaned
    assert "```json" in cleaned
    assert VERIFICATION_LINE in cleaned


# ---------------------------------------------------------------------------
# 16. SUBJECT-AWARE MCQ GENERATOR (JAVA/OOPJ AND OTHERS)
# ---------------------------------------------------------------------------

def test_generate_subject_mcqs_for_oopj_and_domain():
    """Verify generate_subject_mcqs returns structured questions with A,B,C,D options and explanations."""
    # Java / OOPJ
    java_mcqs = generate_subject_mcqs("Object Oriented Programming Through Java (OOPJ)", "Unit 1: Introduction", count=5)
    assert len(java_mcqs) == 5
    for idx, q in enumerate(java_mcqs):
        assert q["question_number"] == idx + 1
        assert len(q["options"]) >= 4
        assert set(q["options"].keys()) >= {"A", "B", "C", "D"}
        assert q["correct_option"] in {"A", "B", "C", "D"}
        assert len(q["explanation"]) > 5

    # Data Structures
    ds_mcqs = generate_subject_mcqs("Advanced Data Structures", "Unit 3: Balanced Trees", count=4)
    assert len(ds_mcqs) == 4
    assert any("avl" in q["question"].lower() or "heap" in q["question"].lower() or "tree" in q["question"].lower() for q in ds_mcqs)


# ---------------------------------------------------------------------------
# 17. EEE SUBJECTS RECEIVE DOMAIN-SPECIFIC MCQS (NOT GENERIC CIRCUITS)
# ---------------------------------------------------------------------------

def test_generate_subject_mcqs_eee_subjects_domain_specific():
    """Verify that EEE subjects receive domain-accurate questions and not generic circuit/diode questions."""
    # 1. Power Systems (PS-II)
    ps_mcqs = generate_subject_mcqs(
        "POWER SYSTEMS - II (PS-II)", 
        "Unit 1: Transmission Line Parameters", 
        "Types of Conductors, Calculation of Resistance, Bundle Conductors, Skin effect, Proximity effect, GMR and GMD", 
        count=5
    )
    assert len(ps_mcqs) == 5
    ps_text = " ".join(q["question"].lower() for q in ps_mcqs)
    assert any(w in ps_text for w in ["ferranti", "conductor", "bundle", "skin effect", "surge impedance", "insulator", "corona"])
    # Must NOT be the old generic circuit questions
    assert "thevenin" not in ps_text
    assert "kirchhoff's current law" not in ps_text

    # 2. Electrical Machines-I
    emc_mcqs = generate_subject_mcqs(
        "ELECTRICAL MACHINES-I", 
        "Unit 1: Electromechanical Energy Conversion", 
        "Forces and torques in magnetic field system, energy balance, singly and multiply excited magnetic systems", 
        count=5
    )
    assert len(emc_mcqs) == 5
    emc_text = " ".join(q["question"].lower() for q in emc_mcqs)
    assert any(w in emc_text for w in ["back emf", "transformer", "induction motor", "torque", "synchronous", "governor"])
    assert "thevenin" not in emc_text

    # 3. Modern Control Theory (MCTH)
    mcth_mcqs = generate_subject_mcqs(
        "MODERN CONTROL THEORY (MCTH)", 
        "Unit 1: Controllability and Observability", 
        "Concepts of controllability and observability, Controllability tests, Kalman test, Gilbert test", 
        count=5
    )
    assert len(mcth_mcqs) == 5
    mcth_text = " ".join(q["question"].lower() for q in mcth_mcqs)
    assert any(w in mcth_text for w in ["kalman", "controllability", "state transition", "routh", "bode", "observability"])

    # 4. Power Electronics (PE)
    pe_mcqs = generate_subject_mcqs(
        "POWER ELECTRONICS(PE)", 
        "Unit 1: Basics of Power Electronics", 
        "Introduction to power electronics, power semiconductor switches, Diodes, Thyristor, SCR, MOSFET, IGBT", 
        count=5
    )
    assert len(pe_mcqs) == 5
    pe_text = " ".join(q["question"].lower() for q in pe_mcqs)
    assert any(w in pe_text for w in ["latching current", "holding current", "snubber", "buck", "thyristor", "rectifier"])

    # 5. Measurements and Instrumentation (EMI)
    emi_mcqs = generate_subject_mcqs(
        "ELECTRICAL MEASUREMENTS AND INSTRUMENTATION (EMI)", 
        "Unit 1: Measuring Instruments & Digital Meters", 
        "Fundamentals: Errors, Static Characteristics, PMMC instruments, Moving Iron", 
        count=5
    )
    assert len(emi_mcqs) == 5
    emi_text = " ".join(q["question"].lower() for q in emi_mcqs)
    assert any(w in emi_text for w in ["pmmc", "moving iron", "wattmeter", "voltmeter", "bridge", "lvdt"])

    # 6. Electromagnetic Field Theory (EMF)
    emf_mcqs = generate_subject_mcqs(
        "ELECTROMAGNETIC FIELD THEORY (EMF)", 
        "Unit 1: Vector Algebra", 
        "Scalars and Vectors, Unit vector, Vector addition, Coulomb's Law, Gauss's law", 
        count=5
    )
    assert len(emf_mcqs) == 5
    emf_text = " ".join(q["question"].lower() for q in emf_mcqs)
    assert any(w in emf_text for w in ["maxwell", "poynting", "ampere", "skin depth", "dielectric", "coulomb"])


# ---------------------------------------------------------------------------
# 18. CIVIL, MECHANICAL, AND ECE DOMAIN-SPECIFIC MCQS
# ---------------------------------------------------------------------------

def test_generate_subject_mcqs_civil_mech_ece_domain_specific():
    """Verify that Civil, Mechanical, and ECE departments receive domain-specific questions."""
    # Civil - Surveying
    ce_mcqs = generate_subject_mcqs(
        "SURVEYING", 
        "Unit 1: Chain and Compass Surveying", 
        "Principles of surveying, Chain surveying, Compass surveying, Prismatic compass, Local attraction", 
        count=5
    )
    assert len(ce_mcqs) == 5
    ce_text = " ".join(q["question"].lower() for q in ce_mcqs)
    assert any(w in ce_text for w in ["bearing", "local attraction", "leveling", "compass", "curvature", "surveying"])

    # Mechanical - Thermodynamics
    me_mcqs = generate_subject_mcqs(
        "THERMODYNAMICS", 
        "Unit 1: Basic Concepts and First Law", 
        "System, Boundary, Surroundings, Thermodynamic equilibrium, Zeroth law, First law of thermodynamics, Heat and Work", 
        count=5
    )
    assert len(me_mcqs) == 5
    me_text = " ".join(q["question"].lower() for q in me_mcqs)
    assert any(w in me_text for w in ["first law", "carnot", "clausius", "otto", "throttling", "entropy"])

    # ECE - VLSI Design
    ece_mcqs = generate_subject_mcqs(
        "VLSI DESIGN", 
        "Unit 1: MOS Transistor Theory", 
        "MOS Transistor Theory: nMOS, pMOS, CMOS fabrication, Inverter voltage transfer characteristics", 
        count=5
    )
    assert len(ece_mcqs) == 5
    ece_text = " ".join(q["question"].lower() for q in ece_mcqs)
    assert any(w in ece_text for w in ["cmos", "pmos", "setup time", "power", "stick", "vlsi"])


# ---------------------------------------------------------------------------
# 19. SEED-BASED QUESTION REGENERATION AND OPTION SHUFFLING
# ---------------------------------------------------------------------------

def test_generate_subject_mcqs_seed_variety_and_shuffling():
    """Verify that different seeds produce fresh questions and randomized option placements."""
    mcqs_seed1 = generate_subject_mcqs("POWER SYSTEMS - II (PS-II)", "Unit 1: Transmission Line Parameters", count=4, seed=123)
    mcqs_seed2 = generate_subject_mcqs("POWER SYSTEMS - II (PS-II)", "Unit 1: Transmission Line Parameters", count=4, seed=987)

    assert len(mcqs_seed1) == 4
    assert len(mcqs_seed2) == 4

    # Option keys must always be A, B, C, D
    for q in mcqs_seed1 + mcqs_seed2:
        assert set(q["options"].keys()) >= {"A", "B", "C", "D"}
        assert q["correct_option"] in {"A", "B", "C", "D"}
        # Correct option key must point to the correct text
        assert len(q["options"][q["correct_option"]]) > 0

    q1_text = [q["question"] for q in mcqs_seed1]
    q2_text = [q["question"] for q in mcqs_seed2]
    # Either the questions selected are different or the options are in a different permutation
    assert q1_text != q2_text or mcqs_seed1[0]["options"] != mcqs_seed2[0]["options"]


# ---------------------------------------------------------------------------
# 20. PRACTICE PROMPT EMBEDS SEED AND DIVERSITY DIRECTIVE
# ---------------------------------------------------------------------------

def test_build_practice_prompt_with_seed():
    """Verify build_practice_prompt accepts seed and adds diversity directive."""
    _, usr_prompt = build_practice_prompt(
        "POWER SYSTEMS - II", "Unit 1", 5, "Multiple Choice", 
        unit_topics="Transmission line parameters", seed=4242
    )
    assert "4242" in usr_prompt
    assert "Variation/Seed" in usr_prompt


# ---------------------------------------------------------------------------
# 21. SHORT ANSWER GENERATION ACROSS DOMAINS AND VARIETY
# ---------------------------------------------------------------------------

def test_generate_subject_short_answers_domain_specific_and_variety():
    """Verify that short answers generate domain-specific derivations and step-by-step solutions with variety."""
    # 1. EEE Power Systems
    ps_sa = generate_subject_short_answers("POWER SYSTEMS - II (PS-II)", "Unit 1: Transmission Line Parameters", count=3, seed=12)
    assert "### Question 1:" in ps_sa
    assert "**Answer & Step-by-Step Solution:**" in ps_sa
    assert "**Key Takeaway / Explanation:**" in ps_sa
    assert VERIFICATION_LINE in ps_sa
    ps_lower = ps_sa.lower()
    assert any(k in ps_lower for k in ["ferranti", "insulator", "surge impedance", "corona", "transmission"])

    # 2. Civil Surveying
    ce_sa = generate_subject_short_answers("SURVEYING", "Unit 1: Chain and Compass", count=2, seed=34)
    assert "### Question 1:" in ce_sa
    ce_lower = ce_sa.lower()
    assert any(k in ce_lower for k in ["bearing", "bending", "surveying", "quadrantal"])

    # 3. Seed Variety
    sa1 = generate_subject_short_answers("ELECTRICAL MACHINES-I", "Unit 1", count=2, seed=10)
    sa2 = generate_subject_short_answers("ELECTRICAL MACHINES-I", "Unit 1", count=2, seed=90)
    assert sa1 != sa2


# ---------------------------------------------------------------------------
# 22. SUBJECT NOTES AND MATERIALS INDEXING & RETRIEVAL
# ---------------------------------------------------------------------------

def test_subject_notes_retrieval_all_semesters():
    """Verify that all 99 notes across EEE Semesters 3, 4, 5, 6, and 7 are indexed and retrievable."""
    import os
    db = DatabaseManager()

    # Total notes indexed for EEE should be 99
    all_eee_notes = db.get_subject_notes("EEE", 3) + \
                    db.get_subject_notes("EEE", 4) + \
                    db.get_subject_notes("EEE", 5) + \
                    db.get_subject_notes("EEE", 6) + \
                    db.get_subject_notes("EEE", 7)
    assert len(all_eee_notes) == 99, f"Expected 99 EEE notes, got {len(all_eee_notes)}"

    # Check key subjects
    emf_notes = db.get_subject_notes("EEE", 3, "ELECTROMAGNETIC FIELD THEORY (EMF)")
    assert len(emf_notes) == 8

    ism_notes = db.get_subject_notes("EEE", 4, "INDUCTION AND SYNCHRONOUS MACHINES (ISM)")
    assert len(ism_notes) == 22

    ac_notes = db.get_subject_notes("EEE", 4, "ANALOG CIRCUITS (AC)")
    assert len(ac_notes) == 5

    cse_notes = db.get_subject_notes("EEE", 4, "CONTROL SYSTEMS ENGINEERING (CSE)")
    assert len(cse_notes) == 2

    psoc_notes = db.get_subject_notes("EEE", 7, "POWER SYSTEM OPERATION AND CONTROL (PSOC)")
    assert len(psoc_notes) == 9

    sgp_notes = db.get_subject_notes("EEE", 6, "SWITCHGEAR AND PROTECTION (SGP)")
    assert len(sgp_notes) == 4

    edsp_notes = db.get_subject_notes("EEE", 7, "ELEMENTS OF DIGITAL SIGNAL PROCESSING (EDSP)")
    assert len(edsp_notes) == 7

    ms_notes = db.get_subject_notes("EEE", 7, "MANAGEMENT SCIENCE (MS)")
    assert len(ms_notes) == 6

    uee_notes = db.get_subject_notes("EEE", 7, "UTILIZATION OF ELECTRICAL ENERGY (UEE)")
    assert len(uee_notes) == 3


def test_subject_notes_unit_filtering_and_file_existence():
    """Verify unit-specific filtering and that physical note files exist on disk."""
    import os
    db = DatabaseManager()

    # EMF Unit 1 and Unit 2 notes
    emf_u1 = db.get_subject_notes("EEE", 3, "ELECTROMAGNETIC FIELD THEORY (EMF)", unit_number=1)
    assert len(emf_u1) >= 1
    for n in emf_u1:
        assert n["unit_number"] == 1
        assert os.path.exists(n["abs_filepath"]), f"File missing on disk: {n['abs_filepath']}"
        assert n["file_size"] > 0
        assert n["file_type"].lstrip(".") in ("pdf", "doc", "docx")
        assert "formatted_size" in n

    emf_u2 = db.get_subject_notes("EEE", 3, "ELECTROMAGNETIC FIELD THEORY (EMF)", unit_number=2)
    assert len(emf_u2) == 2
    for n in emf_u2:
        assert n["unit_number"] == 2
        assert os.path.exists(n["abs_filepath"])

    # ISM Unit 1 notes
    ism_u1 = db.get_subject_notes("EEE", 4, "INDUCTION AND SYNCHRONOUS MACHINES (ISM)", unit_number=1)
    assert len(ism_u1) >= 1
    for n in ism_u1:
        assert n["unit_number"] == 1
        assert os.path.exists(n["abs_filepath"])


def test_available_note_courses_for_semester():
    """Verify distinct course discovery with note counts and formatted sizes for a semester."""
    db = DatabaseManager()

    sem4_courses = db.get_available_note_courses_for_semester("EEE", 4)
    assert len(sem4_courses) == 3
    course_titles = [c["course_title"] for c in sem4_courses]
    assert "ANALOG CIRCUITS (AC)" in course_titles
    assert "CONTROL SYSTEMS ENGINEERING (CSE)" in course_titles
    assert "INDUCTION AND SYNCHRONOUS MACHINES (ISM)" in course_titles

    sem6_courses = db.get_available_note_courses_for_semester("EEE", 6)
    assert len(sem6_courses) == 2
    s6_titles = [c["course_title"] for c in sem6_courses]
    assert any("MEASUR" in t for t in s6_titles)
    assert any("SWITCHGEAR" in t for t in s6_titles)


def test_get_note_by_id():
    """Verify single note retrieval by ID."""
    db = DatabaseManager()
    note = db.get_note_by_id(1)
    assert note is not None
    assert "title" in note
    assert "filename" in note
    assert "abs_filepath" in note
    assert "formatted_size" in note






