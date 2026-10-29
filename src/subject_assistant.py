"""
Subject Assistance Module for GPREC AI Student Assistant.
Provides pure prompt builders, topic parsing, caching, and tutoring logic for B.Tech subjects.
"""

import os
import re
import time
import json
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


def build_practice_prompt(
    subject_name: str, 
    unit_title: str, 
    num_questions: int, 
    question_type: str, 
    unit_topics: Optional[str] = None
) -> Tuple[str, str]:
    """
    Builds prompt for AI-generated practice questions (3 to 10 questions).
    Type: "Multiple Choice" or "Short Answer".
    Labeled: "AI-generated practice questions, not from previous exam papers".
    """
    count = max(3, min(10, int(num_questions)))
    q_type_lower = (question_type or "multiple choice").lower()
    is_mcq = "choice" in q_type_lower

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

    if is_mcq:
        format_instructions = """
Format each question strictly in JSON within a ```json code block so the application can render them interactively:
[
  {
    "question_number": 1,
    "question": "Question text with LaTeX $...$",
    "options": {
      "A": "Option A text",
      "B": "Option B text",
      "C": "Option C text",
      "D": "Option D text"
    },
    "correct_option": "A",
    "explanation": "Brief step-by-step explanation of why this option is correct."
  }
]
"""
    else:
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
    user_prompt = f"""Subject: {subject_name}
Unit: {unit_title}{topics_ctx}
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
    max_tokens: int = 1500
) -> str:
    """
    Invokes the LLM using the same model setting and timeout rules as the main chat
    (20s timeout, max 1 retry). Cleans reasoning scratchpads and falls back to mock educational answer if offline.
    """
    model_to_use = (
        model_name 
        or os.getenv("LLM_MODEL") 
        or getattr(config, "LLM_MODEL", None) 
        or getattr(config, "OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
    )

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
                    "temperature": 0.2,
                    "timeout": 20.0,
                    "max_tokens": max_tokens
                }
                # For OpenRouter, disable the internal reasoning scratchpad so tokens/time aren't wasted
                is_openrouter = "openrouter" in str(getattr(client, "base_url", "")).lower() or getattr(config, "LLM_PROVIDER", "") == "openrouter"
                if is_openrouter:
                    kwargs["extra_body"] = {"reasoning": {"effort": "none"}}

                last_err = None
                for attempt in range(2):  # 20s timeout, max 1 retry
                    try:
                        response = client.chat.completions.create(**kwargs)
                        msg = response.choices[0].message
                        text = (msg.content or "").strip()
                        if not text and getattr(msg, "reasoning", None):
                            text = str(msg.reasoning).strip()
                        if text:
                            return clean_subject_response(text)
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
                        temperature=0.2, 
                        max_output_tokens=max_tokens
                    )
                )
                text = (response.text or "").strip()
                if text:
                    return clean_subject_response(text)
        except Exception as e:
            print(f"[SubjectAssistant] LLM call failed: {e}. Using educational fallback.")

    # Educational fallback for test environments and offline usage
    return generate_offline_fallback(user_prompt)


def generate_offline_fallback(user_prompt: str) -> str:
    """Provides a valid, structured educational fallback response when LLM is unavailable."""
    prompt_lower = (user_prompt or "").lower()

    # 1. Practice questions JSON (Multiple Choice)
    if "format each question strictly in json" in prompt_lower or ("requested question count:" in prompt_lower and "multiple choice" in prompt_lower):
        mock_mcq = [
            {
                "question_number": 1,
                "question": "What is the primary condition for an AVL tree to remain balanced?",
                "options": {
                    "A": "Balance factor of each node must be in $\\{-1, 0, +1\\}$",
                    "B": "Every node must have exactly two children",
                    "C": "Depth of all leaf nodes must be identical",
                    "D": "Root node key must be the median of all keys"
                },
                "correct_option": "A",
                "explanation": "In an AVL tree, the balance factor is defined as $\\text{height}(L) - \\text{height}(R)$, which must remain within $\\{-1, 0, 1\\}$."
            },
            {
                "question_number": 2,
                "question": "Which collision resolution technique stores all colliding keys in a linked list at the same hash index?",
                "options": {
                    "A": "Linear Probing",
                    "B": "Quadratic Probing",
                    "C": "Separate Chaining (Open Hashing)",
                    "D": "Double Hashing"
                },
                "correct_option": "C",
                "explanation": "Separate chaining maintains a linked list of elements at each bucket location in the hash table."
            },
            {
                "question_number": 3,
                "question": "What is the time complexity of deleting the minimum element from a Binary Min-Heap with $n$ elements?",
                "options": {
                    "A": "$\\mathcal{O}(1)$",
                    "B": "$\\mathcal{O}(\\log n)$",
                    "C": "$\\mathcal{O}(n)$",
                    "D": "$\\mathcal{O}(n \\log n)$"
                },
                "correct_option": "B",
                "explanation": "Extracting the root takes $\\mathcal{O}(1)$, but restoring heap order via sift-down takes $\\mathcal{O}(\\log n)$."
            }
        ]
        return f"```json\n{json.dumps(mock_mcq, indent=2)}\n```\n\n{VERIFICATION_LINE}"

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
