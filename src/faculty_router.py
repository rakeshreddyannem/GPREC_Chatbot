import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from src.database import DatabaseManager
from src.reliability import ResponseType
from src.faculty_parser import DEPARTMENT_CONFIGS


# Alias mappings to canonical department names
DEPT_MAP = {
    "ce": "Civil Engineering",
    "civil": "Civil Engineering",
    "civil engineering": "Civil Engineering",
    
    "cse": "Computer Science and Engineering",
    "computer science": "Computer Science and Engineering",
    "computer science and engineering": "Computer Science and Engineering",
    "cs": "Computer Science and Engineering",
    
    "eee": "Electrical and Electronics Engineering",
    "electrical": "Electrical and Electronics Engineering",
    "electrical engineering": "Electrical and Electronics Engineering",
    "electrical and electronics engineering": "Electrical and Electronics Engineering",
    "electrical and electronics": "Electrical and Electronics Engineering",
    
    "ece": "Electronics and Communication Engineering",
    "electronics": "Electronics and Communication Engineering",
    "electronics and communication": "Electronics and Communication Engineering",
    "electronics and communication engineering": "Electronics and Communication Engineering",
    
    "me": "Mechanical Engineering",
    "mech": "Mechanical Engineering",
    "mechanical": "Mechanical Engineering",
    "mechanical engineering": "Mechanical Engineering",
    
    "h&s": "Humanities and Basic Sciences",
    "hs": "Humanities and Basic Sciences",
    "humanities": "Humanities and Basic Sciences",
    "basic sciences": "Humanities and Basic Sciences",
    "humanities and basic sciences": "Humanities and Basic Sciences",
    "humanities & basic sciences": "Humanities and Basic Sciences",
    "humanities and sciences": "Humanities and Basic Sciences",
    "bs": "Humanities and Basic Sciences",
    
    "csm": "CSE - Artificial Intelligence & Machine Learning",
    "ai ml": "CSE - Artificial Intelligence & Machine Learning",
    "aiml": "CSE - Artificial Intelligence & Machine Learning",
    "ai": "CSE - Artificial Intelligence & Machine Learning",
    "cse ai": "CSE - Artificial Intelligence & Machine Learning",
    "cse aiml": "CSE - Artificial Intelligence & Machine Learning",
    "artificial intelligence": "CSE - Artificial Intelligence & Machine Learning",
    
    "csd": "CSE - Data Science",
    "cse ds": "CSE - Data Science",
    "cse data science": "CSE - Data Science",
    "data science": "CSE - Data Science",
    "ds": "CSE - Data Science",
    
    "csb": "Computer Science and Business Systems",
    "business systems": "Computer Science and Business Systems",
    "computer science and business systems": "Computer Science and Business Systems",
    
    "cst": "Computer Science and Technology",
    "computer science and technology": "Computer Science and Technology"
}

KNOWN_DEPT_CODES = "CE, CSE, EEE, ECE, ME, H&S, CSM, CSD, CSB, CST"


def resolve_department(text: str) -> Optional[str]:
    """Resolve department from query text. Returns canonical department name or None."""
    t_lower = text.lower()
    
    # Sort aliases by descending length so "computer science and engineering" matches before "cse"
    sorted_aliases = sorted(DEPT_MAP.keys(), key=lambda x: len(x), reverse=True)
    for alias in sorted_aliases:
        # Match as discrete word/phrase
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, t_lower):
            # Special check for "me": ensure it's not the common English pronoun "me"
            if alias == "me":
                if re.search(r'\b(?:show|tell|give|help|let|send|ask|teach|guide|for|to)\s+me\b', t_lower):
                    continue
                if re.search(r'\bme\s+(?:dr|prof|who|what|about|photo|photos|picture|how)\b', t_lower):
                    continue
            return DEPT_MAP[alias]
    return None


def is_faculty_query(query: str, db: DatabaseManager) -> bool:
    """Determine if query is asking about faculty, HODs, professors, or faculty counts/lists."""
    q_lower = query.lower()
    
    # 1. Direct faculty keywords
    faculty_keywords = [
        "faculty", "prof", "professor", "professors", "hod", "head of department",
        "head of the department", "department head", "dept head", "teacher", "teachers",
        "lecturer", "lecturers", "staff list", "faculty list", "faculty count", "phd faculty",
        "adjunct faculty", "guest faculty", "visiting faculty", "photo", "picture", "image", "profile"
    ]
    if any(re.search(r'\b' + re.escape(k) + r'\b', q_lower) for k in faculty_keywords):
        return True
        
    # 2. Academic / professional titles (including fused titles like Drkishore)
    if re.search(r'\b(dr\.?|prof\.?|sri\.?|smt\.?)\b', q_lower) or re.search(r'\b(dr|prof|sri|smt)[a-z]{3,}\b', q_lower):
        return True

    # 3. Person inquiry patterns like "who is <name>" or "tell me about <name>"
    m = re.match(r'^(?:who is|tell me about|info (?:about|regarding|on)|details (?:of|about)|profile of|photo of|image of|show me)\s+(.+)$', q_lower)
    if m:
        target = m.group(1).strip()
        general_topics = [
            "admission", "hostel", "fee", "fees", "syllabus", "exam", "result", "results",
            "placement", "placements", "library", "college", "gprec", "bus", "transport",
            "canteen", "sports", "timings", "attendance", "scholarship", "regulation", "regulations"
        ]
        if not any(re.search(r'\b' + re.escape(t) + r'\b', target) for t in general_topics):
            return True

    # 4. Direct faculty name lookup (e.g. user inputs "Kishore" or "Kasiviswanath")
    words = q_lower.split()
    if 1 <= len(words) <= 3 and len(q_lower) >= 4:
        if db.get_faculty_by_name(query):
            return True

    return False


def handle_faculty_query(query: str, db: DatabaseManager) -> Optional[Dict[str, Any]]:
    """
    Process faculty queries using pure deterministic Python logic and database lookups.
    Returns response dict or None if not a faculty query.
    """
    if not is_faculty_query(query, db):
        return None

    q_lower = query.lower()
    dept = resolve_department(query)

    # 1. HOD Query
    is_hod_q = bool(re.search(r'\b(hod|head of the department|head of department|department head)\b', q_lower))
    
    if is_hod_q:
        if not dept:
            # Check if user mentioned an unknown department (e.g. "who is the hod of an unknown department" or "who is the hod of robotics")
            m_dept = re.search(r'\b(?:of|in|for)\s+(?:an?\s+|the\s+)?([a-zA-Z\s&-]+?)(?:\s+department)?$', query, re.IGNORECASE)
            if m_dept:
                unknown_candidate = m_dept.group(1).strip()
                unknown_candidate = re.sub(r'^(?:a|an|the)\s+', '', unknown_candidate, flags=re.IGNORECASE).strip()
                if unknown_candidate.lower() not in ("college", "gprec", "the college", "our college", "the department", ""):
                    return {
                        "response_type": ResponseType.NOT_FOUND,
                        "answer": f"GPREC does not have an '{unknown_candidate}' department. Available departments are: {KNOWN_DEPT_CODES}.",
                        "sources": [],
                        "confidence": "High",
                        "confidence_reason": "Department not found in GPREC Directory"
                    }

            # Ambiguous department - ask for clarification
            return {
                "response_type": ResponseType.CLARIFY,
                "answer": f"Which department's HOD are you looking for? ({KNOWN_DEPT_CODES})",
                "clarify_question": f"Which department's HOD are you looking for? ({KNOWN_DEPT_CODES})",
                "clarify_options": ["CE", "CSE", "EEE", "ECE", "ME", "H&S", "CSM", "CSD", "CSB", "CST"],
                "sources": [],
                "confidence": "High",
                "confidence_reason": "Department clarification needed for HOD query"
            }

        # Look up HOD for resolved department
        hod = db.get_hod(dept)
        if hod:
            name = hod["name"]
            desig = hod["designation"] or "Head of the Department"
            qual = f" ({hod['qualification']})" if hod.get("qualification") else ""
            email_part = f"\n* **Email:** {hod['email']}" if hod.get("email") else ""
            profile_part = f"\n* **Profile Document:** [View Official Profile PDF]({hod['profile_url']})" if hod.get("profile_url") else ""

            ans = (
                f"The Head of the Department (HOD) of **{dept}** is **{name}**, {desig}{qual}."
                f"{email_part}{profile_part}"
            )
            return {
                "response_type": ResponseType.ANSWERED,
                "answer": ans,
                "faculty_records": [hod],
                "is_particular_faculty": True,
                "sources": [{
                    "title": f"Faculty Directory: {name} (HOD, {dept})",
                    "source_url": hod.get("profile_url") or hod.get("source_url") or "https://www.gprec.ac.in",
                    "page": None,
                    "published_date": None
                }],
                "confidence": "High",
                "confidence_reason": f"Official GPREC Faculty Directory for {dept}"
            }
        else:
            return {
                "response_type": ResponseType.NOT_FOUND,
                "answer": f"I could not find an official HOD listing for the {dept} department.",
                "sources": [],
                "confidence": "High",
                "confidence_reason": f"No HOD record in database for {dept}"
            }

    # 2. Count Query (e.g. "how many faculty members in cse", "faculty count of mechanical")
    is_count_q = any(k in q_lower for k in [
        "how many faculty", "how many professors", "faculty count", "number of faculty",
        "count of faculty", "total faculty", "how many teachers", "number of teachers"
    ])
    if is_count_q:
        if not dept:
            return {
                "response_type": ResponseType.CLARIFY,
                "answer": f"Which department's faculty count are you looking for? ({KNOWN_DEPT_CODES})",
                "clarify_question": f"Which department's faculty count are you looking for? ({KNOWN_DEPT_CODES})",
                "clarify_options": ["CE", "CSE", "EEE", "ECE", "ME", "H&S", "CSM", "CSD", "CSB", "CST"],
                "sources": [],
                "confidence": "High",
                "confidence_reason": "Department clarification needed for faculty count"
            }

        faculty_list = db.get_faculty(department=dept, is_active=1)
        if faculty_list:
            regular_count = sum(1 for f in faculty_list if not f.get("is_guest"))
            guest_count = sum(1 for f in faculty_list if f.get("is_guest"))
            last_checked = faculty_list[0].get("last_checked") or "official college website"
            date_display = last_checked.split()[0] if " " in last_checked else last_checked

            guest_str = f" (and {guest_count} guest/adjunct members)" if guest_count > 0 else ""
            ans = f"The {dept} department has **{regular_count}** regular faculty members{guest_str}, as of {date_display}."

            return {
                "response_type": ResponseType.ANSWERED,
                "answer": ans,
                "sources": [{
                    "title": f"Faculty Directory: {dept} ({len(faculty_list)} members)",
                    "source_url": faculty_list[0].get("source_url") or "https://www.gprec.ac.in",
                    "page": None,
                    "published_date": None
                }],
                "confidence": "High",
                "confidence_reason": f"Official GPREC Faculty Directory for {dept}"
            }
        else:
            return {
                "response_type": ResponseType.NOT_FOUND,
                "answer": f"No faculty records were found for the {dept} department.",
                "sources": [],
                "confidence": "High",
                "confidence_reason": f"No faculty records in database for {dept}"
            }

    # 3. List Query (e.g. "list civil engineering faculty", "faculty of mechanical")
    is_list_q = any(k in q_lower for k in [
        "list", "who are the faculty", "faculty members", "all faculty", "faculty list",
        "professors of", "professors in", "teachers in", "staff of"
    ]) or (
        dept and any(k in q_lower for k in ["faculty", "professors", "teachers", "staff"]) and not any(k in q_lower for k in ["who is", "profile of", "tell me about"])
    )

    if is_list_q:
        if not dept:
            # Check if asking about an unknown department
            m_dept = re.search(r'\b(?:of|in|for)\s+([a-zA-Z\s&-]+?)(?:\s+faculty)?$', query, re.IGNORECASE)
            if m_dept:
                unknown_candidate = m_dept.group(1).strip()
                if unknown_candidate.lower() not in ("college", "gprec", "the college"):
                    return {
                        "response_type": ResponseType.NOT_FOUND,
                        "answer": f"GPREC does not have an '{unknown_candidate}' department. Available departments are: {KNOWN_DEPT_CODES}.",
                        "sources": [],
                        "confidence": "High",
                        "confidence_reason": "Department not found in GPREC Directory"
                    }

            return {
                "response_type": ResponseType.CLARIFY,
                "answer": f"Which department's faculty list are you looking for? ({KNOWN_DEPT_CODES})",
                "clarify_question": f"Which department's faculty list are you looking for? ({KNOWN_DEPT_CODES})",
                "clarify_options": ["CE", "CSE", "EEE", "ECE", "ME", "H&S", "CSM", "CSD", "CSB", "CST"],
                "sources": [],
                "confidence": "High",
                "confidence_reason": "Department clarification needed for faculty list"
            }

        faculty_list = db.get_faculty(department=dept, is_active=1)
        if faculty_list:
            # Group by designation hierarchy
            professors = []
            assoc_profs = []
            asst_profs = []
            guest_faculty = []
            others = []

            for f in faculty_list:
                d_str = (f.get("designation") or "").lower()
                if f.get("is_guest"):
                    guest_faculty.append(f)
                elif "assistant professor" in d_str or "asst" in d_str:
                    asst_profs.append(f)
                elif "associate professor" in d_str or "assoc" in d_str:
                    assoc_profs.append(f)
                elif "professor" in d_str:
                    professors.append(f)
                else:
                    others.append(f)

            lines = [f"Faculty members of the Department of **{dept}**:\n"]

            def format_group(group_title: str, members: List[Dict[str, Any]]):
                if not members:
                    return
                lines.append(f"### {group_title} ({len(members)})")
                for m in members:
                    qual_str = f" – {m['qualification']}" if m.get("qualification") else ""
                    hod_badge = " **[HOD]**" if m.get("is_hod") else ""
                    link_str = f" | [Profile PDF]({m['profile_url']})" if m.get("profile_url") else ""
                    lines.append(f"* **{m['name']}**{hod_badge}{qual_str}{link_str}")
                lines.append("")

            format_group("Professors", professors)
            format_group("Associate Professors", assoc_profs)
            format_group("Assistant Professors", asst_profs)
            format_group("Guest / Adjunct Faculty", guest_faculty)
            format_group("Other Faculty", others)

            return {
                "response_type": ResponseType.ANSWERED,
                "answer": "\n".join(lines).strip(),
                "sources": [{
                    "title": f"Faculty Directory: {dept} ({len(faculty_list)} members)",
                    "source_url": faculty_list[0].get("source_url") or "https://www.gprec.ac.in",
                    "page": None,
                    "published_date": None
                }],
                "confidence": "High",
                "confidence_reason": f"Official GPREC Faculty Directory for {dept}"
            }

    # 4. Single Person Query
    # Extract person name candidate from query
    search_target = query

    # Separate fused honorifics like "Drkishore" or "ProfSuresh"
    search_target = re.sub(r'\b(dr|prof|sri|smt|mr|mrs|ms)([a-z]{3,})\b', r'\1 \2', search_target, flags=re.IGNORECASE)
    # Strip possessive 's or '
    search_target = re.sub(r"['’]s\b", '', search_target)

    # Iteratively strip trigger phrases and leading prepositions/articles
    prev = ""
    while prev != search_target:
        prev = search_target
        search_target = re.sub(
            r'^(?:can you\s+|please\s+|tell me\s+|give me\s+|show me\s+|find\s+|get\s+|who is\s+|what is\s+|info (?:about|regarding|on)\s+|profile of\s+|details of\s+|photo of\s+|image of\s+|about\s+|the\s+|of\s+|a\s+|an\s+)+',
            '', search_target, flags=re.IGNORECASE
        ).strip()

    # Strip keywords
    search_target = re.sub(r'\b(photos?|pictures?|images?|details|profiles?|info|faculty|teacher|sir|madam)\b', '', search_target, flags=re.IGNORECASE).strip()
    search_target = re.sub(r'^(?:the|of|a|an|for|in|about)\s+', '', search_target, flags=re.IGNORECASE).strip()
    search_target = re.sub(r'\s+(?:the|of|a|an|for|in|about)$', '', search_target, flags=re.IGNORECASE).strip()

    # Strip department mentions if any
    if dept:
        for k in DEPT_MAP.keys():
            search_target = re.sub(r'\b' + re.escape(k) + r'\b', '', search_target, flags=re.IGNORECASE)
        search_target = re.sub(r'\b(department|dept|in|of|from)\b', '', search_target, flags=re.IGNORECASE).strip()

    # Clean titles, punctuation and extra spaces
    search_target = re.sub(r'^\s*(?:dr|prof|professor|sri|smt|mr|mrs|ms)\.?\s*', '', search_target, flags=re.IGNORECASE).strip()
    search_target = re.sub(r'[^a-zA-Z0-9\s]', ' ', search_target).strip()
    search_target = re.sub(r'\s+', ' ', search_target)

    STOP_WORDS = {
        "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by",
        "about", "what", "who", "where", "when", "how", "is", "are", "was", "were",
        "can", "could", "will", "would", "should", "me", "my", "your", "his", "her",
        "their", "our", "us", "him", "them", "this", "that", "these", "those",
        "profile", "profiles", "detail", "details", "photo", "photos", "image", "images",
        "faculty", "department", "dept", "college", "gprec", "kurnool", "engineering",
        "analyze", "request", "previous", "question", "answer", "summary", "note", "likely",
        "typo", "show", "tell", "give", "please", "sir", "madam"
    }

    if search_target and len(search_target) >= 3 and search_target.lower() not in STOP_WORDS:
        matches = db.get_faculty_by_name(search_target, department=dept)
        
        # If no direct match, check without department filter
        if not matches and dept:
            matches = db.get_faculty_by_name(search_target)

        # Also try partial word matching if still empty
        if not matches:
            words = [w for w in search_target.split() if len(w) >= 4 and w.lower() not in STOP_WORDS]
            for w in words:
                m_sub = db.get_faculty_by_name(w, department=dept)
                if not m_sub and dept:
                    m_sub = db.get_faculty_by_name(w)
                if m_sub:
                    matches = m_sub
                    break

        if matches:
            # If multiple matches across DIFFERENT departments, show both!
            if len(matches) > 1 and len(set(m["department"] for m in matches)) > 1:
                lines = [f"I found {len(matches)} faculty members matching **{search_target}** across different departments:\n"]
                for i, m in enumerate(matches, 1):
                    qual_str = f", {m['qualification']}" if m.get("qualification") else ""
                    email_str = f" (Email: {m['email']})" if m.get("email") else ""
                    link_str = f" [Profile PDF]({m['profile_url']})" if m.get("profile_url") else ""
                    lines.append(f"{i}. **{m['name']}** – **{m.get('designation', 'Faculty')}** in the Department of **{m['department']}**{qual_str}.{email_str}{link_str}")

                return {
                    "response_type": ResponseType.ANSWERED,
                    "answer": "\n\n".join(lines),
                    "faculty_records": matches,
                    "is_particular_faculty": True,
                    "sources": [{
                        "title": f"Faculty Directory: {m['name']} ({m['department']})",
                        "source_url": m.get("profile_url") or m.get("source_url") or "https://www.gprec.ac.in",
                        "page": None,
                        "published_date": None
                    } for m in matches],
                    "confidence": "High",
                    "confidence_reason": f"Multiple matching faculty members across departments"
                }

            # Single match (or same person/department)
            person = matches[0]
            name = person["name"]
            desig = person["designation"] or "Faculty Member"
            p_dept = person["department"]
            qual = f", holding **{person['qualification']}**" if person.get("qualification") else ""
            email_part = f"\n* **Email:** {person['email']}" if person.get("email") else ""
            profile_part = f"\n* **Profile Document:** [View Official Profile PDF]({person['profile_url']})" if person.get("profile_url") else ""

            ans = (
                f"**{name}** is a **{desig}** in the Department of **{p_dept}**{qual}."
                f"{email_part}{profile_part}"
            )

            return {
                "response_type": ResponseType.ANSWERED,
                "answer": ans,
                "faculty_records": [person],
                "is_particular_faculty": True,
                "sources": [{
                    "title": f"Faculty Directory: {name} ({p_dept})",
                    "source_url": person.get("profile_url") or person.get("source_url") or "https://www.gprec.ac.in",
                    "page": None,
                    "published_date": None
                }],
                "confidence": "High",
                "confidence_reason": f"Official GPREC Faculty Directory for {p_dept}"
            }
        else:
            # No match found
            return {
                "response_type": ResponseType.NOT_FOUND,
                "answer": f"I could not find a faculty member named '{search_target}' in the GPREC directory.",
                "sources": [],
                "confidence": "High",
                "confidence_reason": "No faculty record found in directory"
            }

    return None
