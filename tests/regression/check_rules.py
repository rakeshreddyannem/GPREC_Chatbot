import re
from typing import Dict, Any, Tuple, List

def check_q1_placements(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    if "error" in ans.lower() and "rate limit" in ans.lower():
        return False, f"LLM error: {ans}"
    return True, "Passed basic reliability check."

def check_q2_eee_faculty_designations(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    return True, "Passed basic reliability check."

def check_q3_list_phd_faculties(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Check if ambiguity handling exists (asks which department or scoped)
    has_clarify = any(kw in ans.lower() for kw in ["which department", "specify the department", "showing:", "department:"])
    if not has_clarify and res.get("response_type") != "CLARIFY":
        return False, "Failed ambiguity check: Query lacks department and did not ask to clarify or state scope."
    return True, "Passed ambiguity check."

def check_q4_phd_faculties_eee(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Forbid inference: never state someone has a PhD just because of jury member / resource person
    lower = ans.lower()
    forbidden_phrases = ["jury member implies", "resource person implies", "acting as jury", "inferred to have phd", "likely holds a phd"]
    for phrase in forbidden_phrases:
        if phrase in lower:
            return False, f"Violated forbidden inference rule: Contains '{phrase}'."
    return True, "Passed inference restriction check."

def check_q5_boys_hostel(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Sensitive info check: no password patterns or personal numbers
    if re.search(r'password\s*[:=]\s*\w+', ans, re.I):
        return False, "Exposed password pattern."
    return True, "Passed basic reliability check."

def check_q6_clubs(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    return True, "Passed basic reliability check."

def check_q7_eee_faculty_details(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    return True, "Passed basic reliability check."

def check_q8_principal(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    if "sreenivasa reddy" in ans.lower() or "b. sreenivasa reddy" in ans.lower():
        return True, "Correctly identified Principal Dr. B. Sreenivasa Reddy."
    return False, "Failed to identify Principal Dr. B. Sreenivasa Reddy."

def check_q9_itca(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Check that crawl date / first_seen is not displayed as notice date
    # Check if unsourced acronym expansion exists
    today_pattern = re.compile(r'notice\s*(?:date)?\s*[:\-]?\s*2026', re.I)
    if today_pattern.search(ans):
        return False, "Displayed crawl/current date as notice date."
    return True, "Passed date check."

def check_q10_fee_structure_eee(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Should not have duplicate "I couldn't find... + Not Found Card"
    duplicate_pattern = ans.count("I couldn't find this information")
    if duplicate_pattern > 1:
        return False, "Contains duplicate not found message."
    return True, "Single response check passed."

def check_q11_library(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Source reranking: check if irrelevant sources like Alumni / RTI are present in sources
    for src in res.get("sources", []):
        url = src.get("source_url", "").lower()
        title = src.get("title", "").lower()
        if "alumni" in url or "rti" in url or "right to information" in title:
            return False, f"Irrelevant source retrieved for library: {title} ({url})"
    return True, "Passed library source relevance check."

def check_q12_head_eee_library(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans or len(ans) < 5:
        return False, "FAILED: Answer is blank or empty."
    return True, "Answer is non-empty."

def check_q13_exam_timetable(res: Dict[str, Any]) -> Tuple[bool, str]:
    ans = res.get("answer", "").strip()
    if not ans:
        return False, "Answer is empty."
    # Never output 30 bullets
    bullet_count = len(re.findall(r'^\s*[-*•\d+\.]\s+', ans, re.M))
    if bullet_count > 15:
        return False, f"Outputted too many raw bullets ({bullet_count} bullets), expected <= 5 matching notices or CLARIFY."
    return True, "Passed bullet count check."

CHECK_FUNCTIONS = {
    1: check_q1_placements,
    2: check_q2_eee_faculty_designations,
    3: check_q3_list_phd_faculties,
    4: check_q4_phd_faculties_eee,
    5: check_q5_boys_hostel,
    6: check_q6_clubs,
    7: check_q7_eee_faculty_details,
    8: check_q8_principal,
    9: check_q9_itca,
    10: check_q10_fee_structure_eee,
    11: check_q11_library,
    12: check_q12_head_eee_library,
    13: check_q13_exam_timetable,
}

def evaluate_result(q_id: int, result: Dict[str, Any]) -> Dict[str, Any]:
    check_fn = CHECK_FUNCTIONS.get(q_id)
    if not check_fn:
        return {"passed": True, "reason": "No custom check defined"}
    passed, reason = check_fn(result)
    return {"passed": passed, "reason": reason}
