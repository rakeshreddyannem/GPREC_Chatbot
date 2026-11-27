"""
Subject Assistance Module for GPREC AI Student Assistant.
Provides pure prompt builders, topic parsing, caching, and tutoring logic for B.Tech subjects.
"""

import os
import re
import time
import json
import random
import hashlib
from typing import Dict, Any, List, Optional, Tuple

import config

VERIFICATION_LINE = "AI explanation. Verify important results with your textbook."
OUTSIDE_SUBJECT_NOTE_PREFIX = "Note: This topic appears to be outside the selected subject"
COLLEGE_FACT_REDIRECT = (
    "For college administrative information (such as fees, faculty details, and campus notices), "
    "please visit the **Ask AI** page."
)

PRACTICE_DISCLAIMER = "AI-generated practice questions, not from previous exam papers"


def split_topics(topics_str: str) -> List[str]:
    """
    Splits syllabus topics on commas, semicolons, dashes, and bullet marks.
    Cleans up whitespace, bullet markers, and punctuation, preserving unique ordered topics.
    """
    if not topics_str or not isinstance(topics_str, str):
        return []
    
    # Split on commas, semicolons, bullets, double-bars, newlines, or dashes separating capitalized phrases
    raw_parts = re.split(
        r'[,;•‖\n]+|\s+[-–—]\s+|(?<=[a-z0-9])\s*[-–—]\s*(?=[A-Z])|(?<=[a-z])\.\s+(?=[A-Z])',
        topics_str
    )
    cleaned_topics = []
    seen = set()

    for part in raw_parts:
        # Strip bullets, numbers, hyphens and extra whitespace
        item = re.sub(r'^[\s\-*•\d.)]+', '', part).strip()
        # Strip optional Unit/Chapter prefix if present
        item = re.sub(r'^(?:unit|chapter)\s*\d+\s*[:\-]\s*', '', item, flags=re.IGNORECASE).strip()
        # Clean trailing punctuation like period, colon, or dash
        item = re.sub(r'[\s.:\-]+$', '', item).strip()
        
        if len(item) > 1 and item.lower() not in seen:
            seen.add(item.lower())
            cleaned_topics.append(item)

    return cleaned_topics


def get_subject_cache_key(
    subject: str, 
    unit: str, 
    topic: str, 
    content_type: str, 
    extra: str = "",
    branch: str = "",
    scheme: str = ""
) -> str:
    """
    Produces a stable, deterministic cache key for the SQLite answer_cache table.
    Incorporates (branch, scheme, subject, unit, topic, content_type).
    """
    norm_subject = re.sub(r'\s+', '_', (subject or "any").strip().lower())
    norm_unit = re.sub(r'\s+', '_', str(unit or "all").strip().lower())
    norm_topic = re.sub(r'\s+', '_', str(topic or "general").strip().lower())
    norm_type = (content_type or "misc").strip().lower()
    norm_branch = re.sub(r'\s+', '_', str(branch or "").strip().lower())
    norm_scheme = re.sub(r'\s+', '_', str(scheme or "").strip().lower())
    norm_extra = re.sub(r'\s+', '_', str(extra or "").strip().lower())
    
    parts = ["subassist", norm_type]
    if norm_branch:
        parts.append(norm_branch)
    if norm_scheme:
        parts.append(norm_scheme)
    parts.extend([norm_subject, norm_unit, norm_topic])
    if norm_extra:
        parts.append(norm_extra)
        
    return ":".join(parts)


def clear_subject_cache(db: Any = None) -> int:
    """
    Clears subject assistant cached entries (explanations, revision notes, practice sets)
    from answer_cache. Called when the syllabus is re-ingested.
    """
    if db is not None:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM answer_cache WHERE normalized_query LIKE 'subassist:%'")
                count = cursor.rowcount
                conn.commit()
                return count
        except Exception:
            return 0
    return 0


def is_college_fact_query(query: str) -> bool:
    """
    Identifies queries that ask about college administrative facts rather than subject concepts.
    """
    q_lower = (query or "").lower().strip()
    college_keywords = [
        "fee", "fees", "tuition", "challan", "scholarship",
        "hod", "principal", "faculty", "professor", "associate professor", "assistant professor", "staff",
        "timetable", "timetables", "time table", "time tables", "exam schedule", "exam schedules",
        "circular", "circulars", "notice", "notices", "last date",
        "hostel", "mess", "bus", "transport", "canteen", "library", "admissions", "intake", "cutoff",
        "placement", "placements", "highest package", "average package", "who is the principal", "who is hod"
    ]
    # Check exact word matches or key phrases
    for kw in college_keywords:
        if re.search(rf'\b{re.escape(kw)}\b', q_lower):
            return True
    return False


def is_outside_subject(
    query: str, 
    subject_name: str, 
    units_data: Optional[List[Dict[str, Any]]] = None
) -> bool:
    """
    Heuristically checks if a query is clearly about a distinct engineering domain/subject.
    """
    q_lower = (query or "").lower().strip()
    subj_lower = (subject_name or "").lower().strip()

    # Domain indicators
    electrical_keywords = [
        "transformer", "induction motor", "dc motor", "synchronous motor", "thevenin", "norton", 
        "kirchhoff", "power factor", "transmission line", "ferranti", "buchholz", "substation",
        "flux", "emf equation", "rlc", "impedance", "armature", "stator", "rotor", "superposition theorem"
    ]
    cs_keywords = [
        "sql", "database", "rdbms", "b-tree", "avl tree", "heap", "stack", "queue", "linked list",
        "acid properties", "normalization", "hashing", "graph traversal", "bfs", "dfs", "binary search tree",
        "concurrency control", "two-phase locking", "serializability"
    ]
    civil_keywords = [
        "concrete", "slump test", "beam deflection", "shear force", "bending moment", "soil mechanics",
        "surveying", "cement", "rebar", "hydraulics"
    ]
    mech_keywords = [
        "carnot cycle", "rankine cycle", "ic engine", "thermodynamics", "refrigeration", "entropy",
        "lathe", "milling", "gear train", "bernoulli"
    ]

    is_cs_subject = any(k in subj_lower for k in ["data structure", "database", "algorithm", "software", "computer", "dbms", "ads", "dbs"])
    is_eee_subject = any(k in subj_lower for k in ["electrical", "power system", "machine", "circuit", "control system", "electronics", "eee"])
    
    # If the student selected a CS subject but asks about electrical hardware/machines
    if is_cs_subject:
        if any(re.search(rf'\b{re.escape(w)}\b', q_lower) for w in electrical_keywords):
            return True
        if any(re.search(rf'\b{re.escape(w)}\b', q_lower) for w in civil_keywords):
            return True
        if any(re.search(rf'\b{re.escape(w)}\b', q_lower) for w in mech_keywords):
            return True

    # If the student selected an EEE subject but asks about CS databases or trees
    if is_eee_subject:
        if any(re.search(rf'\b{re.escape(w)}\b', q_lower) for w in cs_keywords):
            return True
        if any(re.search(rf'\b{re.escape(w)}\b', q_lower) for w in civil_keywords):
            return True

    # Check against unit titles and topics if provided
    if units_data:
        all_topics_text = " ".join([
            f"{u.get('unit_title', '')} {u.get('topics', '')}" for u in units_data
        ]).lower()
        # If words in question have 0 overlap with topics text and query has distinct keywords
        q_words = [w for w in re.findall(r'[a-zA-Z]{4,}', q_lower) if w not in {"explain", "what", "which", "how", "with", "example", "problem", "does", "step", "steps"}]
        if q_words and all(w not in all_topics_text and w not in subj_lower for w in q_words):
            if any(re.search(rf'\b{re.escape(w)}\b', q_lower) for w in electrical_keywords + civil_keywords + mech_keywords + cs_keywords):
                return True

    return False


def _format_topic_short(topic: str, max_chars: int = 38) -> str:
    """Format a syllabus topic into a clean, concise topic title suitable for example doubt buttons."""
    t = re.sub(r'^(?:introduction|overview|basics?)\s*[:\-]\s*', '', topic, flags=re.IGNORECASE).strip()
    if not t:
        t = topic.strip()
    if len(t) > max_chars:
        t = t[:max_chars].rsplit(' ', 1)[0] + '...'
    return t


def generate_example_doubts(
    subject_title: str, 
    first_unit_topics: Optional[str] = None
) -> List[str]:
    """
    Generates 3 practical example doubt questions for the selected subject.
    """
    st_lower = (subject_title or "").lower()
    
    if "data structure" in st_lower or "ads" in st_lower:
        return [
            "How do I convert an infix expression to postfix using a stack?",
            "Explain polynomial addition using linked lists with an example.",
            "What is the difference between linear and non-linear data structures?"
        ]
    elif "database" in st_lower or "dbs" in st_lower or "dbms" in st_lower:
        return [
            "What are the ACID properties in database transactions with real examples?",
            "How do I design an ER diagram and map it to relational tables?",
            "Explain 1NF, 2NF, and 3NF normalization with a step-by-step example."
        ]
    
    is_non_numerical = any(k in st_lower for k in [
        "gender", "humanities", "management", "ethics", "english", 
        "constitution", "values", "sociology", "history", "economics", "law"
    ])

    # Generic topic parsing from first unit topics
    if first_unit_topics:
        topics = split_topics(first_unit_topics)
        if len(topics) >= 3:
            t0 = _format_topic_short(topics[0])
            t1 = _format_topic_short(topics[1])
            t2 = _format_topic_short(topics[2])
            q2 = f"What are key concepts in {t1}?" if is_non_numerical else f"What are key formulas and operations in {t1}?"
            q3 = f"What are common exam questions on {t2}?" if is_non_numerical else f"What are common mistakes in {t2}?"
            return [
                f"Can you explain {t0} with a step-by-step example?",
                q2,
                q3
            ]
        elif topics:
            t0 = _format_topic_short(topics[0])
            q3 = f"What are the key real-world case studies in {t0}?" if is_non_numerical else f"Can you solve a problem related to {t0}?"
            return [
                f"Explain {t0} step-by-step with an example.",
                f"What are the fundamental concepts in {subject_title}?",
                q3
            ]
            
    return [
        f"What are the fundamental concepts of {subject_title}?",
        f"Can you explain a key worked example for Unit 1 in {subject_title}?",
        f"What are 3 common mistakes students make in this subject?"
    ]


def _format_units_scope(units_data: Optional[List[Dict[str, Any]]]) -> str:
    """Formats syllabus units and topics into a clean text block."""
    if not units_data:
        return "No specific unit breakdown available in syllabus database."
        
    lines = []
    for u in units_data:
        num = u.get("unit_number", "")
        title = u.get("unit_title", "")
        topics = u.get("topics", "")
        tb = u.get("textbooks", "")
        lines.append(f"Unit {num}: {title}\nTopics: {topics}")
        if tb:
            lines.append(f"Textbooks: {tb}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# PURE PROMPT BUILDERS
# ---------------------------------------------------------------------------

def build_doubt_prompt(
    subject_name: str, 
    units_data: Optional[List[Dict[str, Any]]], 
    query: str, 
    history: Optional[List[Dict[str, str]]] = None
) -> Tuple[str, str]:
    """
    Builds system prompt and user prompt for answering a student doubt.
    Uses up to the last 3 turns (6 messages) from history for context.
    """
    system_prompt = f"""You are a patient academic tutor for an undergraduate B.Tech engineering student in India.
Your mission is to help the student understand engineering concepts clearly and solve problems confidently.

Guidelines:
1. Tone & Style: Explain in plain, accessible language with short sentences. Present logical steps before jumping to the final answer.
2. Syllabus Scope: You are tutoring for the subject: "{subject_name}".
   - Use the syllabus units and topics provided in the context when defining what the subject covers.
   - Never add imaginary topics to the official syllabus.
   - If the student's question is about a different engineering subject or topic outside this syllabus, still answer the academic question helpfully, but prefix or end your answer with a single line:
     "Note: This topic appears to be outside the selected subject ({subject_name}) syllabus."
3. Formulas & Numerical Problems:
   - Always format mathematical and engineering formulas clearly in LaTeX between $ signs (or $$ for display blocks), including proper physical units.
   - For numerical problems, strictly show: Given values, Formula, Step-by-step substitution, and Final answer with units.
4. Accuracy & Limitations:
   - If you are unsure about any theorem, value, or fact, say so honestly in one sentence and advise the student to consult the prescribed textbook.
   - Never fabricate textbook page numbers, equation numbers, or examination years.
   - No college administration facts (fees, faculty contact details, admissions, timetables, notices). If asked, instruct the student to use the **Ask AI** page.
5. Direct Response Constraint:
   - CRITICAL: Output ONLY the final student-facing answer directly. Do NOT output "Analyze the Request", planning commentary, or drafting scratchpads.
6. Mandatory Ending:
   - Every response must end with this exact line on a new line:
     "{VERIFICATION_LINE}"
"""

    scope_text = _format_units_scope(units_data)
    
    # Format up to last 3 conversation turns (6 messages)
    history_str = ""
    if history:
        recent_turns = history[-6:]
        conv_lines = []
        for msg in recent_turns:
            role = "Student" if msg.get("role") == "user" else "Tutor"
            content = msg.get("content", "")
            conv_lines.append(f"{role}: {content}")
        if conv_lines:
            history_str = "--- PREVIOUS CONVERSATION (LAST 3 TURNS) ---\n" + "\n".join(conv_lines) + "\n\n"

    user_prompt = f"""--- SUBJECT SCOPE ---
Subject: {subject_name}
{scope_text}

{history_str}Student Doubt: {query}

Tutor Explanation (begin directly with the explanation without any meta-commentary or scratchpad):"""

    return system_prompt, user_prompt


def build_topic_explanation_prompt(
    subject_name: str, 
    unit_title: str, 
    topic: str, 
    user_notes: Optional[str] = None,
    syllabus_context: Optional[str] = None
) -> Tuple[str, str]:
    """
    Builds system and user prompt for explaining a specific syllabus topic.
    Mandatory structure:
    - Short Intro
    - Step-by-Step Explanation
    - Key Formulas (in LaTeX $ ... $ with units)
    - One Worked Example
    - 3 Common Mistakes
    - Verification Line
    """
    system_prompt = f"""You are a patient, expert engineering tutor for a B.Tech student in India.
Explain the requested syllabus topic with maximum clarity.

Structure your response using these exact section headings:
### 1. Short Intro
(2-3 concise sentences defining the concept)

### 2. Step-by-Step Explanation
(Core principles broken into numbered, logical steps)

### 3. Key Formulas
(All equations in LaTeX between $ signs, specifying every symbol and its units)

### 4. Worked Example
(A practical engineering problem: Given values -> Applicable formula -> Step-by-step substitution -> Final result with units)

### 5. 3 Common Mistakes
(Three specific pitfalls students make in exams or derivations, and how to avoid them)

Guidelines:
- Plain language, short sentences.
- Always include LaTeX formulas with units.
- Never invent textbook page numbers, equation numbers, or exam years.
- CRITICAL: Output ONLY the final response directly. Do NOT output "Analyze the Request", thinking steps, or drafting notes. Begin immediately with "### 1. Short Intro".
- End your explanation with the exact line:
  "{VERIFICATION_LINE}"
"""

    notes_str = f"\nStudent Specific Request/Doubt: {user_notes}\n" if user_notes else ""
    ctx_str = f"\nSyllabus Context:\n{syllabus_context}\n" if syllabus_context else ""

    user_prompt = f"""Subject: {subject_name}
Unit: {unit_title}
Topic to Explain: {topic}{notes_str}{ctx_str}

Please generate the comprehensive explanation following the 5-part structure. Begin directly with '### 1. Short Intro' without any preamble or scratchpad."""

    return system_prompt, user_prompt


def extract_mcq_json(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Extracts and parses a list of MCQ dictionaries from text.
    Handles:
    - ```json ... ``` or ``` ... ``` code blocks
    - Bare JSON arrays: [ { ... } ]
    - Unescaped LaTeX backslashes (\\frac, \\alpha, \\{, \\in)
    - Trailing commas in objects/arrays
    - Text/reasoning preceding or following the JSON block
    - Normalizes options A, B, C, D, correct_option, and explanation
    """
    if not text or not isinstance(text, str):
        return None

    raw_candidates = []

    # 1. Look for ```json ... ``` or ``` ... ``` code blocks
    for m in re.finditer(r'```(?:json)?\s*(\[\s*\{[\s\S]*?\}\s*\])\s*```', text, re.IGNORECASE):
        raw_candidates.append(m.group(1))

    # 2. Look for any bracketed array containing objects: [ { ... } ]
    start_idx = text.find('[')
    end_idx = text.rfind(']')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        raw_candidates.append(text[start_idx:end_idx + 1])

    def try_parse(candidate: str) -> Optional[List[Dict[str, Any]]]:
        if not candidate:
            return None
        # Try direct json.loads
        try:
            val = json.loads(candidate)
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val
        except Exception:
            pass

        # Try removing trailing commas
        cleaned = re.sub(r',\s*([\]}])', r'\1', candidate)
        try:
            val = json.loads(cleaned)
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val
        except Exception:
            pass

        # Try escaping unescaped backslashes (common in LaTeX formulas)
        # Escape any backslash that is not followed by a valid JSON escape char (" \ / b f n r t u)
        escaped = re.sub(r'\\(?![/"\\bfnrtu])', r'\\\\', cleaned)
        try:
            val = json.loads(escaped)
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val
        except Exception:
            pass

        return None

    parsed_data = None
    for cand in raw_candidates:
        res = try_parse(cand)
        if res:
            parsed_data = res
            break

    if not parsed_data or not isinstance(parsed_data, list):
        return None

    valid_questions = []
    for idx, item in enumerate(parsed_data):
        if not isinstance(item, dict):
            continue
        q_text = item.get("question") or item.get("question_text") or item.get("q") or ""
        options = item.get("options") or item.get("choices") or {}
        if not q_text or not isinstance(options, dict) or len(options) < 2:
            continue

        norm_options = {}
        for k, v in options.items():
            norm_options[str(k).strip().upper()] = str(v).strip()

        correct = str(item.get("correct_option") or item.get("answer") or item.get("correct") or "A").strip().upper()
        opt_match = re.search(r'\b([A-D])\b', correct)
        if opt_match:
            correct = opt_match.group(1)
        elif correct and correct[0] in norm_options:
            correct = correct[0]
        else:
            correct = list(norm_options.keys())[0]

        explanation = str(item.get("explanation") or item.get("solution") or item.get("reason") or "Correct answer based on syllabus concepts.").strip()

        valid_questions.append({
            "question_number": item.get("question_number", idx + 1),
            "question": str(q_text).strip(),
            "options": norm_options,
            "correct_option": correct,
            "explanation": explanation
        })

    return valid_questions if len(valid_questions) >= 1 else None


def shuffle_question_options(q: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    q_copy = dict(q)
    orig_options = dict(q.get("options", {}))
    orig_correct = str(q.get("correct_option", "A")).strip().upper()
    if orig_correct not in orig_options:
        return q_copy
    correct_text = orig_options[orig_correct]
    opt_values = list(orig_options.values())
    rng.shuffle(opt_values)
    new_options = {chr(65 + i): val for i, val in enumerate(opt_values)}
    new_correct = next(k for k, v in new_options.items() if v == correct_text)
    q_copy["options"] = new_options
    q_copy["correct_option"] = new_correct
    return q_copy

def generate_subject_mcqs(
    subject_name: str, 
    unit_title: str, 
    unit_topics: Optional[str] = None, 
    count: int = 5,
    seed: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Generates high-yield, syllabus-accurate multiple choice questions for B.Tech subjects.
    Provides dedicated, domain-tailored questions for:
    - EEE: Power Systems, Electrical Machines, Control Systems, Power Electronics, Measurements, EMF, EV
    - CE: Surveying, Strength of Materials, Fluid Mechanics/Hydraulics
    - ME: Thermodynamics, Machine Design & Manufacturing
    - ECE: VLSI Design, Signals & Communications
    - CSE/CSM: Machine Learning, Java/OOP, Data Structures, OS, DBMS, Networks
    - Mathematics: Calculus, Differential Equations, Linear Algebra, Probability & Statistics
    - Dynamic topic synthesizer tailored to syllabus topics for any specialized or elective course.
    """
    count = max(3, min(10, int(count)))
    rng = random.Random(seed) if seed is not None else random.Random()
    text_corpus = f" {subject_name} {unit_title} {unit_topics or ''} ".lower()

    def has_any(*patterns: str) -> bool:
        for p in patterns:
            if re.search(r'\b' + re.escape(p) + r'\b', text_corpus, re.IGNORECASE):
                return True
        return False

    pool: List[Dict[str, Any]] = []

    # 1. EEE: Power Systems & Transmission & Distribution
    if has_any("power system", "power systems", "ps-i", "ps-ii", "ps1", "ps2", "ps3", "psa", "psoc", 
               "switchgear", "sgp", "transmission line", "transmission lines", "overhead line", 
               "distribution system", "distribution systems", "eds", "smart grid", "sgt", "hvdc", "facts", 
               "insulator", "insulators", "corona", "ferranti", "transients", "substation"):
        pool = [
            {
                "question": "What is the primary cause of the Ferranti effect observed in long unloaded or lightly loaded high-voltage transmission lines?",
                "options": {
                    "A": "Line charging capacitance drawing leading current through series line inductance, making receiving end voltage exceed sending end voltage.",
                    "B": "Excessive inductive reactance causing heavy active power dissipation.",
                    "C": "Ground fault transients reflecting traveling waves at the source terminals.",
                    "D": "Corona discharge ionizing atmospheric air around outer conductor bundles."
                },
                "correct_option": "A",
                "explanation": "In long AC transmission lines under light load or open circuit, line shunt capacitance draws leading charging current that produces a voltage rise across the series inductance, causing $V_R > V_S$."
            },
            {
                "question": "What is the primary technical advantage of using bundled conductors in extra-high-voltage (EHV) overhead transmission lines?",
                "options": {
                    "A": "Increases Geometric Mean Radius (GMR), lowering line reactance and reducing corona loss and radio interference.",
                    "B": "Decreases conductor cross-sectional area to minimize steel core weight.",
                    "C": "Completely eliminates ground fault currents in ungrounded neutral systems.",
                    "D": "Increases surge impedance to reduce power transfer capacity."
                },
                "correct_option": "A",
                "explanation": "Bundling multiple sub-conductors increases effective self-GMR ($D_s$), which reduces line inductance ($L \\propto \\ln(D_m/D_s)$), increases capacitance, increases Surge Impedance Loading (SIL), and mitigates corona formation."
            },
            {
                "question": "How is the string efficiency of a multi-unit suspension insulator string defined?",
                "options": {
                    "A": "$\\text{String Efficiency} = \\frac{\\text{Flashover Voltage Across Whole String}}{n \\times \\text{Voltage Across Unit Nearest to Conductor}} \\times 100\\%$",
                    "B": "$\\text{String Efficiency} = \\frac{\\text{Voltage of Topmost Unit}}{n \\times \\text{Total String Voltage}} \\times 100\\%$",
                    "C": "$\\text{String Efficiency} = \\frac{\\text{Leakage Current}}{\\text{Capacitive Current}} \\times 100\\%$",
                    "D": "$\\text{String Efficiency} = n \\times \\frac{\\text{Operating Line Voltage}}{\\text{Withstand Voltage}} \\times 100\\%$"
                },
                "correct_option": "A",
                "explanation": "Due to shunt capacitance to the tower cross-arm, the voltage distribution across insulator discs is non-uniform, with the bottom disc nearest to the conductor experiencing maximum dielectric stress."
            },
            {
                "question": "Skin effect in an AC transmission conductor results in which of the following physical distributions?",
                "options": {
                    "A": "Higher current density near the outer conductor surface and reduced current density at the conductor center.",
                    "B": "Uniform current density across the entire conductor cross-section regardless of frequency.",
                    "C": "Current concentration strictly at the geometric center of the conductor cross-section.",
                    "D": "Zero magnetic flux linkage inside the solid metal core."
                },
                "correct_option": "A",
                "explanation": "Inner conductor filaments link more internal magnetic flux and thus have higher self-inductance than outer filaments, forcing AC current to crowd toward the conductor periphery (skin depth $\\delta = \\sqrt{2/(\\omega \\mu \\sigma)}$)."
            },
            {
                "question": "For a lossless three-phase transmission line with characteristic surge impedance $Z_c$, what is the Surge Impedance Loading (SIL)?",
                "options": {
                    "A": "$\\text{SIL} = \\frac{V_L^2}{Z_c}$",
                    "B": "$\\text{SIL} = \\frac{V_L}{\\sqrt{3} Z_c}$",
                    "C": "$\\text{SIL} = V_L^2 \\cdot Z_c$",
                    "D": "$\\text{SIL} = \\frac{Z_c}{V_L^2}$"
                },
                "correct_option": "A",
                "explanation": "At surge impedance loading, reactive power generated by line capacitance ($Q_C = V_L^2 / X_C$) exactly equals reactive power consumed by line inductance ($Q_L = I^2 X_L$), and the line delivers active power $P_0 = V_L^2 / Z_c$ at unity power factor."
            },
            {
                "question": "In symmetrical fault calculations, which sequence component exists exclusively during ground-involved unbalanced faults (e.g., Single Line-to-Ground)?",
                "options": {
                    "A": "Zero sequence component ($I_{a0}$)",
                    "B": "Positive sequence component ($I_{a1}$)",
                    "C": "Negative sequence component ($I_{a2}$)",
                    "D": "Sub-transient quadrature sequence"
                },
                "correct_option": "A",
                "explanation": "Zero sequence currents require a neutral return path to ground; they cannot circulate in an isolated neutral system and are absent in balanced 3-phase faults."
            },
            {
                "question": "What is the critical breakdown electric field strength (dielectric strength) of atmospheric air at standard temperature and pressure ($25^\\circ\\text{C}, 76\\text{ cm Hg}$)?",
                "options": {
                    "A": "$30\\text{ kV/cm (peak)} \\approx 21.2\\text{ kV/cm (RMS)}$",
                    "B": "$10\\text{ kV/cm (peak)}$",
                    "C": "$100\\text{ kV/cm (peak)}$",
                    "D": "$5\\text{ kV/cm (RMS)}$"
                },
                "correct_option": "A",
                "explanation": "When surface electric field intensity exceeds the disruptive critical gradient of air ($30\\text{ kV (peak)/cm}$), localized dielectric breakdown occurs, initiating corona discharge with ozone formation."
            },
            {
                "question": "Which type of circuit breaker utilizes high electronegative gas properties for ultra-fast arc quenching in modern EHV/UHV substations?",
                "options": {
                    "A": "Sulphur Hexafluoride ($\\text{SF}_6$) Circuit Breaker",
                    "B": "Air Blast Circuit Breaker",
                    "C": "Minimum Oil Circuit Breaker (MOCB)",
                    "D": "Plain Break Oil Circuit Breaker"
                },
                "correct_option": "A",
                "explanation": "$\\text{SF}_6$ is a non-toxic, chemically inert, highly electronegative gas that absorbs free electrons in the arc column to form immobile negative ions, rapidly restoring dielectric withstand strength."
            }
        ]

    # 2. EEE: Electrical Machines (DC Machines, Transformers, Induction, Synchronous)
    elif has_any("electrical machine", "electrical machines", "emc-i", "emc-ii", "emc1", "emc2", 
                 "dc machine", "dc machines", "dcmt", "induction machine", "induction machines", 
                 "induction motor", "induction motors", "synchronous machine", "synchronous machines", 
                 "alternator", "alternators", "transformer", "transformers", "ism", "special machines", "smc"):
        pool = [
            {
                "question": "In a DC motor, what is the fundamental governing role of the generated Back EMF ($E_b = V - I_a R_a$)?",
                "options": {
                    "A": "Acts as an automatic governor that dynamically regulates armature current according to mechanical load demands.",
                    "B": "Increases electrical copper losses in field windings to stabilize thermal dissipation.",
                    "C": "Reverses the magnetic polarity of inter-pole windings during steady-state rotation.",
                    "D": "Prevents mechanical brush friction on the commutator segments."
                },
                "correct_option": "A",
                "explanation": "Back EMF $E_b = \\frac{\\Phi Z N P}{60 A}$ opposes applied terminal voltage $V$; when load increases, speed drops, $E_b$ decreases, allowing higher armature current $I_a = (V - E_b)/R_a$ to produce the required torque."
            },
            {
                "question": "Why is the Open-Circuit (OC) test of a single-phase transformer conducted at rated voltage on the Low-Voltage (LV) winding while leaving the HV winding open?",
                "options": {
                    "A": "To measure rated core (iron) losses accurately while operating at manageable rated voltage and safe test conditions.",
                    "B": "To measure full-load copper losses with maximum primary winding current.",
                    "C": "To determine leakage reactance and equivalent series winding resistance.",
                    "D": "To test the dielectric breakdown of high-voltage winding insulation oil."
                },
                "correct_option": "A",
                "explanation": "In an OC test, rated voltage is applied to the LV winding with rated frequency. Armature current is only the small no-load magnetizing current ($I_0$), so copper loss is negligible and wattmeter reading reflects core loss."
            },
            {
                "question": "What is the operating slip $s$ of a three-phase induction motor running at rotor speed $N$ when synchronous stator speed is $N_s$?",
                "options": {
                    "A": "$s = \\frac{N_s - N}{N_s}$",
                    "B": "$s = \\frac{N - N_s}{N}$",
                    "C": "$s = \\frac{N_s}{N}$",
                    "D": "$s = \\frac{N_s - N}{N}$"
                },
                "correct_option": "A",
                "explanation": "Fractional slip $s = (N_s - N)/N_s$ represents the relative speed between stator rotating magnetic field and rotor conductors, determining induced rotor frequency $f_r = s f$."
            },
            {
                "question": "How does adding external resistance to the rotor circuit of a wound-rotor (slip-ring) induction motor affect the maximum developed torque ($T_{max}$)?",
                "options": {
                    "A": "Maximum torque magnitude remains constant, but the slip at which maximum torque occurs shifts to a higher value.",
                    "B": "Maximum torque increases proportionally with the added rotor resistance.",
                    "C": "Maximum torque decreases inversely with rotor resistance squared.",
                    "D": "Both maximum torque magnitude and synchronous speed increase."
                },
                "correct_option": "A",
                "explanation": "Peak torque $T_{max} = \\frac{3}{2\\omega_s} \\frac{V_1^2}{2 X_2'}$ depends only on stator voltage and leakage reactance, not on rotor resistance; rotor resistance only changes the slip at which breakdown torque occurs ($s_{mT} = R_2 / X_2$)."
            },
            {
                "question": "What is the primary operational function of damper (amortisseur) windings in a salient-pole synchronous machine?",
                "options": {
                    "A": "Damp out rotor oscillations (hunting) during load transients and provide starting induction torque as an induction motor.",
                    "B": "Supply DC field excitation current to rotor pole windings.",
                    "C": "Eliminate armature reaction cross-magnetizing effects under steady unity power factor.",
                    "D": "Increase the mechanical inertia of the exciter rotor."
                },
                "correct_option": "A",
                "explanation": "Damper windings embedded in rotor pole faces experience induced currents whenever relative motion exists between the rotor and the stator revolving field, providing damping torque against hunting and starting torque as an induction motor."
            },
            {
                "question": "The V-curves of a synchronous motor graphically illustrate the relationship between which two operational parameters at constant mechanical power output?",
                "options": {
                    "A": "Armature current ($I_a$) versus DC Field excitation current ($I_f$)",
                    "B": "Electromagnetic torque versus speed",
                    "C": "Terminal voltage versus load angle ($\\delta$)",
                    "D": "Power factor versus rotor slip"
                },
                "correct_option": "A",
                "explanation": "V-curves show armature current $I_a$ on the y-axis vs field current $I_f$ on the x-axis. Minimum $I_a$ corresponds to unity power factor; under-excitation draws lagging reactive current, and over-excitation draws leading reactive current."
            },
            {
                "question": "Why are distribution transformers designed to achieve maximum efficiency at approximately $50\\% - 70\\%$ of full rated load rather than $100\\%$ full load?",
                "options": {
                    "A": "Because distribution transformers operate 24 hours a day with fluctuating light loads, prioritizing high All-Day Energy Efficiency.",
                    "B": "Because copper losses are independent of load current variations.",
                    "C": "To keep core losses zero during peak daytime consumer demand.",
                    "D": "To prevent mechanical vibration of laminated core clamping bolts."
                },
                "correct_option": "A",
                "explanation": "Distribution transformers remain energized 24/7 (constant core loss) but carry variable, light average loads. Designing core loss lower than full-load copper loss maximizes all-day energy efficiency ($kWh_{out} / kWh_{in}$)."
            },
            {
                "question": "In a DC generator, what are the two distinct components of armature reaction under loaded conditions?",
                "options": {
                    "A": "Cross-magnetizing effect (distorting air-gap flux) and Demagnetizing effect (weakening main pole flux).",
                    "B": "Synchronizing torque and transient dampening torque.",
                    "C": "Skin effect and proximity eddy losses in commutator bars.",
                    "D": "Frictional windage loss and core hysteresis distortion."
                },
                "correct_option": "A",
                "explanation": "Current carrying armature conductors set up an MMF perpendicular to the main field MMF. The resulting armature reaction causes cross-magnetization (shifting magnetic neutral axis MNA) and demagnetization due to magnetic saturation."
            }
        ]

    # 3. EEE / ECE: Modern Control Theory & Control Systems
    elif has_any("control system", "control systems", "control theory", "controllability", 
                 "observability", "mcth", "csd", "cse", "state space", "root locus", 
                 "bode plot", "nyquist", "routh", "digital control", "dcs"):
        pool = [
            {
                "question": "According to Kalman's algebraic rank criterion, a continuous-time linear time-invariant system $\\dot{\\mathbf{x}} = \\mathbf{A}\\mathbf{x} + \\mathbf{B}\\mathbf{u}$ with $n$ state variables is completely state controllable if and only if:",
                "options": {
                    "A": "$\\text{Rank}([\\mathbf{B} \\quad \\mathbf{A}\\mathbf{B} \\quad \\mathbf{A}^2\\mathbf{B} \\quad \\dots \\quad \\mathbf{A}^{n-1}\\mathbf{B}]) = n$",
                    "B": "$\\det(\\mathbf{A}) \\neq 0$",
                    "C": "All eigenvalues of $\\mathbf{A}$ lie strictly in the left half of the complex s-plane.",
                    "D": "$\\text{Trace}(\\mathbf{A}) = \\text{Rank}(\\mathbf{B})$"
                },
                "correct_option": "A",
                "explanation": "The controllability matrix $\\mathbf{Q}_c = [\\mathbf{B} \\quad \\mathbf{A}\\mathbf{B} \\quad \\dots \\quad \\mathbf{A}^{n-1}\\mathbf{B}]$ must have full rank $n$ for any initial state to be steerable to any target state in finite time."
            },
            {
                "question": "What is the analytical formulation for the state transition matrix $\\mathbf{\\Phi}(t) = e^{\\mathbf{A}t}$ using Laplace transformation?",
                "options": {
                    "A": "$\\mathbf{\\Phi}(t) = \\mathcal{L}^{-1}\\{(s\\mathbf{I} - \\mathbf{A})^{-1}\\}$",
                    "B": "$\\mathbf{\\Phi}(t) = \\mathcal{L}\\{(s\\mathbf{I} + \\mathbf{A})\\}$",
                    "C": "$\\mathbf{\\Phi}(t) = (\\mathbf{I} - \\mathbf{A}t)^{-1}$",
                    "D": "$\\mathbf{\\Phi}(t) = \\det(s\\mathbf{I} - \\mathbf{A}) \\cdot \\mathbf{I}$"
                },
                "correct_option": "A",
                "explanation": "Taking the Laplace transform of $\\dot{\\mathbf{x}}(t) = \\mathbf{A}\\mathbf{x}(t)$ yields $s\\mathbf{X}(s) - \\mathbf{x}(0) = \\mathbf{A}\\mathbf{X}(s) \\implies \\mathbf{X}(s) = (s\\mathbf{I} - \\mathbf{A})^{-1}\\mathbf{x}(0)$, giving $\\mathbf{\\Phi}(t) = \\mathcal{L}^{-1}\\{(s\\mathbf{I} - \\mathbf{A})^{-1}\\}$."
            },
            {
                "question": "In Routh-Hurwitz stability analysis, what does the number of sign changes in the first column of the Routh array indicate?",
                "options": {
                    "A": "The exact number of characteristic roots (poles) lying in the right-half of the complex s-plane (unstable poles).",
                    "B": "The total number of closed-loop poles at the origin.",
                    "C": "The system damping ratio $\\zeta$.",
                    "D": "The number of complex conjugate zeros in the left-half s-plane."
                },
                "correct_option": "A",
                "explanation": "Routh's criterion states that the number of roots of the characteristic polynomial with positive real parts equals the number of sign changes in the coefficients of the first column of the Routh array."
            },
            {
                "question": "For a closed-loop system to be stable, what relationship must hold between Gain Margin (GM) and Phase Margin (PM) on a logarithmic Bode plot?",
                "options": {
                    "A": "Both Gain Margin ($> 0\\text{ dB}$) and Phase Margin ($> 0^\\circ$) must be strictly positive, and Phase Crossover Frequency $\\omega_{pc} >$ Gain Crossover Frequency $\\omega_{gc}$.",
                    "B": "Phase Margin must be negative while Gain Margin is infinite.",
                    "C": "Gain Margin must equal zero decibels at all frequencies.",
                    "D": "Phase Crossover Frequency must evaluate to zero."
                },
                "correct_option": "A",
                "explanation": "For minimum phase open-loop systems, positive gain margin and positive phase margin ensure the Nyquist plot does not encircle $(-1 + j0)$, guaranteeing closed-loop asymptotic stability."
            },
            {
                "question": "What is the steady-state error $e_{ss}$ of a Type 1 feedback control system subjected to a unit step input $r(t) = u(t)$?",
                "options": {
                    "A": "$e_{ss} = 0$",
                    "B": "$e_{ss} = \\frac{1}{1 + K_p}$",
                    "C": "$e_{ss} = \\infty$",
                    "D": "$e_{ss} = \\frac{1}{K_v}$"
                },
                "correct_option": "A",
                "explanation": "A Type 1 system has one open-loop pole at the origin ($s=0$), making position error constant $K_p = \\lim_{s\\to 0} G(s) = \\infty$; hence $e_{ss} = 1/(1 + K_p) = 0$."
            },
            {
                "question": "How are the departure angles ($\\theta_d$) of root locus branches departing from complex open-loop poles calculated?",
                "options": {
                    "A": "$\\theta_d = 180^\\circ - (\\sum \\text{angles of poles to the pole} - \\sum \\text{angles of zeros to the pole})$",
                    "B": "$\\theta_d = \\frac{360^\\circ}{n - m}$",
                    "C": "$\\theta_d = \\sum \\text{angles from all zeros}$",
                    "D": "$\\theta_d = 90^\\circ - \\text{Phase Crossover Angle}$"
                },
                "correct_option": "A",
                "explanation": "By the angle criterion of root locus, $\\angle G(s)H(s) = \\pm (2k+1)180^\\circ$, giving $\\theta_d = 180^\\circ - \\sum \\phi_p + \\sum \\phi_z$."
            },
            {
                "question": "According to Gilbert's diagonal canonical test, an LTI system with distinct eigenvalues $\\lambda_i$ is completely observable if and only if:",
                "options": {
                    "A": "The transformed output matrix $\\mathbf{\\tilde{C}}$ has NO column containing all zero entries.",
                    "B": "The state matrix $\\mathbf{A}$ has positive trace.",
                    "C": "The input matrix $\\mathbf{B}$ has zero rank.",
                    "D": "All eigenvalues are real and non-negative."
                },
                "correct_option": "A",
                "explanation": "In Jordan or diagonal form, if the $j$-th column of the output matrix $\\mathbf{\\tilde{C}}$ is zero, the $j$-th state variable does not couple into any output, making the system unobservable."
            }
        ]

    # 4. EEE: Power Electronics
    elif has_any("power electronic", "power electronics", "thyristor", "thyristors", "scr", 
                 "chopper", "choppers", "power inverter", "power inverters", "bridge inverter",
                 "cycloconverter", "cycloconverters", "controlled rectifier", "controlled rectifiers", 
                 "igbt", "triac", "pel", "pel1", "pel2", "smpc", "electric drives"):
        pool = [
            {
                "question": "What is the fundamental difference between the 'latching current' ($I_L$) and 'holding current' ($I_H$) of a Silicon Controlled Rectifier (SCR)?",
                "options": {
                    "A": "Latching current is the minimum anode current needed to maintain ON state during turn-on when gate pulse is removed; holding current is minimum anode current to prevent turn-off ($I_L > I_H$).",
                    "B": "Holding current is always greater than latching current ($I_H > I_L$).",
                    "C": "Latching current applies only during reverse breakdown conditions.",
                    "D": "Holding current is the peak gate trigger pulse current required for forward conduction."
                },
                "correct_option": "A",
                "explanation": "Latching current is associated with the turn-on process (gate signal removal), while holding current is associated with the turn-off process (anode current reduction). Typically $I_L \\approx 2 \\text{ to } 3 \\times I_H$."
            },
            {
                "question": "Why is an RC snubber circuit connected in parallel across a power semiconductor switch (such as an SCR or IGBT)?",
                "options": {
                    "A": "To protect the device against false $dv/dt$ triggering and destructive transient voltage spikes.",
                    "B": "To minimize high $di/dt$ during instantaneous device turn-on.",
                    "C": "To supply DC gate drive current during conduction.",
                    "D": "To eliminate the need for heat sink thermal dissipation."
                },
                "correct_option": "A",
                "explanation": "High rates of rise of anode voltage ($dv/dt$) charge the junction capacitance $C_{j2}$, creating a capacitive current $i = C_{j2}(dv/dt)$ that can falsely turn ON the SCR. The RC snubber bypasses high-frequency transients and clamps peak voltages."
            },
            {
                "question": "In an ideal DC-DC Step-Down (Buck) converter operating in Continuous Conduction Mode (CCM) with duty cycle $D = T_{on}/T$, what is the average output voltage $V_o$?",
                "options": {
                    "A": "$V_o = D \\cdot V_s$",
                    "B": "$V_o = \\frac{V_s}{1 - D}$",
                    "C": "$V_o = \\frac{D}{1 - D} V_s$",
                    "D": "$V_o = (1 - D) V_s$"
                },
                "correct_option": "A",
                "explanation": "By inductor volt-second balance across a switching period: $(V_s - V_o) D T + (-V_o)(1 - D) T = 0 \\implies V_o = D V_s$ (where $0 < D < 1$)."
            },
            {
                "question": "For a single-phase fully-controlled thyristor bridge rectifier supplying a highly inductive load (continuous load current) at firing angle $\\alpha$, what is the average output DC voltage $V_{dc}$?",
                "options": {
                    "A": "$V_{dc} = \\frac{2 V_m}{\\pi} \\cos\\alpha$",
                    "B": "$V_{dc} = \\frac{V_m}{\\pi} (1 + \\cos\\alpha)$",
                    "C": "$V_{dc} = \\frac{2 V_m}{\\pi} \\sin\\alpha$",
                    "D": "$V_{dc} = \\frac{V_m}{2\\pi} \\cos^2\\alpha$"
                },
                "correct_option": "A",
                "explanation": "Integrating the AC supply voltage from $\\alpha$ to $\\pi + \\alpha$: $V_{dc} = \\frac{1}{\\pi} \\int_\\alpha^{\\pi+\\alpha} V_m \\sin(\\omega t) d(\\omega t) = \\frac{2 V_m}{\\pi} \\cos\\alpha$."
            },
            {
                "question": "In Sinusoidal Pulse Width Modulation (SPWM) for voltage source inverters, what does the amplitude modulation index $m_a$ represent?",
                "options": {
                    "A": "$m_a = \\frac{V_{control}}{V_{tri}}$, where $V_{control}$ is reference sine amplitude and $V_{tri}$ is carrier triangle amplitude.",
                    "B": "$m_a = \\frac{f_{carrier}}{f_{reference}}$",
                    "C": "$m_a = \\frac{V_{dc}}{V_{rms}}$",
                    "D": "$m_a = 2\\pi f_{fundamental} \\cdot L$"
                },
                "correct_option": "A",
                "explanation": "The modulation index $m_a = \\hat{V}_{control} / \\hat{V}_{tri}$ controls the fundamental AC output voltage amplitude; for $m_a \\le 1$ (linear range), the fundamental output amplitude is directly proportional to $m_a$."
            },
            {
                "question": "What is the primary operational distinction between a Voltage Source Inverter (VSI) and a Current Source Inverter (CSI)?",
                "options": {
                    "A": "VSI is fed from a stiff DC voltage source with a large parallel capacitor, whereas CSI is fed from a stiff DC current source with a large series inductor.",
                    "B": "CSI produces purely sinusoidal output voltage without filtering.",
                    "C": "VSI cannot be operated using PWM control strategies.",
                    "D": "CSI switches only conduct in reverse breakdown mode."
                },
                "correct_option": "A",
                "explanation": "A VSI has low internal source impedance (clamped by a DC link capacitor) producing regulated AC output voltage waveforms, while a CSI has high internal impedance (series reactor) producing regulated AC output current waveforms."
            }
        ]

    # 5. EEE / ECE: Measurements & Instrumentation
    elif has_any("measurement", "measurements", "instrumentation", "pmmc", "wattmeter", 
                 "transducer", "transducers", "dvm", "measuring instrument", "measuring instruments", 
                 "emi", "eemi", "bridges"):
        pool = [
            {
                "question": "What fundamental type of electrical quantity is measured by a Permanent Magnet Moving Coil (PMMC) instrument?",
                "options": {
                    "A": "True Average value of DC signals only (reads zero on symmetrical sinusoidal AC).",
                    "B": "True RMS value of AC and DC signals equally.",
                    "C": "Peak-to-peak voltage of high-frequency pulses.",
                    "D": "Reactive volt-amperes of inductive loads."
                },
                "correct_option": "A",
                "explanation": "Because the magnetic field is unidirectional from permanent magnets, deflecting torque reverses direction every half-cycle on AC, averaging to zero deflection due to pointer inertia; thus PMMC measures pure DC average."
            },
            {
                "question": "Why does a Moving Iron (MI) instrument exhibit a non-linear (cramped near zero) scale calibration?",
                "options": {
                    "A": "Deflecting torque is directly proportional to the square of the operating current ($T_d \\propto I^2$).",
                    "B": "Control torque provided by hair springs varies exponentially with temperature.",
                    "C": "Eddy current damping opposes deflection quadratically.",
                    "D": "Air-gap magnetic flux decreases linearly with pointer angle."
                },
                "correct_option": "A",
                "explanation": "In moving iron meters, deflecting torque $T_d = \\frac{1}{2} I^2 \\frac{dL}{d\\theta}$; since $T_d \\propto I^2$, the scale follows a square-law spacing (cramped at beginning, spread out at higher values)."
            },
            {
                "question": "In the two-wattmeter method for measuring 3-phase power, what is the power factor angle $\\phi$ of a balanced load with readings $W_1$ and $W_2$?",
                "options": {
                    "A": "$\\tan\\phi = \\sqrt{3} \\left( \\frac{W_1 - W_2}{W_1 + W_2} \\right)$",
                    "B": "$\\cos\\phi = \\frac{W_1 - W_2}{W_1 + W_2}$",
                    "C": "$\\tan\\phi = \\frac{W_1 + W_2}{\\sqrt{3}(W_1 - W_2)}$",
                    "D": "$\\sin\\phi = \\frac{W_1}{W_2}$"
                },
                "correct_option": "A",
                "explanation": "Individual wattmeter readings are $W_1 = V_L I_L \\cos(30^\\circ - \\phi)$ and $W_2 = V_L I_L \\cos(30^\\circ + \\phi)$, leading directly to $W_1 + W_2 = \\sqrt{3} V_L I_L \\cos\\phi$ and $\\tan\\phi = \\sqrt{3}(W_1 - W_2)/(W_1 + W_2)$."
            },
            {
                "question": "How is the measurement range of an electrical DC voltmeter extended?",
                "options": {
                    "A": "Connecting a high non-inductive multiplier resistance in series with the meter movement.",
                    "B": "Connecting a low resistance shunt in parallel with the meter coil.",
                    "C": "Adding a current transformer in series with the input leads.",
                    "D": "Decreasing the number of turns on the deflecting coil."
                },
                "correct_option": "A",
                "explanation": "To measure higher voltages without exceeding the galvanometer's full-scale current rating ($I_m$), a high series multiplier resistance $R_s = R_m(m - 1)$ is added in series to drop the excess voltage."
            },
            {
                "question": "Which AC bridge circuit is specifically suitable for measuring an unknown medium inductance in terms of a standard capacitance?",
                "options": {
                    "A": "Maxwell's Inductance-Capacitance Bridge",
                    "B": "Schering Bridge",
                    "C": "Wien Bridge",
                    "D": "Wheatstone Bridge"
                },
                "correct_option": "A",
                "explanation": "Maxwell's Inductance-Capacitance bridge balances an unknown medium-Q inductor against a standard variable capacitor and resistors, yielding balance equations independent of source frequency."
            },
            {
                "question": "What is the operating principle of a Linear Variable Differential Transformer (LVDT)?",
                "options": {
                    "A": "Mutual inductance changes between a primary coil and two balanced secondary coils as an iron core is linearly displaced.",
                    "B": "Piezoelectric charge generated by mechanical crystal stress.",
                    "C": "Change in electrical resistance caused by strain deformation.",
                    "D": "Thermoelectric Seebeck effect across thermocouple junctions."
                },
                "correct_option": "A",
                "explanation": "An LVDT consists of one primary coil and two identical secondaries connected in series-opposition; core displacement increases coupling in one secondary and reduces it in the other, producing differential AC voltage proportional to position."
            }
        ]

    # 6. EEE / ECE: Electromagnetic Field Theory / EMF
    elif has_any("electromagnetic field", "electromagnetic fields", "emf", "electrostatic", 
                 "electrostatics", "magnetostatic", "magnetostatics", "maxwell", "poynting", "coulomb"):
        pool = [
            {
                "question": "Which of Maxwell's four equations represents Gauss's Law for magnetic fields, confirming the non-existence of isolated magnetic monopoles?",
                "options": {
                    "A": "$\\nabla \\cdot \\mathbf{B} = 0$",
                    "B": "$\\nabla \\cdot \\mathbf{D} = \\rho_v$",
                    "C": "$\\nabla \\times \\mathbf{E} = -\\frac{\\partial \\mathbf{B}}{\\partial t}$",
                    "D": "$\\nabla \\times \\mathbf{H} = \\mathbf{J} + \\frac{\\partial \\mathbf{D}}{\\partial t}$"
                },
                "correct_option": "A",
                "explanation": "$\\nabla \\cdot \\mathbf{B} = 0$ states that net magnetic flux through any closed Gaussian surface is zero, proving magnetic flux lines are continuous closed loops and free magnetic charges do not exist."
            },
            {
                "question": "What does the Poynting Vector $\\mathbf{S} = \\mathbf{E} \\times \\mathbf{H}$ physically represent in electromagnetic wave propagation?",
                "options": {
                    "A": "The instantaneous directional power density (rate of energy flow per unit area) carried by the EM wave in $\\text{W/m}^2$.",
                    "B": "The electrostatic potential gradient around an isolated point charge.",
                    "C": "The mechanical momentum stored within magnetic core laminations.",
                    "D": "The velocity of light in vacuum."
                },
                "correct_option": "A",
                "explanation": "By Poynting's theorem, $\\mathbf{S} = \\mathbf{E} \\times \\mathbf{H}$ points in the direction of electromagnetic energy propagation, with units of watts per square meter ($\\text{W/m}^2$)."
            },
            {
                "question": "What is Maxwell's crucial modification to Ampere's Circuital Law for time-varying electromagnetic fields?",
                "options": {
                    "A": "Addition of the Displacement Current density term $\\mathbf{J}_D = \\frac{\\partial \\mathbf{D}}{\\partial t}$.",
                    "B": "Substitution of magnetic vector potential $\\mathbf{A}$ for magnetic flux density $\\mathbf{B}$.",
                    "C": "Elimination of conduction current density $\\mathbf{J}$ in dielectrics.",
                    "D": "Setting divergence of electric field to zero in all conducting media."
                },
                "correct_option": "A",
                "explanation": "Maxwell added displacement current density $\\partial \\mathbf{D}/\\partial t$ to ensure continuity of current ($\\nabla \\cdot (\\nabla \\times \\mathbf{H}) = 0 = \\nabla \\cdot \\mathbf{J} + \\frac{\\partial \\rho_v}{\\partial t}$), resolving the capacitor charging paradox."
            },
            {
                "question": "What is the formula for the skin depth $\\delta$ of an electromagnetic plane wave penetrating a good conductor ($\\\\sigma \\\\gg \\\\omega\\\\epsilon$)?",
                "options": {
                    "A": "$\\delta = \\sqrt{\\frac{2}{\\omega \\mu \\sigma}}$",
                    "B": "$\\delta = \\frac{\\omega}{\\sqrt{\\mu \\sigma}}$",
                    "C": "$\\delta = \\frac{1}{2\\pi \\sqrt{\\mu \\epsilon}}$",
                    "D": "$\\delta = \\sqrt{\\frac{\\sigma}{\\omega \\mu}}$"
                },
                "correct_option": "A",
                "explanation": "Skin depth $\\delta$ is the distance over which field amplitude decays to $1/e$ (approx $36.8\\%$) of its surface value: $\\delta = 1/\\alpha = \\sqrt{2/(\\omega \\mu \\sigma)}$."
            },
            {
                "question": "At the planar boundary between two perfect dielectric media with no free surface charge ($\\rho_s = 0$), which boundary condition must hold?",
                "options": {
                    "A": "Normal components of electric flux density are continuous ($D_{n1} = D_{n2}$) and tangential electric fields are continuous ($E_{t1} = E_{t2}$).",
                    "B": "Tangential magnetic fields drop to zero at the interface.",
                    "C": "Normal electric field components are strictly equal ($E_{n1} = E_{n2}$).",
                    "D": "Surface charge density increases proportionally to relative permittivity."
                },
                "correct_option": "A",
                "explanation": "From $\\oint \\mathbf{E} \\cdot d\\mathbf{l} = 0$, tangential electric field is continuous across any interface ($E_{t1} = E_{t2}$). From $\\oint \\mathbf{D} \\cdot d\\mathbf{S} = Q_{enc}$, normal displacement is continuous when $\\rho_s = 0$ ($D_{n1} = D_{n2}$)."
            }
        ]

    # 7. EEE: Electric Vehicles & Battery Technology
    elif has_any("electric vehicle", "electric vehicles", "ev technology", "battery management", "bms", "bldc", "ev", "evt", "ehv"):
        pool = [
            {
                "question": "What method is most commonly utilized in an Electric Vehicle Battery Management System (BMS) for real-time State-of-Charge (SOC) tracking?",
                "options": {
                    "A": "Coulomb Counting (Current Integration) combined with Extended Kalman Filtering (EKF).",
                    "B": "Direct terminal voltage measurement without thermal correction.",
                    "C": "Measuring electrolyte specific gravity during high-speed driving.",
                    "D": "Complete battery full-discharge cycle calibration every journey."
                },
                "correct_option": "A",
                "explanation": "Coulomb counting integrates instantaneous current over time ($SOC = SOC_0 - \\frac{1}{C_n}\\int i\\,dt$). To prevent integration drift, modern EV BMS units pair it with Kalman Filtering to fuse cell model voltage predictions."
            },
            {
                "question": "Why are Brushless DC (BLDC) and Permanent Magnet Synchronous Motors (PMSM) widely favored over brushed DC motors for modern EV drivetrains?",
                "options": {
                    "A": "Higher efficiency, superior power-to-weight density, negligible maintenance due to absence of mechanical brushes/commutators, and excellent thermal dissipation.",
                    "B": "They can be operated directly from a DC battery without electronic inverters.",
                    "C": "Their speed cannot exceed 1000 RPM, providing natural speed limiting.",
                    "D": "They use cheap ferrite magnets that require zero sensor control."
                },
                "correct_option": "A",
                "explanation": "BLDC and PMSM motors eliminate mechanical commutators and brushes, achieving up to $95\\%$ efficiency, higher torque density, and cooling from stator coils on the exterior casing."
            },
            {
                "question": "During EV regenerative braking, what operational transition occurs in the drivetrain electrical system?",
                "options": {
                    "A": "The traction motor operates as an electrical generator, converting vehicle kinetic energy back into electrical energy to recharge the battery pack.",
                    "B": "Dynamic resistors dissipate vehicle inertia purely as thermal heat into the chassis.",
                    "C": "Battery cells are connected in reverse polarity to mechanically lock the wheels.",
                    "D": "The DC-DC converter turns off to isolate high voltage storage."
                },
                "correct_option": "A",
                "explanation": "During deceleration, inverter switching timing makes the motor generate back-EMF greater than terminal DC link voltage, flowing negative current back into the high-voltage battery pack."
            },
            {
                "question": "What does a battery charging C-rate of $2\\text{C}$ signify for a $60\\text{ kWh}$ EV battery pack?",
                "options": {
                    "A": "The battery pack can be theoretically fully charged from empty in 30 minutes ($0.5\\text{ hour}$) at $120\\text{ kW}$ power.",
                    "B": "The battery takes 2 full hours to complete charging.",
                    "C": "The charging voltage must be doubled to 2000 Volts.",
                    "D": "The battery delivers twice its rated cycle lifespan."
                },
                "correct_option": "A",
                "explanation": "C-rate measures charge/discharge current relative to capacity: $1\\text{C}$ discharges fully in 1 hour; $2\\text{C}$ discharges/charges in $1/2\\text{ hour} = 30\\text{ minutes}$."
            }
        ]

    # 8. Civil Engineering: Surveying
    elif has_any("surveying", "compass surveying", "chain surveying", "levelling", 
                 "theodolite", "tachometry", "triangulation", "prismatic compass"):
        pool = [
            {
                "question": "In compass surveying, if the Whole Circle Bearing (WCB) of a line is $245^\\circ 30'$, what is its equivalent Quadrantal (Reduced) Bearing?",
                "options": {
                    "A": "$\\text{S } 65^\\circ 30' \\text{ W}$",
                    "B": "$\\text{N } 65^\\circ 30' \\text{ W}$",
                    "C": "$\\text{S } 24^\\circ 30' \\text{ W}$",
                    "D": "$\\text{W } 65^\\circ 30' \\text{ S}$"
                },
                "correct_option": "A",
                "explanation": "A bearing of $245^\\circ 30'$ lies in the third quadrant (South-West). Reduced Bearing $= \\text{WCB} - 180^\\circ = 245^\\circ 30' - 180^\\circ = \\text{S } 65^\\circ 30' \\text{ W}$."
            },
            {
                "question": "What causes 'Local Attraction' during magnetic compass surveying observations in the field?",
                "options": {
                    "A": "Presence of magnetic substances such as iron ore, steel structures, electric transmission cables, or metallic objects near the instrument.",
                    "B": "Variations in atmospheric temperature between morning and afternoon.",
                    "C": "Earth curvature over long surveying sight distances.",
                    "D": "Frictional resistance of the agate bearing pivot."
                },
                "correct_option": "A",
                "explanation": "Local attraction deflects the magnetic needle away from the true magnetic meridian due to external magnetic fields from underground iron pipes, steel bridges, electric power lines, or keys/pens."
            },
            {
                "question": "In spirit leveling, what is the 'Height of Instrument' (HI) formula using a known Benchmark (BM) Reduced Level and Back Sight (BS)?",
                "options": {
                    "A": "$\\text{HI} = \\text{RL of BM} + \\text{BS}$",
                    "B": "$\\text{HI} = \\text{RL of BM} - \\text{BS}$",
                    "C": "$\\text{HI} = \\text{BS} - \\text{FS}$",
                    "D": "$\\text{HI} = \\text{RL of BM} + \\text{FS}$"
                },
                "correct_option": "A",
                "explanation": "The line of collimation height is determined by adding the staff reading at the known benchmark (Back Sight) to the elevation of the benchmark: $\\text{HI} = \\text{RL} + \\text{BS}$. The RL of subsequent points is $\\text{RL} = \\text{HI} - \\text{FS}$."
            },
            {
                "question": "What is the defining operational distinction between a Prismatic Compass and a Surveyor's Compass?",
                "options": {
                    "A": "A Prismatic compass has a graduated ring attached to the needle reading $0^\\circ$ to $360^\\circ$ (with $0^\\circ$ at South), allowing sighting and reading simultaneously through a prism.",
                    "B": "A Surveyor's compass uses whole circle bearings while a Prismatic compass uses quadrantal bearings.",
                    "C": "A Prismatic compass does not utilize a magnetic needle.",
                    "D": "A Surveyor's compass requires zero tripod support."
                },
                "correct_option": "A",
                "explanation": "In a Prismatic compass, the graduated aluminum ring rotates with the needle and readings run clockwise from South ($0^\\circ$) to West ($90^\\circ$), North ($180^\\circ$), East ($270^\\circ$); sighting and reading occur at the same instant through the prism."
            },
            {
                "question": "What is the combined correction for Earth's curvature ($C_c$) and atmospheric refraction ($C_r$) for a distance $d$ in kilometers in leveling?",
                "options": {
                    "A": "$C_{comb} = -0.0673 \\, d^2 \\text{ meters}$",
                    "B": "$C_{comb} = +0.0785 \\, d^2 \\text{ meters}$",
                    "C": "$C_{comb} = -0.0112 \\, d^2 \\text{ meters}$",
                    "D": "$C_{comb} = -0.573 \\, d \\text{ meters}$"
                },
                "correct_option": "A",
                "explanation": "Curvature makes staff readings too high ($C_c = -0.0785 d^2$) and refraction bends light downward ($C_r = +0.0112 d^2$). The net combined correction is subtractive: $C = -0.0673 d^2$ meters."
            }
        ]

    # 9. Civil Engineering: Strength of Materials (SOM) & Mechanics
    elif has_any("strength of materials", "simple stresses", "bending moment", 
                 "shear force", "torsion", "mohr", "deflection of beams", "som"):
        pool = [
            {
                "question": "What is the fundamental mathematical relationship between Young's Modulus ($E$), Modulus of Rigidity ($G$), and Poisson's Ratio ($\\mu$)?",
                "options": {
                    "A": "$E = 2G(1 + \\mu)$",
                    "B": "$E = 3G(1 - 2\\mu)$",
                    "C": "$G = 2E(1 + \\mu)$",
                    "D": "$E = G(1 - \\mu)$"
                },
                "correct_option": "A",
                "explanation": "Elastic constant theory relates tensile stress, shear stress, and volumetric strain through $E = 2G(1 + \\mu) = 3K(1 - 2\\mu) = \\frac{9KG}{3K + G}$."
            },
            {
                "question": "In beam bending theory, what is the pure bending equation (flexure formula) relating bending moment $M$, moment of inertia $I$, bending stress $\\sigma$, and radius of curvature $R$?",
                "options": {
                    "A": "$\\frac{M}{I} = \\frac{\\sigma}{y} = \\frac{E}{R}$",
                    "B": "$\\frac{M}{y} = \\frac{\\sigma}{I} = \\frac{R}{E}$",
                    "C": "$\\frac{M}{E} = \\frac{I}{\\sigma} = \\frac{y}{R}$",
                    "D": "$\\frac{M}{R} = \\frac{\\sigma}{E} = \\frac{y}{I}$"
                },
                "correct_option": "A",
                "explanation": "The Euler-Bernoulli flexural formula states that $\\frac{M}{I} = \\frac{\\sigma}{y} = \\frac{E}{R}$, where $y$ is distance from neutral axis."
            },
            {
                "question": "In a structural beam loaded transversally, what occurs at a 'Point of Contraflexure' (inflection point)?",
                "options": {
                    "A": "The bending moment changes sign (passes through zero), and curvature changes from sagging to hogging.",
                    "B": "The shear force reaches its absolute maximum value.",
                    "C": "The deflection of the beam is strictly infinite.",
                    "D": "The cross-section experiences maximum torsional warping."
                },
                "correct_option": "A",
                "explanation": "A point of contraflexure is a section along a flexural member where the bending moment equals zero ($M = 0$) and switches sign between hogging (negative) and sagging (positive)."
            },
            {
                "question": "What is the torsion formula for a circular shaft of polar moment of inertia $J$ subjected to torque $T$?",
                "options": {
                    "A": "$\\frac{T}{J} = \\frac{\\tau}{r} = \\frac{G\\theta}{L}$",
                    "B": "$\\frac{T}{r} = \\frac{\\tau}{J} = \\frac{L}{G\\theta}$",
                    "C": "$\\frac{T}{G} = \\frac{\\tau}{\\theta} = \\frac{J}{r L}$",
                    "D": "$\\frac{T}{L} = \\frac{\\tau}{G} = \\frac{J\\theta}{r}$"
                },
                "correct_option": "A",
                "explanation": "Torsion theory for circular cross-sections establishes that shear stress varies linearly with radius $r$: $\\frac{T}{J} = \\frac{\\tau}{r} = \\frac{G\\theta}{L}$, where $J = \\frac{\\pi D^4}{32}$."
            },
            {
                "question": "In Mohr's Circle for plane stress analysis, what does the radius of the circle physically represent?",
                "options": {
                    "A": "The maximum in-plane shear stress ($\\tau_{max} = \\frac{\\sigma_1 - \\sigma_2}{2}$).",
                    "B": "The average normal hydrostatic stress.",
                    "C": "The principal compressive strain.",
                    "D": "The angle of obliquity on the octahedral plane."
                },
                "correct_option": "A",
                "explanation": "Mohr's circle center is at $((\\sigma_x + \\sigma_y)/2, 0)$ and its radius is $R = \\sqrt{((\\sigma_x - \\sigma_y)/2)^2 + \\tau_{xy}^2}$, which is precisely the maximum in-plane shear stress $\\tau_{max}$."
            }
        ]

    # 10. Mechanical Engineering: Thermodynamics
    elif has_any("thermodynamic", "thermodynamics", "first law of thermodynamics", 
                 "second law of thermodynamics", "carnot", "entropy", "otto cycle", "diesel cycle", "rankine"):
        pool = [
            {
                "question": "What is the mathematical formulation of the First Law of Thermodynamics for a closed system undergoing a non-flow process?",
                "options": {
                    "A": "$\\delta Q = dU + \\delta W$ (Heat added equals increase in internal energy plus work done)",
                    "B": "$\\delta Q = dH - V dP$",
                    "C": "$dU = T dS + P dV$",
                    "D": "$\\delta W = -dU - dS$"
                },
                "correct_option": "A",
                "explanation": "Energy conservation for a closed stationary system states that net heat transfer $\\delta Q$ into the system equals the change in internal energy $dU$ plus boundary work $\\delta W = P dV$."
            },
            {
                "question": "What is the theoretical thermal efficiency $\\eta_{th}$ of a Carnot heat engine operating between absolute temperatures $T_H$ and $T_L$?",
                "options": {
                    "A": "$\\eta = 1 - \\frac{T_L}{T_H}$",
                    "B": "$\\eta = 1 - \\frac{T_H}{T_L}$",
                    "C": "$\\eta = \\frac{T_H - T_L}{T_L}$",
                    "D": "$\\eta = \\frac{T_L}{T_H}$"
                },
                "correct_option": "A",
                "explanation": "The Carnot cycle represents the maximum theoretical upper bound on efficiency for any engine operating between high temperature reservoir $T_H$ and sink $T_L$: $\\eta = 1 - T_L/T_H$."
            },
            {
                "question": "According to the Clausius Inequality, what is the integral $\\oint \\frac{\\delta Q}{T}$ for any real (irreversible) thermodynamic cycle?",
                "options": {
                    "A": "$\\oint \\frac{\\delta Q}{T} < 0$",
                    "B": "$\\oint \\frac{\\delta Q}{T} = 0$",
                    "C": "$\\oint \\frac{\\delta Q}{T} > 0$",
                    "D": "$\\oint \\frac{\\delta Q}{T} = \\infty$"
                },
                "correct_option": "A",
                "explanation": "Clausius inequality states $\\oint \\frac{\\delta Q}{T} \\le 0$, where equality holds strictly for reversible cycles and strict inequality ($< 0$) holds for all irreversible cycles."
            },
            {
                "question": "How does the air-standard thermal efficiency of an ideal Otto cycle vary with the compression ratio $r = V_1/V_2$?",
                "options": {
                    "A": "Increases as compression ratio $r$ increases according to $\\eta = 1 - \\frac{1}{r^{\\gamma - 1}}$.",
                    "B": "Decreases linearly with increasing compression ratio.",
                    "C": "Remains constant regardless of compression ratio.",
                    "D": "Depends only on maximum combustion temperature."
                },
                "correct_option": "A",
                "explanation": "Otto cycle efficiency $\\eta = 1 - 1/(r^{\\gamma-1})$ is a monotonically increasing function of compression ratio $r$ and specific heat ratio $\\gamma = C_p/C_v$."
            },
            {
                "question": "What property of a pure substance remains constant during an ideal throttling process through a porous plug or partially open valve?",
                "options": {
                    "A": "Specific Enthalpy ($h_1 = h_2$)",
                    "B": "Specific Entropy ($s_1 = s_2$)",
                    "C": "Internal Energy ($u_1 = u_2$)",
                    "D": "Temperature ($T_1 = T_2$)"
                },
                "correct_option": "A",
                "explanation": "Throttling is an adiabatic, unresisted expansion with no shaft work; from steady flow energy equation $h_1 + q = h_2 + w$, since $q = 0$ and $w = 0$, $h_1 = h_2$ (isenthalpic process)."
            }
        ]

    # 11. ECE: VLSI Design & Digital Electronics
    elif has_any("vlsi", "vlsi design", "mos transistor", "cmos fabrication", "stick diagram", "fpga"):
        pool = [
            {
                "question": "Why does a static CMOS inverter consume negligible static power when the output is stable at either logic '0' or logic '1'?",
                "options": {
                    "A": "Because one of the two complementary transistors (either pull-up pMOS or pull-down nMOS) is completely OFF, breaking the direct path from $V_{DD}$ to Ground.",
                    "B": "Because gate oxide resistance drops to zero in steady-state.",
                    "C": "Because substrate diode junctions conduct reverse saturation current only.",
                    "D": "Because parasitic wire inductance opposes DC current flow."
                },
                "correct_option": "A",
                "explanation": "In static CMOS, for input High ($V_{DD}$), nMOS is ON and pMOS is OFF; for input Low (GND), pMOS is ON and nMOS is OFF. Except for tiny subthreshold leakage currents, no direct DC path exists between $V_{DD}$ and GND."
            },
            {
                "question": "Why are pMOS transistors designed with wider channel widths ($W_p \\approx 2 \\text{ to } 2.5 \\times W_n$) than nMOS transistors in CMOS logic gates?",
                "options": {
                    "A": "To compensate for lower hole mobility ($\\mu_p \\approx 0.4 \\mu_n$) so that rise time and fall time are symmetric.",
                    "B": "To increase threshold voltage $V_{tp}$ above supply voltage.",
                    "C": "To eliminate gate-to-drain overlap Miller capacitance.",
                    "D": "To allow higher substrate body-effect biasing."
                },
                "correct_option": "A",
                "explanation": "Electrons in silicon have approximately $2.5\\times$ higher mobility than holes ($\\mu_n \\approx 500\\text{ cm}^2/\\text{V}\\cdot\\text{s}$ vs $\\mu_p \\approx 200\\text{ cm}^2/\\text{V}\\cdot\\text{s}$). Making $W_p \\approx 2.5 W_n$ balances current driving capability."
            },
            {
                "question": "In synchronous sequential circuits, what does a 'Setup Time' ($t_{setup}$) violation cause?",
                "options": {
                    "A": "Data input fails to remain stable before the active clock edge, causing the flip-flop to enter an unpredictable metastable state.",
                    "B": "Clock frequency increases beyond the power supply voltage.",
                    "C": "Excessive electromigration burns the interconnect metal.",
                    "D": "Combinational logic delays become negative."
                },
                "correct_option": "A",
                "explanation": "Setup time is the minimum duration the data input must be stable prior to the arrival of the clock edge. Violating this condition leads to metastability, where the flip-flop output hovers between logic levels."
            },
            {
                "question": "What is the formula for dynamic power dissipation ($P_{dyn}$) in a CMOS logic gate operating at clock frequency $f$ with load capacitance $C_L$?",
                "options": {
                    "A": "$P_{dyn} = \\alpha \\cdot C_L \\cdot V_{DD}^2 \\cdot f$",
                    "B": "$P_{dyn} = C_L \\cdot V_{DD} \\cdot f$",
                    "C": "$P_{dyn} = \\alpha \\cdot I_{leak} \\cdot V_{DD}$",
                    "D": "$P_{dyn} = \\frac{V_{DD}^2}{R_{on}}$"
                },
                "correct_option": "A",
                "explanation": "Every switching transition charges and discharges load capacitance $C_L$. With activity factor $\\alpha$, the dynamic power is $P_{dyn} = \\alpha C_L V_{DD}^2 f$."
            },
            {
                "question": "In VLSI Stick Diagrams based on Mead-Conway Lambda ($\\lambda$) rules, which color standardly designates the Polysilicon layer?",
                "options": {
                    "A": "Red",
                    "B": "Green",
                    "C": "Blue",
                    "D": "Yellow"
                },
                "correct_option": "A",
                "explanation": "Standard VLSI layout colors: Red = Polysilicon, Green = n-diffusion, Yellow/Brown = p-diffusion, Blue = Metal 1."
            }
        ]

    # 12. CSE / CSM: Machine Learning & AI
    elif has_any("machine learning", "deep learning", "bias-variance", "fml", 
                 "neural network", "neural networks", "supervised learning", "unsupervised learning", "ai"):
        pool = [
            {
                "question": "In machine learning statistical modeling, what is the primary consequence of a model having 'High Variance'?",
                "options": {
                    "A": "The model fits training noise too closely (Overfitting), leading to poor generalization performance on unseen test data.",
                    "B": "The model makes strong erroneous assumptions about data relationships (Underfitting).",
                    "C": "The model parameters shrink strictly to zero.",
                    "D": "The training loss remains completely constant."
                },
                "correct_option": "A",
                "explanation": "High variance means the model is overly complex and sensitive to small fluctuations in the training set (overfitting), capturing noise rather than underlying patterns."
            },
            {
                "question": "What is the key geometric and mathematical difference between $L_1$ Regularization (Lasso) and $L_2$ Regularization (Ridge)?",
                "options": {
                    "A": "$L_1$ penalty ($\\lambda \\sum |w_i|$) induces exact feature sparsity by driving irrelevant coefficients to zero, whereas $L_2$ penalty ($\\lambda \\sum w_i^2$) shrinks weights smoothly toward zero.",
                    "B": "$L_2$ regularization sets coefficients strictly to zero while $L_1$ does not.",
                    "C": "$L_1$ regularization can only be applied to unsupervised clustering.",
                    "D": "$L_2$ regularization eliminates the need for gradient descent."
                },
                "correct_option": "A",
                "explanation": "The diamond-shaped contour constraint of the $L_1$ norm hits coordinate axes where $w_i = 0$, performing automatic feature selection, whereas the spherical $L_2$ constraint shrinks weights without setting them to exact zero."
            },
            {
                "question": "In binary classification performance evaluation, what is the formula for 'Recall' (Sensitivity)?",
                "options": {
                    "A": "$\\text{Recall} = \\frac{\\text{True Positives (TP)}}{\\text{True Positives (TP)} + \\text{False Negatives (FN)}}$",
                    "B": "$\\text{Recall} = \\frac{\\text{True Positives (TP)}}{\\text{True Positives (TP)} + \\text{False Positives (FP)}}$",
                    "C": "$\\text{Recall} = \\frac{\\text{True Negatives (TN)}}{\\text{Total Population}}$",
                    "D": "$\\text{Recall} = \\frac{\\text{Precision} \\times 2}{\\text{F1-score}}$"
                },
                "correct_option": "A",
                "explanation": "Recall measures the model's ability to identify all actual positive cases: $\\text{Recall} = \\text{TP} / (\\text{TP} + \\text{FN})$."
            },
            {
                "question": "Why does the Rectified Linear Unit (ReLU) activation function ($f(x) = \\max(0, x)$) mitigate the vanishing gradient problem compared to the Sigmoid function in deep neural networks?",
                "options": {
                    "A": "Its derivative is constant ($f'(x) = 1$) for all positive inputs ($x > 0$), preventing gradients from exponentially attenuating during backpropagation.",
                    "B": "It squashes activations into the narrow range $[0, 1]$.",
                    "C": "It is non-differentiable at all negative values.",
                    "D": "It eliminates the need for bias parameters."
                },
                "correct_option": "A",
                "explanation": "Sigmoid derivative peaks at $0.25$ and approaches zero for large $|x|$, causing gradients to vanish exponentially through layers; ReLU has a derivative of $1$ for $x > 0$, sustaining strong backpropagated error gradients."
            },
            {
                "question": "What is the primary optimization objective of the Support Vector Machine (SVM) algorithm for linearly separable classes?",
                "options": {
                    "A": "Find the decision hyperplane that maximizes the geometric separation margin between the closest support vectors of each class.",
                    "B": "Minimize the sum of squared distances within each cluster.",
                    "C": "Maximize the entropy of posterior class probabilities.",
                    "D": "Project data onto orthogonal axes of maximum variance."
                },
                "correct_option": "A",
                "explanation": "SVM finds an optimal hyperplane $\\mathbf{w}^T\\mathbf{x} + b = 0$ that maximizes the geometric margin $2/\\|\\mathbf{w}\\|$, which provides maximum robustness against noise."
            }
        ]

    # 13. CSE / CSM: Java / Object Oriented Programming
    elif has_any("oopj", "java", "object oriented programming", "oops"):
        pool = [
            {
                "question": "Which of the following statements accurately describes the difference between a class and an object in Java?",
                "options": {
                    "A": "A class is a blueprint or template, whereas an object is an instance of a class allocated in heap memory.",
                    "B": "An object is a blueprint or template, whereas a class is allocated at runtime in stack memory.",
                    "C": "Classes and objects both occupy identical memory in the JVM stack area.",
                    "D": "A class can only be instantiated once per JVM execution lifecycle."
                },
                "correct_option": "A",
                "explanation": "A class serves as a syntactic template that defines fields and methods, while an object is a concrete runtime instance allocated in the JVM heap using the 'new' keyword."
            },
            {
                "question": "Which access modifier in Java grants visibility to subclasses in different packages, while restricting access from unrelated classes in those external packages?",
                "options": {
                    "A": "protected",
                    "B": "private",
                    "C": "default (package-private)",
                    "D": "public"
                },
                "correct_option": "A",
                "explanation": "The 'protected' modifier allows access within the declaring package and also by derived subclasses located in foreign packages via inheritance."
            },
            {
                "question": "In Java, what mechanism allows a subclass to provide a specific implementation of a method already defined in its superclass?",
                "options": {
                    "A": "Method Overriding",
                    "B": "Method Overloading",
                    "C": "Static Binding",
                    "D": "Encapsulation"
                },
                "correct_option": "A",
                "explanation": "Method overriding allows a subclass to define a specific implementation of a superclass method with the same signature, resolved dynamically at runtime (dynamic method dispatch)."
            },
            {
                "question": "Which keyword is used in a subclass constructor to explicitly invoke the constructor of its immediate superclass?",
                "options": {
                    "A": "super()",
                    "B": "this()",
                    "C": "parent()",
                    "D": "base()"
                },
                "correct_option": "A",
                "explanation": "The 'super()' call invokes the immediate parent class constructor and must be the very first statement inside the subclass constructor body."
            },
            {
                "question": "Which block in Java exception handling is guaranteed to execute whether an exception is caught or not?",
                "options": {
                    "A": "finally",
                    "B": "try",
                    "C": "catch",
                    "D": "throws"
                },
                "correct_option": "A",
                "explanation": "The 'finally' block is always executed when leaving a try-catch construct, ensuring critical cleanup such as closing I/O streams or database connections."
            }
        ]

    # 14. CSE / CSM: Data Structures & Algorithms
    elif has_any("data structure", "data structures", "ads", "algorithm", "algorithms", 
                 "tree", "trees", "hash", "linear", "queue", "stack", "heap", "avl"):
        pool = [
            {
                "question": "What is the primary condition for an AVL tree to remain balanced at every node $u$?",
                "options": {
                    "A": "Balance factor $\\text{BF}(u) = \\text{height}(L) - \\text{height}(R) \\in \\{-1, 0, +1\\}$",
                    "B": "Every node must have exactly two non-null children",
                    "C": "Depth of all leaf nodes must be strictly identical",
                    "D": "Root node key must equal the median of all tree keys"
                },
                "correct_option": "A",
                "explanation": "An AVL tree is a self-balancing binary search tree where the difference between left and right subtree heights never exceeds 1."
            },
            {
                "question": "Which collision resolution technique stores all colliding keys in an auxiliary linked list located at the hashed table slot?",
                "options": {
                    "A": "Separate Chaining (Open Hashing)",
                    "B": "Linear Probing",
                    "C": "Quadratic Probing",
                    "D": "Double Hashing"
                },
                "correct_option": "A",
                "explanation": "Separate chaining resolves hash collisions by maintaining a singly linked list at each table index bucket."
            },
            {
                "question": "What is the worst-case time complexity of extracting the minimum element from a Binary Min-Heap containing $n$ elements?",
                "options": {
                    "A": "$\\mathcal{O}(\\log n)$",
                    "B": "$\\mathcal{O}(1)$",
                    "C": "$\\mathcal{O}(n)$",
                    "D": "$\\mathcal{O}(n \\log n)$"
                },
                "correct_option": "A",
                "explanation": "Extracting the root takes $\\mathcal{O}(1)$, but restoring the heap order property via downward percolate (sift-down) takes $\\mathcal{O}(\\log n)$."
            },
            {
                "question": "What is the maximum height of a Red-Black tree with $n$ internal keys?",
                "options": {
                    "A": "$2 \\log_2(n + 1)$",
                    "B": "$\\log_2 n$",
                    "C": "$n / 2$",
                    "D": "$n - 1$"
                },
                "correct_option": "A",
                "explanation": "Due to the black-height property, the path from root to farthest leaf is at most twice the path to the nearest leaf, guaranteeing height $\\le 2\\log_2(n+1)$."
            },
            {
                "question": "Which data structure is fundamentally utilized to implement Breadth-First Search (BFS) graph traversal?",
                "options": {
                    "A": "Queue",
                    "B": "Stack",
                    "C": "Priority Queue (Min-Heap)",
                    "D": "Hash Map"
                },
                "correct_option": "A",
                "explanation": "BFS explores vertices level-by-level in First-In-First-Out (FIFO) order using a Queue data structure."
            }
        ]

    # 15. CSE / CSM: Operating Systems
    elif has_any("operating system", "operating systems", "os", "fos", "cpu scheduling", "deadlock", "virtual memory"):
        pool = [
            {
                "question": "Which CPU scheduling algorithm provably minimizes average waiting time for a set of stationary processes?",
                "options": {
                    "A": "Shortest Job First (SJF / SRTF)",
                    "B": "First-Come, First-Served (FCFS)",
                    "C": "Round Robin (RR)",
                    "D": "Priority Scheduling without preemption"
                },
                "correct_option": "A",
                "explanation": "SJF is provably optimal because scheduling shorter burst processes first minimizes queue wait times for subsequent processes."
            },
            {
                "question": "Which of the following is NOT one of the four Coffman conditions necessary for deadlock to occur?",
                "options": {
                    "A": "Preemption of Allocated Resources",
                    "B": "Mutual Exclusion",
                    "C": "Hold and Wait",
                    "D": "Circular Wait"
                },
                "correct_option": "A",
                "explanation": "The four Coffman conditions are Mutual Exclusion, Hold & Wait, No Preemption, and Circular Wait. Preemption breaks deadlock."
            },
            {
                "question": "Belady's Anomaly is an unexpected phenomenon where increasing page frames leads to more page faults. Which page replacement algorithm exhibits this?",
                "options": {
                    "A": "First-In, First-Out (FIFO)",
                    "B": "Least Recently Used (LRU)",
                    "C": "Optimal Page Replacement (OPT)",
                    "D": "Least Frequently Used (LFU)"
                },
                "correct_option": "A",
                "explanation": "FIFO is not a stack algorithm, so adding more physical page frames can paradoxically increase page faults for certain reference strings."
            },
            {
                "question": "What is the primary role of the Translation Lookaside Buffer (TLB) in virtual memory architectures?",
                "options": {
                    "A": "Cache recently translated virtual page number to physical frame number mappings",
                    "B": "Store disk sector addresses for dirty page writeback",
                    "C": "Arbitrate bus access between CPU and DMA controllers",
                    "D": "Queue pending process control blocks during context switching"
                },
                "correct_option": "A",
                "explanation": "The TLB is an associative hardware cache that speeds up virtual-to-physical address translation by avoiding page table memory lookups."
            }
        ]

    # 16. CSE / CSM: Database Management Systems (DBMS)
    elif has_any("database", "dbms", "sql", "normalization", "relational", "ids", "idbs"):
        pool = [
            {
                "question": "Which normal form requires that a relation is in 2NF and has NO transitive dependencies between non-prime attributes?",
                "options": {
                    "A": "Third Normal Form (3NF)",
                    "B": "First Normal Form (1NF)",
                    "C": "Second Normal Form (2NF)",
                    "D": "Boyce-Codd Normal Form (BCNF)"
                },
                "correct_option": "A",
                "explanation": "3NF removes transitive dependencies, requiring that for every functional dependency $X \\rightarrow Y$, either $X$ is a superkey or $Y$ is a prime attribute."
            },
            {
                "question": "What property of database transactions ensures that either all operations of a transaction complete, or none of them are reflected in the database?",
                "options": {
                    "A": "Atomicity",
                    "B": "Consistency",
                    "C": "Isolation",
                    "D": "Durability"
                },
                "correct_option": "A",
                "explanation": "Atomicity (the 'A' in ACID) guarantees all-or-nothing execution, rolling back changes if any step fails."
            },
            {
                "question": "Why are B+ Trees preferred over B-Trees for disk-based database indexing?",
                "options": {
                    "A": "All data pointers reside exclusively in leaf nodes linked sequentially, optimizing range scans.",
                    "B": "B+ Trees have lower fan-out and deeper tree heights.",
                    "C": "B+ Trees require zero balancing rotations upon key insertion.",
                    "D": "B+ Trees store non-key data only in internal nodes."
                },
                "correct_option": "A",
                "explanation": "In B+ Trees, internal nodes only store navigation keys (maximizing fan-out), while all data records are in leaf nodes linked as a singly/doubly linked list for rapid sequential range queries."
            }
        ]

    # 17. CSE / CSM: Computer Networks
    elif has_any("computer network", "computer networks", "cn", "tcp", "ip", "osi", "arp", "udp", "icn"):
        pool = [
            {
                "question": "Which layer of the OSI reference model is responsible for logical IP addressing, packet routing, and forwarding?",
                "options": {
                    "A": "Network Layer (Layer 3)",
                    "B": "Data Link Layer (Layer 2)",
                    "C": "Transport Layer (Layer 4)",
                    "D": "Session Layer (Layer 5)"
                },
                "correct_option": "A",
                "explanation": "The Network Layer (Layer 3) handles end-to-end packet delivery, host addressing (IPv4/IPv6), and routing path determination."
            },
            {
                "question": "In the TCP 3-way connection handshake, what is the exact sequence of flag packets exchanged between client and server?",
                "options": {
                    "A": "SYN $\\rightarrow$ SYN-ACK $\\rightarrow$ ACK",
                    "B": "ACK $\\rightarrow$ SYN $\\rightarrow$ ACK-SYN",
                    "C": "FIN $\\rightarrow$ ACK $\\rightarrow$ FIN-ACK",
                    "D": "SYN $\\rightarrow$ ACK $\\rightarrow$ DATA"
                },
                "correct_option": "A",
                "explanation": "TCP establishes a reliable duplex connection using SYN (client), SYN-ACK (server response), and ACK (client confirmation)."
            },
            {
                "question": "What protocol resolves a known logical IP address to a physical MAC hardware address on a local area network?",
                "options": {
                    "A": "ARP (Address Resolution Protocol)",
                    "B": "DNS (Domain Name System)",
                    "C": "DHCP (Dynamic Host Configuration Protocol)",
                    "D": "ICMP (Internet Control Message Protocol)"
                },
                "correct_option": "A",
                "explanation": "ARP broadcasts on the local subnet to map a destination IPv4 address to its 48-bit MAC Ethernet hardware address."
            }
        ]

    # 18. Mathematics (Engineering Mathematics, Calculus, Probability)
    elif has_any("mathematics", "calculus", "differential equations", "matrices", "eigenvalues", 
                 "laplace", "probability", "statistical", "cvnm", "numerical methods"):
        pool = [
            {
                "question": "According to the Cayley-Hamilton Theorem, what matrix relation holds for every square matrix $\\mathbf{A}$ with characteristic polynomial $P(\\lambda) = \\det(\\lambda\\mathbf{I} - \\mathbf{A})$?",
                "options": {
                    "A": "Every square matrix satisfies its own characteristic equation: $P(\\mathbf{A}) = \\mathbf{0}$.",
                    "B": "The determinant of $\\mathbf{A}$ equals the product of its diagonal elements.",
                    "C": "The inverse matrix $\\mathbf{A}^{-1}$ equals its transpose $\\mathbf{A}^T$.",
                    "D": "All eigenvalues must be purely imaginary."
                },
                "correct_option": "A",
                "explanation": "The Cayley-Hamilton theorem states that substituting matrix $\\mathbf{A}$ into its characteristic scalar polynomial produces the null matrix ($P(\\mathbf{A}) = \\mathbf{0}$), enabling high matrix powers and matrix inversion."
            },
            {
                "question": "What is the Laplace transform $\\mathcal{L}\\{e^{at}\\}$ for $s > a$?",
                "options": {
                    "A": "$\\frac{1}{s - a}$",
                    "B": "$\\frac{1}{s + a}$",
                    "C": "$\\frac{a}{s^2 + a^2}$",
                    "D": "$\\frac{s}{s^2 - a^2}$"
                },
                "correct_option": "A",
                "explanation": "Evaluating the definition integral $\\int_0^\\infty e^{-st} e^{at} dt = \\int_0^\\infty e^{-(s-a)t} dt = \\frac{1}{s - a}$ for $\\text{Re}(s) > a$."
            },
            {
                "question": "What is the rank of a matrix $\\mathbf{A}_{m \\times n}$ in linear algebra?",
                "options": {
                    "A": "The maximum number of linearly independent row vectors or column vectors in the matrix.",
                    "B": "The total number of non-zero entries in the matrix.",
                    "C": "The product $m \\times n$.",
                    "D": "The absolute value of its trace."
                },
                "correct_option": "A",
                "explanation": "Rank represents the dimension of the vector space spanned by its rows or columns, determined by the order of the highest non-zero minor."
            }
        ]

    # 19. Specialized Circuits & Network Analysis
    elif has_any("circuit analysis", "network analysis", "eca-i", "eca-ii", "thevenin", "norton", "two-port", "two port"):
        pool = [
            {
                "question": "Kirchhoff's Current Law (KCL) at any junction in an electrical circuit is a direct consequence of which conservation law?",
                "options": {
                    "A": "Conservation of Electric Charge",
                    "B": "Conservation of Energy",
                    "C": "Conservation of Momentum",
                    "D": "Conservation of Magnetic Flux"
                },
                "correct_option": "A",
                "explanation": "KCL states that the algebraic sum of currents entering a node is zero, which is conservation of electric charge."
            },
            {
                "question": "According to Thevenin's Theorem, any linear two-terminal bilateral resistive network can be replaced by:",
                "options": {
                    "A": "An ideal voltage source $V_{th}$ in series with an equivalent resistance $R_{th}$",
                    "B": "An ideal current source $I_N$ in parallel with an equivalent resistance $R_N$",
                    "C": "A pure capacitance in parallel with an ideal voltage source",
                    "D": "A dependent voltage source in series with an ideal diode"
                },
                "correct_option": "A",
                "explanation": "Thevenin's theorem reduces complex linear networks to a single independent voltage source $V_{th}$ in series with $R_{th}$."
            },
            {
                "question": "Under what condition is maximum power transferred from an AC source with internal impedance $Z_s = R_s + jX_s$ to a load impedance $Z_L = R_L + jX_L$?",
                "options": {
                    "A": "$Z_L = Z_s^*$ (Complex Conjugate: $R_L = R_s$ and $X_L = -X_s$)",
                    "B": "$Z_L = Z_s$",
                    "C": "$R_L = 0$ and $X_L = 0$",
                    "D": "$Z_L = -Z_s$"
                },
                "correct_option": "A",
                "explanation": "Maximum power transfer theorem for AC states that load impedance must be the complex conjugate of source impedance ($Z_L = Z_s^*$) to cancel reactances."
            }
        ]

    # DYNAMIC TOPIC-BASED QUESTION SYNTHESIS
    # Extract topics from syllabus to enrich pool or provide specialized questions
    extracted_topics = split_topics(unit_topics or "")
    if not extracted_topics and unit_title:
        extracted_topics = [t.strip() for t in re.split(r'[:\-–]', unit_title) if len(t.strip()) > 3]

    if extracted_topics:
        # Create syllabus-grounded dynamic questions
        dynamic_questions = []
        for top in extracted_topics:
            dynamic_questions.append({
                "question": f"In the study of '{top}' within {subject_name}, which analytical principle or governing characteristic is most essential?",
                "options": {
                    "A": f"It establishes the foundational operational constraints and governing performance criteria for '{top}'.",
                    "B": f"It represents an empirical approximation that violates standard conservation laws.",
                    "C": f"It only applies when all dynamic state variables evaluate to zero.",
                    "D": f"It eliminates all external dependencies and hardware boundary conditions."
                },
                "correct_option": "A",
                "explanation": f"In {subject_name}, understanding '{top}' provides rigorous analytical principles and operating boundary conditions according to the engineering syllabus."
            })
            dynamic_questions.append({
                "question": f"When evaluating system performance for '{top}' in {subject_name}, what is the primary design trade-off?",
                "options": {
                    "A": f"Balancing optimal operational efficiency against design constraints and stability margins.",
                    "B": f"Maximizing parasitic losses to lower operating temperature.",
                    "C": f"Disregarding steady-state response characteristics entirely.",
                    "D": f"Operating exclusively in open-loop saturation."
                },
                "correct_option": "A",
                "explanation": f"Engineering analysis of '{top}' requires balancing efficiency, stability margins, and component ratings."
            })

        # If pool was empty (no static domain matched), dynamic questions become our pool!
        if not pool:
            pool = dynamic_questions
        else:
            # Enrich existing domain pool with unit-specific topic questions
            pool = pool + dynamic_questions[:3]

    # Fallback if pool is still empty
    if not pool:
        pool = [
            {
                "question": f"In {subject_name} ({unit_title}), which factor is most critical when analyzing system stability and performance?",
                "options": {
                    "A": "Adherence to governing domain physical laws and operational boundary constraints",
                    "B": "Minimizing operating parameters to negative values",
                    "C": "Ignoring steady-state response characteristics",
                    "D": "Exclusively prioritizing transient overshoot"
                },
                "correct_option": "A",
                "explanation": f"System analysis in {subject_name} requires strict adherence to governing equations and operational constraints."
            }
        ]

    # SELECTION & SHUFFLING
    # 1. Sample requested number of questions
    if seed is not None:
        if len(pool) >= count:
            selected = rng.sample(pool, count)
        else:
            selected = list(pool)
            while len(selected) < count:
                selected.append(rng.choice(pool))
    else:
        # Deterministic slice for stable tests without seed
        selected = pool[:count]
        while len(selected) < count:
            idx = len(selected) + 1
            selected.append({
                "question": f"In {subject_name} ({unit_title}), what principle governs concept #{idx}?",
                "options": {
                    "A": "Adherence to engineering governing standards and boundary constraints",
                    "B": "Unconstrained extrapolation beyond physical limits",
                    "C": "Arbitrary omission of intermediate states",
                    "D": "Neglecting system losses entirely"
                },
                "correct_option": "A",
                "explanation": "Engineering systems adhere to fundamental physical conservation laws and boundary parameters."
            })

    # 2. Shuffle options for each question (if seed is provided or randomly)
    final_questions = []
    for idx, q in enumerate(selected):
        if seed is not None:
            shuffled_q = shuffle_question_options(q, rng)
        else:
            shuffled_q = dict(q)
        shuffled_q["question_number"] = idx + 1
        final_questions.append(shuffled_q)

    return final_questions


def generate_subject_short_answers(
    subject_name: str, 
    unit_title: str, 
    unit_topics: Optional[str] = None, 
    count: int = 5,
    seed: Optional[int] = None
) -> str:
    count = max(3, min(10, int(count)))
    rng = random.Random(seed) if seed is not None else random.Random()
    text_corpus = f" {subject_name} {unit_title} {unit_topics or ''} ".lower()

    def has_any(*patterns: str) -> bool:
        for p in patterns:
            if re.search(r'\b' + re.escape(p) + r'\b', text_corpus, re.IGNORECASE):
                return True
        return False

    pool = []

    # 1. EEE: Power Systems
    if has_any("power system", "power systems", "ps-i", "ps-ii", "ps1", "ps2", "ps3", "psa", "psoc", 
               "switchgear", "sgp", "transmission line", "overhead line", "distribution", "insulator", 
               "corona", "ferranti", "transients", "substation"):
        pool = [
            {
                "question": "Derive the mathematical expression for the Ferranti effect in a medium transmission line using the nominal $\\pi$ model under no-load conditions.",
                "solution": "In a nominal $\\pi$ model of a line with impedance $Z = R + j\\omega L$ and total shunt admittance $Y = j\\omega C$:\n"
                            "1. At no-load ($I_R = 0$), receiving-end current is zero, and current flowing through series impedance is $I_Z = I_{C2} = V_R (Y/2) = V_R (j\\omega C / 2)$.\n"
                            "2. The sending-end voltage is $V_S = V_R + I_Z \\cdot Z = V_R + V_R \\frac{Y Z}{2} = V_R \\left(1 + \\frac{Y Z}{2}\\right)$.\n"
                            "3. Neglecting resistance ($R \\approx 0$), $Z = j\\omega L$ and $Y = j\\omega C$, so $Y Z = (j\\omega C)(j\\omega L) = -\\omega^2 L C$.\n"
                            "4. Substituting: $V_S = V_R \\left(1 - \\frac{\\omega^2 L C}{2}\\right) \\implies V_R = \\frac{V_S}{1 - \\frac{\\omega^2 L C}{2}} > V_S$.\n"
                            "Thus, the receiving end voltage exceeds sending end voltage under light or no-load conditions.",
                "takeaway": "Ferranti effect occurs because line charging current produces a leading voltage rise across the series line inductance."
            },
            {
                "question": "Explain how string efficiency is defined for suspension insulators and derive the expression for a 3-unit insulator string with pin-to-tower shunt capacitance $C_1 = kC$.",
                "solution": "1. Let $C$ be self-capacitance and $C_1 = kC$ be shunt capacitance.\n"
                            "2. By KCL at junction 1: $I_2 = I_1 + i_1 \\implies V_2 \\omega C = V_1 \\omega C + V_1 \\omega (kC) \\implies V_2 = V_1(1 + k)$.\n"
                            "3. By KCL at junction 2: $I_3 = I_2 + i_2 \\implies V_3 = V_2 + (V_1 + V_2)k = V_1(1 + 3k + k^2)$.\n"
                            "4. Total string voltage $V = V_1 + V_2 + V_3 = V_1(3 + 4k + k^2)$.\n"
                            "5. String Efficiency: $\\eta = \\frac{V}{n \\cdot V_n} \\times 100\\% = \\frac{3 + 4k + k^2}{3(1 + 3k + k^2)} \\times 100\\%$.",
                "takeaway": "String efficiency increases as shunt capacitance ratio $k \\to 0$, which can be improved using longer cross-arms or grading rings."
            },
            {
                "question": "Explain the concept of Surge Impedance Loading (SIL) of an overhead transmission line and state its governing equation.",
                "solution": "1. Surge Impedance Loading is the active power delivered by a lossless transmission line to a pure resistive load equal to its surge impedance $Z_c = \\sqrt{L/C}$.\n"
                            "2. At this load, reactive power generated by shunt capacitance ($Q_C = V^2 \\omega C$) exactly cancels reactive power absorbed by series inductance ($Q_L = I^2 \\omega L$).\n"
                            "3. The voltage profile along the entire line becomes flat: $V(x) = V_S = V_R$.\n"
                            "4. Analytical formula: $\\text{SIL} = \\frac{V_{L-L}^2}{Z_c}$ (in MW), where $Z_c \\approx 400\\,\\Omega$ for overhead lines and $40\\,\\Omega$ for underground cables.",
                "takeaway": "Operating at SIL provides unity power factor without requiring external shunt reactive compensation."
            },
            {
                "question": "Describe the physical mechanism of Corona discharge in overhead EHV transmission lines and identify methods to mitigate it.",
                "solution": "1. When surface electric field gradient exceeds the dielectric breakdown strength of air ($g_0 = 30\\text{ kV/cm (peak)}$ at STP), ionization occurs.\n"
                            "2. Free electrons accelerate in the high field, ionizing surrounding air molecules by collision, producing a violet glow, hissing noise, and ozone gas ($\\text{O}_3$).\n"
                            "3. Peek's formula for disruptive critical voltage: $V_d = m_0 g_0 \\delta r \\ln(D/r)$, where $r$ is conductor radius and $D$ is spacing.\n"
                            "4. Mitigation techniques: (a) Using hollow or ACSR conductors to increase radius $r$, (b) Using bundled conductors to increase effective GMR, (c) Increasing conductor spacing $D$.",
                "takeaway": "Corona causes active power loss ($P_c \\propto (f + 25)(V - V_d)^2$) and radio interference; increasing effective conductor radius mitigates it."
            }
        ]

    # 2. EEE: Electrical Machines
    elif has_any("electrical machine", "electrical machines", "emc-i", "emc-ii", "emc1", "emc2", 
                 "dc machine", "dc machines", "dcmt", "induction machine", "induction motor", 
                 "synchronous machine", "alternator", "transformer", "ism"):
        pool = [
            {
                "question": "Derive the torque equation of a DC motor from fundamental electromagnetic relations and describe the governing role of Back EMF ($E_b$).",
                "solution": "1. Electrical power supplied to the armature: $V I_a = E_b I_a + I_a^2 R_a$.\n"
                            "2. Gross mechanical power developed: $P_m = E_b I_a = T_e \\cdot \\omega_m$, where $\\omega_m = \\frac{2\\pi N}{60}$.\n"
                            "3. Since $E_b = \\frac{\\Phi Z N P}{60 A}$, substituting gives: $T_e \\cdot \\left(\\frac{2\\pi N}{60}\\right) = \\left(\\frac{\\Phi Z N P}{60 A}\\right) I_a$.\n"
                            "4. Developed torque: $T_e = \\frac{P Z}{2\\pi A} \\cdot \\Phi I_a = K_a \\Phi I_a$ (in $\\text{N}\\cdot\\text{m}$).\n"
                            "5. Back EMF acts as a self-regulating governor: if load torque increases, motor slows down, $E_b$ drops, which increases armature current $I_a = (V - E_b)/R_a$ to match load torque.",
                "takeaway": "Torque is directly proportional to field flux and armature current ($T_e \\propto \\Phi I_a$), regulated dynamically by Back EMF."
            },
            {
                "question": "Explain the step-by-step procedure to determine the equivalent circuit parameters of a transformer from Open-Circuit (OC) and Short-Circuit (SC) tests.",
                "solution": "1. **Open-Circuit Test** (conducted on LV side at rated voltage $V_1$, HV open):\n"
                            "   - Current is no-load current $I_0$; wattmeter reads iron loss $W_0$.\n"
                            "   - Core loss resistance: $R_c = \\frac{V_1^2}{W_0}$.\n"
                            "   - Magnetizing reactance: $X_m = \\frac{V_1}{I_m}$, where $I_m = \\sqrt{I_0^2 - I_c^2}$ and $I_c = W_0 / V_1$.\n"
                            "2. **Short-Circuit Test** (conducted on HV side with LV shorted at low voltage $V_{sc}$ to circulate rated current $I_{sc}$):\n"
                            "   - Wattmeter reads full-load copper loss $W_{sc}$.\n"
                            "   - Equivalent resistance: $R_{eq} = \\frac{W_{sc}}{I_{sc}^2}$.\n"
                            "   - Equivalent impedance: $Z_{eq} = \\frac{V_{sc}}{I_{sc}}$, so leakage reactance $X_{eq} = \\sqrt{Z_{eq}^2 - R_{eq}^2}$.",
                "takeaway": "OC test determines core loss parameters ($R_c, X_m$) at rated voltage; SC test determines winding series impedance ($R_{eq}, X_{eq}$) at rated current."
            },
            {
                "question": "Derive the condition for maximum torque in a three-phase induction motor and show that maximum torque is independent of rotor resistance.",
                "solution": "1. Torque developed by a 3-phase induction motor is given by: $T = \\frac{3}{\\omega_s} \\cdot \\frac{s E_2^2 R_2}{R_2^2 + (s X_2)^2}$.\n"
                            "2. Differentiating with respect to slip $s$ and equating to zero: $\\frac{dT}{ds} = 0 \\implies R_2 = s X_2 \\implies s_{mT} = \\frac{R_2}{X_2}$.\n"
                            "3. Substituting $s_{mT} = R_2/X_2$ back into the torque equation:\n"
                            "   $T_{max} = \\frac{3}{\\omega_s} \\cdot \\frac{(R_2/X_2) E_2^2 R_2}{R_2^2 + (R_2/X_2)^2 X_2^2} = \\frac{3}{2\\omega_s} \\cdot \\frac{E_2^2}{X_2}$.\n"
                            "4. Inspection reveals that $R_2$ cancels out completely in the expression for $T_{max}$.",
                "takeaway": "Peak torque $T_{max}$ depends only on applied voltage and standstill leakage reactance; adding rotor resistance shifts the slip at which $T_{max}$ occurs without changing its magnitude."
            }
        ]

    # 3. EEE / ECE: Modern Control Theory & Control Systems
    elif has_any("control system", "control systems", "control theory", "controllability", 
                 "observability", "mcth", "state space", "routh", "bode plot"):
        pool = [
            {
                "question": "State Kalman's rank test for controllability and observability of an LTI state-space system $\\dot{\\mathbf{x}} = \\mathbf{A}\\mathbf{x} + \\mathbf{B}\\mathbf{u}$, $\\mathbf{y} = \\mathbf{C}\\mathbf{x}$.",
                "solution": "1. For an $n$-th order system with state matrix $\\mathbf{A}_{n \\times n}$ and input matrix $\\mathbf{B}_{n \\times m}$:\n"
                            "   - Construct the Controllability Matrix: $\\mathbf{Q}_c = [\\mathbf{B} \\quad \\mathbf{A}\\mathbf{B} \\quad \\mathbf{A}^2\\mathbf{B} \\quad \\dots \\quad \\mathbf{A}^{n-1}\\mathbf{B}]$.\n"
                            "   - The system is completely state controllable if and only if $\\text{Rank}(\\mathbf{Q}_c) = n$ (full rank).\n"
                            "2. For output matrix $\\mathbf{C}_{p \\times n}$:\n"
                            "   - Construct the Observability Matrix: $\\mathbf{Q}_o = [\\mathbf{C}^T \\quad \\mathbf{A}^T\\mathbf{C}^T \\quad \\dots \\quad (\\mathbf{A}^{n-1})^T\\mathbf{C}^T]^T$.\n"
                            "   - The system is completely observable if and only if $\\text{Rank}(\\mathbf{Q}_o) = n$.",
                "takeaway": "Kalman rank tests evaluate whether all state modes couple into inputs (controllability) and outputs (observability)."
            },
            {
                "question": "Explain the properties and derivation of the State Transition Matrix $\\mathbf{\\Phi}(t) = e^{\\mathbf{A}t}$ using the Laplace transform method.",
                "solution": "1. The unforced homogeneous state equation is $\\dot{\\mathbf{x}}(t) = \\mathbf{A}\\mathbf{x}(t)$ with initial condition $\\mathbf{x}(0)$.\n"
                            "2. Taking the Laplace transform: $s\\mathbf{X}(s) - \\mathbf{x}(0) = \\mathbf{A}\\mathbf{X}(s) \\implies (s\\mathbf{I} - \\mathbf{A})\\mathbf{X}(s) = \\mathbf{x}(0)$.\n"
                            "3. Solving for $\\mathbf{X}(s)$: $\\mathbf{X}(s) = (s\\mathbf{I} - \\mathbf{A})^{-1}\\mathbf{x}(0)$.\n"
                            "4. Inverse Laplace gives: $\\mathbf{x}(t) = \\mathcal{L}^{-1}\\{(s\\mathbf{I} - \\mathbf{A})^{-1}\\} \\mathbf{x}(0) = \\mathbf{\\Phi}(t)\\mathbf{x}(0)$, where $\\mathbf{\\Phi}(t) = \\mathcal{L}^{-1}\\{(s\\mathbf{I} - \\mathbf{A})^{-1}\\} = e^{\\mathbf{A}t}$.\n"
                            "5. Key properties: (a) $\\mathbf{\\Phi}(0) = \\mathbf{I}$, (b) $\\mathbf{\\Phi}^{-1}(t) = \\mathbf{\\Phi}(-t)$, (c) $\\mathbf{\\Phi}(t_1 + t_2) = \\mathbf{\\Phi}(t_1)\\mathbf{\\Phi}(t_2)$.",
                "takeaway": "The state transition matrix maps the initial state vector at $t=0$ to the state trajectory at any time $t$."
            }
        ]

    # 4. EEE: Power Electronics
    elif has_any("power electronic", "power electronics", "thyristor", "scr", "chopper", "buck", "boost", "inverter"):
        pool = [
            {
                "question": "Derive the relationship between input voltage $V_s$ and average output voltage $V_o$ for a Step-Down (Buck) converter operating in Continuous Conduction Mode.",
                "solution": "1. During ON time ($0 \\le t < DT$), switch is closed and diode is reverse biased:\n"
                            "   Voltage across inductor is $v_L = V_s - V_o$, and current rises linearly: $\\frac{di_L}{dt} = \\frac{V_s - V_o}{L}$.\n"
                            "   Inductor flux change: $\\Delta \\lambda_{on} = (V_s - V_o) D T$.\n"
                            "2. During OFF time ($DT \\le t < T$), switch is open and freewheeling diode conducts:\n"
                            "   Voltage across inductor is $v_L = -V_o$, and current decays: $\\Delta \\lambda_{off} = (-V_o)(1 - D) T$.\n"
                            "3. By the Inductor Volt-Second Balance Principle in steady state, net change in flux over one complete switching period is zero:\n"
                            "   $(V_s - V_o) D T + (-V_o)(1 - D) T = 0 \\implies V_s D - V_o D - V_o + V_o D = 0 \\implies V_o = D V_s$.\n"
                            "4. Since duty cycle $0 < D < 1$, output voltage is always stepped down relative to input.",
                "takeaway": "Volt-second balance across the filter inductor governs the linear conversion ratio $V_o = D V_s$."
            }
        ]

    # 5. Civil Engineering: Surveying & SOM
    elif has_any("surveying", "compass surveying", "levelling", "strength of materials", "bending moment", "torsion", "som"):
        pool = [
            {
                "question": "Explain the difference between Whole Circle Bearing (WCB) and Quadrantal Bearing (QB), and convert $WCB = 215^\\circ 45'$ and $WCB = 310^\\circ 15'$ to QB.",
                "solution": "1. **Definitions**:\n"
                            "   - Whole Circle Bearing (WCB): Measured clockwise from Magnetic North from $0^\\circ$ to $360^\\circ$ using a Prismatic Compass.\n"
                            "   - Quadrantal Bearing (Reduced Bearing QB): Measured from North or South (whichever is closer) toward East or West from $0^\\circ$ to $90^\\circ$.\n"
                            "2. **Conversions**:\n"
                            "   - For $WCB = 215^\\circ 45'$: Lies in the third quadrant (South-West).\n"
                            "     $\\text{QB} = \\text{WCB} - 180^\\circ = 215^\\circ 45' - 180^\\circ = \\text{S } 35^\\circ 45' \\text{ W}$.\n"
                            "   - For $WCB = 310^\\circ 15'$: Lies in the fourth quadrant (North-West).\n"
                            "     $\\text{QB} = 360^\\circ - \\text{WCB} = 360^\\circ - 310^\\circ 15' = \\text{N } 49^\\circ 45' \\text{ W}$.",
                "takeaway": "WCB uses a single azimuth angle ($0^\\circ - 360^\\circ$), while QB incorporates cardinal quadrant prefixes and suffixes."
            },
            {
                "question": "Derive the pure bending formula $\\frac{M}{I} = \\frac{\\sigma}{y} = \\frac{E}{R}$ for a structural beam under transverse loading.",
                "solution": "1. Consider a beam section of radius of curvature $R$ bent by pure moment $M$.\n"
                            "2. At distance $y$ from the neutral axis, fiber strain is $\\epsilon = \\frac{\\Delta L}{L} = \\frac{(R + y)\\theta - R\\theta}{R\\theta} = \\frac{y}{R}$.\n"
                            "3. By Hooke's Law ($\\sigma = E \\epsilon$): $\\sigma = E \\cdot \\frac{y}{R} \\implies \\frac{\\sigma}{y} = \\frac{E}{R}$.\n"
                            "4. Total resisting moment of the section is $M = \\int y \\cdot dF = \\int y (\\sigma dA) = \\int y \\left(\\frac{E}{R} y\\right) dA = \\frac{E}{R} \\int y^2 dA = \\frac{E}{R} I$.\n"
                            "5. Combining both relations yields the Euler-Bernoulli flexural equation: $\\frac{M}{I} = \\frac{\\sigma}{y} = \\frac{E}{R}$.",
                "takeaway": "Bending stress varies linearly across the beam depth, reaching zero at the neutral axis and maximum at outer fibers."
            }
        ]

    # 6. Mechanical Engineering: Thermodynamics
    elif has_any("thermodynamic", "thermodynamics", "carnot", "entropy", "otto cycle", "diesel cycle"):
        pool = [
            {
                "question": "State the First Law of Thermodynamics for a control volume (Steady Flow Energy Equation SFEE) and apply it to a steam/gas turbine.",
                "solution": "1. The general SFEE on mass rate basis $\\dot{m}$ is:\n"
                            "   $\\dot{m} \\left(h_1 + \\frac{v_1^2}{2} + g z_1\\right) + \\dot{Q} = \\dot{m} \\left(h_2 + \\frac{v_2^2}{2} + g z_2\\right) + \\dot{W}_{cv}$.\n"
                            "2. Application to an adiabatic power turbine:\n"
                            "   - Expansion is well insulated: $\\dot{Q} \\approx 0$.\n"
                            "   - Elevation change is negligible: $\\Delta z = 0$.\n"
                            "   - Kinetic energy change is small relative to enthalpy drop: $\\Delta(v^2/2) \\approx 0$.\n"
                            "3. Resulting power equation: $\\dot{W}_{turbine} = \\dot{m}(h_1 - h_2)$ (in $\\text{kW}$).\n"
                            "Thus, turbine shaft work equals the drop in fluid specific enthalpy.",
                "takeaway": "In adiabatic turbomachinery, shaft work generated is directly proportional to enthalpy change between inlet and outlet."
            }
        ]

    # 7. ECE: VLSI Design
    elif has_any("vlsi", "cmos", "mos transistor", "stick diagram"):
        pool = [
            {
                "question": "Derive the formula for dynamic power dissipation in a static CMOS logic gate operating at frequency $f$ and explain the significance of the activity factor $\\alpha$.",
                "solution": "1. When the output switches from Low to High ($0 \\to 1$), load capacitance $C_L$ charges through the pMOS network.\n"
                            "   Total energy drawn from power supply: $E_{VDD} = \\int i(t) V_{DD} dt = V_{DD} \\int dq = V_{DD}(C_L V_{DD}) = C_L V_{DD}^2$.\n"
                            "2. Half of this energy ($0.5 C_L V_{DD}^2$) is stored on the capacitor, and half is dissipated as heat in the pMOS channel.\n"
                            "3. When switching from High to Low ($1 \\to 0$), the stored energy is dissipated to ground through the nMOS network.\n"
                            "4. Total energy dissipated per full clock cycle is $C_L V_{DD}^2$. For activity factor $\\alpha$ (probability of switching transition $0 \\to 1$):\n"
                            "   $P_{dyn} = \\alpha \\cdot C_L \\cdot V_{DD}^2 \\cdot f$.\n"
                            "5. Significance of $\\alpha$: Activity factor scales power according to circuit transition density, showing that lowering supply voltage $V_{DD}$ yields quadratic power savings.",
                "takeaway": "Dynamic power varies quadratically with supply voltage ($V_{DD}^2$) and linearly with clock frequency and switching activity."
            }
        ]

    # 8. CSE / CSM: Machine Learning & Algorithms
    elif has_any("machine learning", "deep learning", "bias-variance", "fml", "data structure", "algorithm", "ads"):
        pool = [
            {
                "question": "Provide the mathematical decomposition of Expected Prediction Error into Bias, Variance, and Irreducible Noise for a regression model.",
                "solution": "1. Let true target $y = f(x) + \\epsilon$, where $\\mathbb{E}[\\epsilon] = 0$ and $\\text{Var}(\\epsilon) = \\sigma^2$. Let $\\hat{f}(x)$ be model prediction.\n"
                            "2. Expected Mean Squared Error at query point $x$:\n"
                            "   $\\mathbb{E}[(y - \\hat{f}(x))^2] = \\mathbb{E}[((f(x) - \\mathbb{E}[\\hat{f}(x)]) + (\\mathbb{E}[\\hat{f}(x)] - \\hat{f}(x)) + \\epsilon)^2]$.\n"
                            "3. Expanding cross-terms (which evaluate to zero due to independence of error $\\epsilon$):\n"
                            "   $\\mathbb{E}[(y - \\hat{f}(x))^2] = (f(x) - \\mathbb{E}[\\hat{f}(x)])^2 + \\mathbb{E}[(\\hat{f}(x) - \\mathbb{E}[\\hat{f}(x)])^2] + \\sigma^2$.\n"
                            "4. Final analytical decomposition:\n"
                            "   $\\text{MSE} = \\text{Bias}(\\hat{f}(x))^2 + \\text{Var}(\\hat{f}(x)) + \\sigma^2$.\n"
                            "   - **Bias$^2$**: Error from simplistic modeling assumptions (Underfitting).\n"
                            "   - **Variance**: Sensitivity of predictions to training set variations (Overfitting).\n"
                            "   - **$\\sigma^2$**: Inherent irreducible data noise.",
                "takeaway": "Optimal machine learning models minimize total error by finding the sweet spot balancing Bias and Variance."
            }
        ]

    # 9. Dynamic Syllabus-Topic Generator
    extracted_topics = split_topics(unit_topics or "")
    if not extracted_topics and unit_title:
        extracted_topics = [t.strip() for t in re.split(r'[:\-–]', unit_title) if len(t.strip()) > 3]

    if extracted_topics:
        dynamic_sa = []
        for top in extracted_topics:
            dynamic_sa.append({
                "question": f"Explain the governing principle, analytical formulation, and engineering significance of '{top}' in {subject_name}.",
                "solution": f"1. **Governing Principle**: '{top}' establishes foundational analytical criteria and boundary constraints in {subject_name}.\n"
                            f"2. **Governing Equations**: Quantitative evaluation utilizes standard governing conservation laws and constitutive relationships for {top}.\n"
                            f"3. **Engineering Application**: Accurate modeling of '{top}' ensures system stability, operational efficiency, and standard compliance across varying operating regimes.\n"
                            f"4. **Design Trade-offs**: Engineers must balance performance parameters against practical thermal, mechanical, or electrical tolerances.",
                "takeaway": f"In {subject_name}, '{top}' provides essential theoretical and practical foundations for rigorous design and performance analysis."
            })
        if not pool:
            pool = dynamic_sa
        else:
            pool = pool + dynamic_sa[:2]

    if not pool:
        pool = [
            {
                "question": f"Explain the foundational concepts and analytical framework governing {subject_name} ({unit_title}).",
                "solution": f"1. Formulate physical laws governing {subject_name}.\n2. Apply boundary conditions for {unit_title}.\n3. Compute performance parameters.\n4. Verify compliance with engineering standards.",
                "takeaway": "Adherence to governing domain laws ensures reliable performance and stability."
            }
        ]

    if seed is not None:
        if len(pool) >= count:
            selected = rng.sample(pool, count)
        else:
            selected = list(pool)
            while len(selected) < count:
                selected.append(rng.choice(pool))
    else:
        selected = pool[:count]
        while len(selected) < count:
            idx = len(selected) + 1
            selected.append({
                "question": f"Describe the analytical procedure and governing equations for Concept #{idx} in {subject_name} ({unit_title}).",
                "solution": f"1. Identify system variables and parameters for Concept #{idx}.\n2. Formulate governing equilibrium or dynamic equations.\n3. Solve for unknown state variables under specified boundary conditions.\n4. Interpret results in terms of practical engineering design.",
                "takeaway": f"System analysis requires consistent application of physical conservation principles."
            })

    # Format output markdown
    lines = []
    for idx, item in enumerate(selected):
        lines.append(f"### Question {idx + 1}:\n{item['question']}\n\n**Answer & Step-by-Step Solution:**\n{item['solution']}\n\n**Key Takeaway / Explanation:**\n{item['takeaway']}\n\n---")

    lines.append(f"\n{VERIFICATION_LINE}")
    return "\n\n".join(lines)


def build_practice_prompt(
    subject_name: str, 
    unit_title: str, 
    num_questions: int, 
    question_type: str, 
    unit_topics: Optional[str] = None,
    seed: Optional[int] = None
) -> Tuple[str, str]:
    """
    Builds prompt for AI-generated practice questions (3 to 10 questions).
    Type: "Multiple Choice" or "Short Answer".
    Labeled: "AI-generated practice questions, not from previous exam papers".
    """
    count = max(3, min(10, int(num_questions)))
    q_type_lower = (question_type or "multiple choice").lower()
    is_mcq = "choice" in q_type_lower

    if is_mcq:
        system_prompt = f"""You are a strict automated engineering exam assistant generating practice questions for a B.Tech student in India.
Header Label: "{PRACTICE_DISCLAIMER}"

MANDATORY RULES FOR MULTIPLE CHOICE QUESTIONS:
- Generate exactly {count} multiple choice questions for the chosen unit and subject.
- Questions must test core engineering concepts, definitions, syntax/formulas, and problem application according to the syllabus.
- You must output ONLY a valid JSON array wrapped in a ```json code block.
- ABSOLUTELY NO internal thoughts, reasoning steps, chain-of-thought, planning steps, or meta-commentary (such as "We need to generate", "Let's craft", etc.).
- Start your response immediately with ```json and end with ```.
- After the closing ``` of the JSON code block, include:
  "{VERIFICATION_LINE}"
"""
        format_instructions = f"""
Output the questions strictly in this JSON format inside a ```json code block:
```json
[
  {{
    "question_number": 1,
    "question": "Clear question text testing a specific concept (use LaTeX $...$ if mathematical)",
    "options": {{
      "A": "Option A text",
      "B": "Option B text",
      "C": "Option C text",
      "D": "Option D text"
    }},
    "correct_option": "A",
    "explanation": "Clear step-by-step explanation of why this option is correct."
  }}
]
```
CRITICAL: Do NOT write any introduction or thoughts. Begin immediately with ```json."""
    else:
        system_prompt = f"""You are an engineering tutor preparing practice questions for a B.Tech student in India.
Header Label: "{PRACTICE_DISCLAIMER}"

Guidelines:
- Generate exactly {count} {question_type} questions for the chosen unit and subject.
- Ensure questions test fundamental concepts, derivations, and numerical application according to the syllabus.
- Do NOT claim questions are from previous year question papers.
- Write mathematical expressions in LaTeX between $ signs.
- CRITICAL: Output ONLY the final practice questions directly. Do NOT output "Analyze the Request", planning commentary, or scratchpads.
- End your entire response with:
  "{VERIFICATION_LINE}"
"""
        format_instructions = """
Format each question clearly with markdown numbering:
### Question X:
[Question description, given parameters]

**Answer & Step-by-Step Solution:**
[Clear derivation or calculation with LaTeX formulas and units]

**Key Takeaway / Explanation:**
[Short explanation of the concept]
---
"""

    topics_ctx = f"\nTopics covered: {unit_topics}" if unit_topics else ""
    seed_str = f"\nVariation/Seed: {seed}. Ensure newly generated questions test distinct subtopics." if seed is not None else ""
    user_prompt = f"""Subject: {subject_name}
Unit: {unit_title}{topics_ctx}{seed_str}
Requested Question Count: {count}
Question Type: {question_type}

{format_instructions}
Remember to adhere to "{PRACTICE_DISCLAIMER}" and include the verification line at the end. Begin directly without introductory commentary."""

    return system_prompt, user_prompt


def build_quick_revision_prompt(
    subject_name: str, 
    unit_title: str, 
    unit_topics: Optional[str] = None
) -> Tuple[str, str]:
    """
    Builds prompt for a one-page summary of a chosen unit:
    - Key points
    - Formulas
    - Definitions
    - 5-line recap
    """
    system_prompt = f"""You are a patient B.Tech engineering tutor creating a concise, high-yield one-page quick revision sheet.

Structure the revision sheet into these exact 4 sections using markdown headers:
### 1. Key Points
(High-yield summary of core concepts in bullet points)

### 2. Formulas & Governing Equations
(All formulas in LaTeX between $ signs, defining all variables and units)

### 3. Essential Definitions
(Key technical terms defined in crisp, accurate sentences)

### 4. 5-Line Recap
(Exactly 5 bullet lines summarizing the whole unit for fast recall)

Guidelines:
- Plain language, short sentences.
- Never invent textbook page numbers, equation numbers, or exam years.
- CRITICAL: Output ONLY the final revision sheet directly. Do NOT output "Analyze the Request", planning commentary, drafting notes, or constraint reviews. Begin immediately with "### 1. Key Points".
- Conclude with the exact line:
  "{VERIFICATION_LINE}"
"""

    topics_ctx = f"\nTopics in Unit: {unit_topics}" if unit_topics else ""
    user_prompt = f"""Subject: {subject_name}
Unit: {unit_title}{topics_ctx}

Please generate the one-page quick revision sheet. Begin directly with '### 1. Key Points' without any introductory preamble, analysis, or drafting notes."""

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# LLM INFERENCE, CLEANING, AND CACHING
# ---------------------------------------------------------------------------

def clean_subject_response(text: str) -> str:
    """
    Cleans LLM response of internal reasoning leaks, chain-of-thought scratchpads,
    and drafting preambles (e.g. 'Analyze the Request', 'Drafting Section', 'Review against constraints').
    """
    if not text or not isinstance(text, str):
        return ""

    cleaned = text.strip()

    # 1. Strip <think>...</think> tags from reasoning models
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned, flags=re.IGNORECASE).strip()

    # 1b. If there is a ```json code block, strip any pre-JSON planning/reasoning scratchpads
    json_match = re.search(r'```(?:json)?\s*\[\s*\{[\s\S]*?\}\s*\]\s*```', cleaned, re.IGNORECASE)
    if json_match:
        pre_text = cleaned[:json_match.start()].strip()
        if pre_text and any(w in pre_text.lower() for w in ["we need to", "thinking", "scratchpad", "let's craft", "plan", "analyze", "question 1", "output should be"]):
            cleaned = cleaned[json_match.start():].strip()

    # 2. If the model slipped into "Drafting Section X" mode, convert to clean sections
    if re.search(r'Drafting Section \d+:', cleaned, re.IGNORECASE):
        # Strip all preamble before the first Drafting Section
        cleaned = re.sub(r'^[\s\S]*?(?=(?:\d+\.\s*)?\*{0,2}Drafting Section 1:)', '', cleaned, flags=re.IGNORECASE)
        # Strip trailing "Review against constraints" or quality check blocks
        cleaned = re.sub(r'\n\s*(?:\d+\.\s*)?\*{0,2}Review against constraints:?[\s\S]*$', '', cleaned, flags=re.IGNORECASE)
        # Convert 'Drafting Section X: Y' to '### \1. \2'
        cleaned = re.sub(r'(?:\d+\.\s*)?\*{0,2}Drafting Section (\d+):?\s*([^\n*]+)\*{0,2}', r'### \1. \2', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

    # 3. Strip general scratchpad preambles (e.g. "Here's a thinking process:", "Analyze the Request:")
    scratchpad_prefix = re.compile(
        r'^\s*(?:here[\'’]?s\s+(?:a\s+)?(?:thinking\s+process|plan)|ok(?:ay)?,\s*here[\'’]?s|(?:\d+\.\s*)?\*{0,2}(?:analyze\s+(?:the\s+|user\s+)?request|thinking\s+process|chain\s+of\s+thought|internal\s+reasoning|drafting\s+plan)\*{0,2}[:\s])'
        r'[\s\S]*?'
        r'(?=\n\s*(?:#{1,4}\s+|(?:\d+\.\s*)?\*{1,2}(?:1\.|Short Intro|Key Points|Question 1|Final Answer|Answer to Student)))',
        re.IGNORECASE
    )
    cleaned = scratchpad_prefix.sub('', cleaned).strip()

    # 3b. Slicing check: if any thinking/reasoning preamble exists before first real heading
    header_match = re.search(r'\n\s*(?:#{1,4}\s+|(?:\d+\.\s*)?\*{1,2})(?:1\.|Key Points|Short Intro|Question 1)\b', cleaned, re.IGNORECASE)
    if header_match and any(phrase in cleaned[:header_match.start()].lower() for phrase in ["thinking process", "analyze", "reasoning", "here's a", "drafting"]):
        cleaned = cleaned[header_match.start():].strip()

    # 4. If the response still starts with "Analyze the Request", find where real answer begins
    if re.match(r'^\s*(?:\d+\.\s*)?\*{0,2}(?:analyze\s+(?:the\s+|user\s+)?request|thinking\s+process|internal\s+reasoning)\*{0,2}[:\s]', cleaned, re.IGNORECASE):
        ans_match = re.search(
            r'\n\s*(?:[-*•]\s*)?(?:#{1,4}\s+|\*{0,2})(?:final\s+)?(?:answer|response|revision sheet|topic explanation)(?::\*{0,2}|\*{0,2}:)?\s*', 
            cleaned, 
            re.IGNORECASE
        )
        if ans_match:
            cleaned = cleaned[ans_match.end():].strip()
        else:
            h_match = re.search(r'\n\s*#{1,4}\s+\S+', cleaned)
            if h_match:
                cleaned = cleaned[h_match.start():].strip()

    # 5. Strip any trailing "Review against constraints" block
    cleaned = re.sub(r'\n\s*(?:\d+\.\s*)?\*{0,2}(?:Review against constraints|Checking against constraints|Constraint review)[\s\S]*$', '', cleaned, flags=re.IGNORECASE).strip()

    # 6. Ensure mandatory verification footnote is present
    if VERIFICATION_LINE.lower() not in cleaned.lower():
        cleaned = f"{cleaned.rstrip()}\n\n{VERIFICATION_LINE}"

    return cleaned


def call_subject_llm(
    system_prompt: str, 
    user_prompt: str, 
    client: Any = None, 
    model_name: Optional[str] = None,
    max_tokens: int = 3500
) -> str:
    """
    Invokes the LLM using the same model setting and timeout rules as the main chat
    (25s timeout, max 1 retry). Cleans reasoning scratchpads and falls back to mock educational answer if offline.
    """
    model_to_use = (
        model_name 
        or os.getenv("LLM_MODEL") 
        or getattr(config, "LLM_MODEL", None) 
        or getattr(config, "OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
    )
    is_mcq = "multiple choice" in user_prompt.lower() or "format each question strictly in json" in user_prompt.lower()

    if client is not None:
        try:
            # OpenRouter (OpenAI-compatible client)
            if hasattr(client, "chat") and hasattr(client.chat, "completions"):
                kwargs = {
                    "model": model_to_use,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.6 if is_mcq else 0.2,
                    "timeout": 30.0 if is_mcq else 25.0,
                    "max_tokens": max_tokens
                }
                # For OpenRouter, request no reasoning or minimum reasoning
                is_openrouter = "openrouter" in str(getattr(client, "base_url", "")).lower() or getattr(config, "LLM_PROVIDER", "") == "openrouter"
                if is_openrouter:
                    kwargs["extra_body"] = {"reasoning": {"max_tokens": 0}}

                last_err = None
                for attempt in range(2):  # timeout, max 1 retry
                    try:
                        response = client.chat.completions.create(**kwargs)
                        msg = response.choices[0].message
                        text = (msg.content or "").strip()
                        # If msg.content is empty, DO NOT fall back to raw reasoning if expecting MCQs
                        if not text and getattr(msg, "reasoning", None):
                            r_text = str(msg.reasoning).strip()
                            if "```json" in r_text or (not is_mcq and len(r_text) > 100):
                                text = r_text
                        if text:
                            cleaned = clean_subject_response(text)
                            # If MCQ was requested, make sure we got valid JSON, else fallback
                            if is_mcq:
                                if extract_mcq_json(cleaned):
                                    return cleaned
                            else:
                                return cleaned
                    except Exception as req_err:
                        last_err = req_err
                        if "extra_body" in kwargs:
                            kwargs.pop("extra_body", None)
                        time.sleep(0.5)
                if last_err:
                    print(f"[SubjectAssistant] OpenAI/OpenRouter call failed after retry: {last_err}")

            # Google GenAI client
            elif hasattr(client, "models") and hasattr(client.models, "generate_content"):
                from google.genai import types
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                response = client.models.generate_content(
                    model=model_to_use,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.6 if is_mcq else 0.2, 
                        max_output_tokens=max_tokens
                    )
                )
                text = (response.text or "").strip()
                if text:
                    cleaned = clean_subject_response(text)
                    if is_mcq:
                        if extract_mcq_json(cleaned):
                            return cleaned
                    else:
                        return cleaned
        except Exception as e:
            print(f"[SubjectAssistant] LLM call failed: {e}. Using educational fallback.")

    # Educational fallback for test environments and offline usage
    return generate_offline_fallback(user_prompt)


def generate_offline_fallback(user_prompt: str) -> str:
    """Provides a valid, structured educational fallback response when LLM is unavailable."""
    prompt_lower = (user_prompt or "").lower()

    # 1. Practice questions JSON (Multiple Choice)
    if "format each question strictly in json" in prompt_lower or ("requested question count:" in prompt_lower and "multiple choice" in prompt_lower) or "multiple choice" in prompt_lower:
        subj_m = re.search(r'Subject:\s*([^\n]+)', user_prompt, re.IGNORECASE)
        unit_m = re.search(r'Unit:\s*([^\n]+)', user_prompt, re.IGNORECASE)
        topics_m = re.search(r'Topics covered:\s*([^\n]+)', user_prompt, re.IGNORECASE)
        count_m = re.search(r'Requested Question Count:\s*(\d+)', user_prompt, re.IGNORECASE)
        seed_m = re.search(r'Variation/Seed:\s*(\d+)', user_prompt, re.IGNORECASE)

        subj = subj_m.group(1).strip() if subj_m else ""
        unit = unit_m.group(1).strip() if unit_m else ""
        topics = topics_m.group(1).strip() if topics_m else ""
        cnt = int(count_m.group(1)) if count_m else 5
        seed_val = int(seed_m.group(1)) if seed_m else None

        mcq_list = generate_subject_mcqs(subj, unit, topics, cnt, seed=seed_val)
        return f"```json\n{json.dumps(mcq_list, indent=2)}\n```\n\n{VERIFICATION_LINE}"

    # 1b. Practice questions (Short Answer)
    if "short answer" in prompt_lower or ("requested question count:" in prompt_lower and "multiple choice" not in prompt_lower):
        subj_m = re.search(r'Subject:\s*([^\n]+)', user_prompt, re.IGNORECASE)
        unit_m = re.search(r'Unit:\s*([^\n]+)', user_prompt, re.IGNORECASE)
        topics_m = re.search(r'Topics covered:\s*([^\n]+)', user_prompt, re.IGNORECASE)
        count_m = re.search(r'Requested Question Count:\s*(\d+)', user_prompt, re.IGNORECASE)
        seed_m = re.search(r'Variation/Seed:\s*(\d+)', user_prompt, re.IGNORECASE)

        subj = subj_m.group(1).strip() if subj_m else ""
        unit = unit_m.group(1).strip() if unit_m else ""
        topics = topics_m.group(1).strip() if topics_m else ""
        cnt = int(count_m.group(1)) if count_m else 5
        seed_val = int(seed_m.group(1)) if seed_m else None

        return generate_subject_short_answers(subj, unit, topics, cnt, seed=seed_val)

    # 2. Quick Revision Sheet Fallback (Exact 4 Sections)
    if "quick revision sheet" in prompt_lower or "revision summary" in prompt_lower:
        # Check if Computer Science / Data Structures
        if any(k in prompt_lower for k in ["data structure", "algorithm", "ads", "hash", "tree", "linear", "queue", "stack"]):
            return (
                "### 1. Key Points\n"
                "- **Abstract Data Types (ADTs)** specify operations independently of implementation details.\n"
                "- **Trees & Balanced BSTs**: AVL and Red-Black trees maintain $O(\\log n)$ height by rebalancing via rotations.\n"
                "- **Hashing**: Maps large keys to fixed array indices in expected $O(1)$ time; collisions are resolved by chaining or open addressing.\n"
                "- **Priority Queues (Heaps)**: Complete binary trees satisfying heap order; insertion and extract-min operate in $O(\\log n)$ time.\n\n"
                "### 2. Formulas & Governing Equations\n"
                "- **Hash Load Factor**: $\\alpha = \\frac{n}{m}$, where $n$ is total inserted keys and $m$ is table slots ($[\\alpha] = \\text{dimensionless}$).\n"
                "- **Linear Probing Sequence**: $h(k, i) = (h'(k) + i) \\bmod m$, for probe step $i = 0, 1, \\dots, m-1$.\n"
                "- **Double Hashing Sequence**: $h(k, i) = (h_1(k) + i \\cdot h_2(k)) \\bmod m$, where $\\gcd(h_2(k), m) = 1$.\n"
                "- **AVL Balance Factor**: $\\text{BF}(u) = \\text{height}(\\text{left}(u)) - \\text{height}(\\text{right}(u)) \\in \\{-1, 0, +1\\}$.\n\n"
                "### 3. Essential Definitions\n"
                "- **Collision**: An event where two distinct keys $k_1 \\neq k_2$ evaluate to the same table index $h(k_1) = h(k_2)$.\n"
                "- **Separate Chaining**: Collision resolution strategy where each table slot points to an external linked list of elements.\n"
                "- **Open Addressing**: Technique where colliding items are placed in alternate vacant slots within the primary array.\n"
                "- **Rehashing**: Dynamic resizing that doubles table capacity and re-inserts entries when load factor exceeds threshold.\n\n"
                "### 4. 5-Line Recap\n"
                "1. Efficient data structures balance access speed, dynamic mutability, and memory overhead.\n"
                "2. AVL and balanced search trees guarantee $O(\\log n)$ worst-case search, insertion, and deletion.\n"
                "3. Hash tables provide $O(1)$ average-case dictionary operations under uniform key distribution.\n"
                "4. Closed hashing requires load factor $\\alpha < 0.75$ and tombstones for correct element deletion.\n"
                "5. Always select data structures matching the dominant operation profile of your engineering application.\n\n"
                f"{VERIFICATION_LINE}"
            )
        # Check if Database Systems / DBMS
        elif any(k in prompt_lower for k in ["database", "dbms", "sql", "transaction", "relation"]):
            return (
                "### 1. Key Points\n"
                "- **Relational Model**: Data organized into tables with schema constraints and integrity rules.\n"
                "- **Normalization**: Decomposing anomalous relations into 1NF, 2NF, 3NF, and BCNF.\n"
                "- **Indexing**: B+ Trees organize disk pages to minimize block I/O lookups to $O(\\log_B N)$.\n"
                "- **ACID Guarantees**: Atomicity, Consistency, Isolation, and Durability govern reliable transactions.\n\n"
                "### 2. Formulas & Governing Equations\n"
                "- **B+ Tree Fanout / Order**: Order $m$ implies each internal node holds $\\lceil m/2 \\rceil \\le k \\le m$ children.\n"
                "- **Functional Dependency Closure**: $X^+ = \\{A \\mid X \\rightarrow A \\text{ is implied by Armstrong's axioms}\\}$.\n\n"
                "### 3. Essential Definitions\n"
                "- **Candidate Key**: A minimal superkey that uniquely identifies each tuple in a relation.\n"
                "- **Third Normal Form (3NF)**: Relation in 2NF where every non-prime attribute is non-transitively dependent on candidate keys.\n"
                "- **Serializability**: Equivalence of concurrent transaction schedules to some sequential execution order.\n\n"
                "### 4. 5-Line Recap\n"
                "1. Database models separate physical storage representations from logical queries.\n"
                "2. Relational algebra operations form the mathematical foundation of SQL queries.\n"
                "3. Normalization eliminates data redundancy and update anomalies.\n"
                "4. B+ tree indices optimize range queries and disk block accesses.\n"
                "5. Concurrency control uses locking and timestamps to ensure serializability.\n\n"
                f"{VERIFICATION_LINE}"
            )

    # 3. Topic Explanation Fallback (5 Sections)
    # Check if Computer Science / Data Structures
    if any(k in prompt_lower for k in ["data structure", "algorithm", "ads", "hash", "tree", "linear", "queue", "stack", "sort"]):
        return (
            "### 1. Short Intro\n"
            "This concept is a foundational algorithmic structure in Computer Science, designed to store, organize, and retrieve data with optimal computational time and space complexity.\n\n"
            "### 2. Step-by-Step Explanation\n"
            "1. **Define the Structure**: Represent elements with precise data properties and connectivity (pointers, indices, or continuous memory).\n"
            "2. **Identify Invariants**: Maintain structural invariants (e.g., heap order, binary search property, or balanced height).\n"
            "3. **Execute Core Operations**: Implement search, insertion, and deletion by traversing or adjusting references.\n"
            "4. **Analyze Complexity**: Compute best, average, and worst-case runtimes using Big-O asymptotic notation.\n\n"
            "### 3. Key Formulas\n"
            "- **Load Factor**: $\\alpha = \\frac{n}{m}$, where $n = \\text{elements}$, $m = \\text{table capacity}$ ($[\\alpha] = \\text{dimensionless}$).\n"
            "- **Linear Probing**: $h(k, i) = (h'(k) + i) \\bmod m$, for step $i = 0, 1, 2, \\dots$.\n"
            "- **Time Complexity**: Average search time $T(n) = \\mathcal{O}(1 + \\alpha)$ operations.\n\n"
            "### 4. Worked Example\n"
            "- **Given**: Table size $m = 7$, primary hash function $h(k) = k \\bmod 7$. Insert keys: $k_1 = 15, k_2 = 22$.\n"
            "- **Formula**: $h(k) = k \\bmod 7$. If occupied, probe index $h'(k, i) = (h(k) + i) \\bmod 7$.\n"
            "- **Step-by-Step Substitution**:\n"
            "  1. Insert $k_1 = 15$: $h(15) = 15 \\bmod 7 = 1$. Slot 1 is empty $\\rightarrow$ Store 15 at index 1.\n"
            "  2. Insert $k_2 = 22$: $h(22) = 22 \\bmod 7 = 1$. Slot 1 is occupied (Collision!).\n"
            "  3. Probe with $i=1$: $(1 + 1) \\bmod 7 = 2$. Slot 2 is empty $\\rightarrow$ Store 22 at index 2.\n"
            "- **Final Result**: Hash table mappings: $\\text{Slot}[1] = 15$, $\\text{Slot}[2] = 22$.\n\n"
            "### 5. 3 Common Mistakes\n"
            "1. Forgetting to modulo by table size $m$ when computing hash indices or probing steps.\n"
            "2. Not marking deleted slots with a tombstone marker in open addressing, breaking subsequent search chains.\n"
            "3. Allowing load factor $\\alpha > 0.75$ in open addressing before triggering table expansion.\n\n"
            f"{VERIFICATION_LINE}"
        )

    # 4. Default Fallback for General / Electrical Engineering
    return (
        "### 1. Short Intro\n"
        "This concept forms a core building block in the engineering curriculum, providing analytical models and governing frameworks.\n\n"
        "### 2. Step-by-Step Explanation\n"
        "1. Identify the input parameters, boundary constraints, and governing conditions.\n"
        "2. Formulate the relationship using standard engineering principles.\n"
        "3. Apply mathematical transformations to isolate the target variable.\n"
        "4. Validate dimensional consistency and stability.\n\n"
        "### 3. Key Formulas\n"
        "- Governing Equation: $V(t) = L \\frac{di(t)}{dt} + R i(t)$ with $[V] = \\text{Volts}$.\n"
        "- Efficiency: $\\eta = \\frac{P_{\\text{out}}}{P_{\\text{in}}} \\times 100\\%$.\n\n"
        "### 4. Worked Example\n"
        "- **Given**: Input power $P_{\\text{in}} = 5000\\text{ W}$, Losses $P_{\\text{loss}} = 500\\text{ W}$.\n"
        "- **Formula**: $P_{\\text{out}} = P_{\\text{in}} - P_{\\text{loss}}$ and $\\eta = \\frac{P_{\\text{out}}}{P_{\\text{in}}} \\times 100\\%$.\n"
        "- **Substitution**: $P_{\\text{out}} = 5000 - 500 = 4500\\text{ W}$. $\\eta = \\frac{4500}{5000} \\times 100\\%$.\n"
        "- **Final Result**: $\\eta = 90\\%$.\n\n"
        "### 5. 3 Common Mistakes\n"
        "1. Forgetting to convert units to SI base units before substitution.\n"
        "2. Misinterpreting initial state conditions in transient or dynamic analysis.\n"
        "3. Omitting the units in intermediate and final numerical results.\n\n"
        f"{VERIFICATION_LINE}"
    )


def answer_subject_doubt(
    query: str, 
    subject_name: str, 
    units_data: Optional[List[Dict[str, Any]]] = None, 
    history: Optional[List[Dict[str, str]]] = None, 
    client: Any = None, 
    model_name: Optional[str] = None,
    db: Any = None,
    branch: str = "",
    scheme: str = ""
) -> str:
    """
    Processes a student doubt with full guardrails:
    - College administrative fact queries redirected to Ask AI page.
    - Outside-subject queries answered with an explicit one-line scope notice.
    - Answers cached in answer_cache.
    - Always ends with VERIFICATION_LINE.
    """
    clean_q = (query or "").strip()
    if not clean_q:
        return "Please ask a question about your subject."

    # 1. College Fact Redirect
    if is_college_fact_query(clean_q):
        return f"{COLLEGE_FACT_REDIRECT}\n\n{VERIFICATION_LINE}"

    # 2. Check Answer Cache if db is provided
    cache_key = get_subject_cache_key(subject_name, "doubt", clean_q, "doubt", branch=branch, scheme=scheme)
    if db is not None:
        cached = db.get_cached_answer(cache_key)
        if cached and cached.get("answer"):
            return cached["answer"]

    # 3. Check Outside-Subject heuristic
    outside_subject = is_outside_subject(clean_q, subject_name, units_data)

    # 4. Build prompt & call LLM
    sys_p, usr_p = build_doubt_prompt(subject_name, units_data, clean_q, history=history)
    raw_answer = call_subject_llm(sys_p, usr_p, client=client, model_name=model_name)

    # 5. Ensure Outside-Subject line is included if detected
    final_answer = raw_answer
    outside_line = f"Note: This topic appears to be outside the selected subject ({subject_name}) syllabus."
    if outside_subject and outside_line.lower() not in final_answer.lower() and "outside the selected subject" not in final_answer.lower():
        final_answer = f"*{outside_line}*\n\n{final_answer}"

    # 6. Ensure Verification Line is present at the end
    if VERIFICATION_LINE.lower() not in final_answer.lower():
        final_answer = f"{final_answer.rstrip()}\n\n{VERIFICATION_LINE}"

    # 7. Store in Cache
    if db is not None:
        db.set_cached_answer(cache_key, {
            "answer": final_answer,
            "response_type": "ANSWERED",
            "subject": subject_name
        })

    return final_answer
