import re
from typing import List, Dict, Any, Optional

CURATED_OFFICIAL_LINKS: List[Dict[str, Any]] = [
    # 1. 2025 Placements Details
    {
        "id": "placements_2025_list",
        "title": "2024-25 Placement Selections & Offers (Company-wise List)",
        "url": "https://www.gprec.ac.in/placementdetails/2025-placements.pdf",
        "category": "placements",
        "year": "2025",
        "doc_type": "list"
    },
    # 2. 2025 Placement Summary
    {
        "id": "placements_2025_summary",
        "title": "2024-25 Placement Summary & Statistics",
        "url": "https://www.gprec.ac.in/placementdetails/2025%20-%20Summary.pdf",
        "category": "placements",
        "year": "2025",
        "doc_type": "summary"
    },
    # 3. 2024 Placements Details
    {
        "id": "placements_2024_list",
        "title": "2023-24 Placement Selections & Offers (Company-wise List)",
        "url": "https://www.gprec.ac.in/placementdetails/2024-placements.pdf",
        "category": "placements",
        "year": "2024",
        "doc_type": "list"
    },
    # 4. 2024 Placement Summary
    {
        "id": "placements_2024_summary",
        "title": "2023-24 Placement Summary & Statistics",
        "url": "https://www.gprec.ac.in/placementdetails/2024%20-%20Summary.pdf",
        "category": "placements",
        "year": "2024",
        "doc_type": "summary"
    },
    # 5. 2023 Placement Summary
    {
        "id": "placements_2023_summary",
        "title": "2022-23 Placement Summary & Statistics",
        "url": "https://www.gprec.ac.in/placementdetails/2023-Summary.pdf",
        "category": "placements",
        "year": "2023",
        "doc_type": "summary"
    },
    # 6. EAPCET Cut-off Ranks
    {
        "id": "eapcet_cutoff_2022",
        "title": "EAPCET 2022 Phase 1 Cut-off Ranks",
        "url": "https://www.gprec.ac.in/collegepdf/EAPCET-2022-PHASE-1-CUT-OFF-Ranks.pdf",
        "category": "admissions",
        "doc_type": "cutoff"
    },
    # 7. Academic Schedule 2026-2027
    {
        "id": "academic_schedule_2026_27",
        "title": "Academic Schedule 2026-2027",
        "url": "https://www.gprec.ac.in/academicplanner/ACADEMIC%20SCHEDULE-2026-2027.pdf",
        "category": "academics",
        "doc_type": "schedule"
    },
    # 8. B.Tech Scheme-2026 Regulations
    {
        "id": "scheme_2026_regulations",
        "title": "B.Tech Scheme-2026 Academic Regulations",
        "url": "https://www.gprec.ac.in/scheme-2026/B.Tech-Scheme-2026-Regulations.pdf",
        "category": "regulations",
        "doc_type": "regulations"
    },
    # 9. Civil Engineering Scheme-23 II, III & IV Year Syllabus
    {
        "id": "syllabus_ce_s23_ii_iii_iv",
        "title": "Civil Engineering Scheme-23 II, III & IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CE-S-23-II-III-IV-Year-Syllabus.pdf",
        "category": "syllabus",
        "branch": "CE",
        "years": ["2", "3", "4", "ii", "iii", "iv"]
    },
    # 10. EEE Scheme-23 III & IV Year Syllabus
    {
        "id": "syllabus_eee_s23_iii_iv",
        "title": "EEE Scheme-23 III & IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/EEE-S23-III-IV-Year-Syllabus.pdf",
        "category": "syllabus",
        "branch": "EEE",
        "years": ["3", "4", "iii", "iv"]
    },
    # 11. EEE Scheme-23 II Year Syllabus
    {
        "id": "syllabus_eee_s23_ii",
        "title": "EEE Scheme-23 II Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/EEE%20S-23%20II%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "EEE",
        "years": ["2", "ii"]
    },
    # 12. Mechanical Engineering Scheme-23 II Year Syllabus
    {
        "id": "syllabus_me_s23_ii",
        "title": "Mechanical Engineering Scheme-23 II Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/ME%20S-23%20II%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "ME",
        "years": ["2", "ii"]
    },
    # 13. Mechanical Engineering Scheme-23 III Year Syllabus
    {
        "id": "syllabus_me_s23_iii",
        "title": "Mechanical Engineering Scheme-23 III Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/ME-S23-III-Year-Syllabus.pdf.pdf",
        "category": "syllabus",
        "branch": "ME",
        "years": ["3", "iii"]
    },
    # 14. B.Tech / Mechanical Engineering Scheme-23 IV Year Syllabus
    {
        "id": "syllabus_me_s23_iv",
        "title": "B.Tech / Mechanical Engineering Scheme-23 IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/SYLLABUS-FOR-IV-%20B.Tech.pdf",
        "category": "syllabus",
        "branch": "ME",
        "years": ["4", "iv"]
    },
    # 15. ECE Scheme-23 II Year Syllabus
    {
        "id": "syllabus_ece_s23_ii",
        "title": "ECE Scheme-23 II Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/ECE%20S-23%20II%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "ECE",
        "years": ["2", "ii"]
    },
    # 16. ECE Scheme-23 III & IV Year Syllabus
    {
        "id": "syllabus_ece_s23_iii_iv",
        "title": "ECE Scheme-23 III & IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/ECE%20S-23%20III,IV%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "ECE",
        "years": ["3", "4", "iii", "iv"]
    },
    # 17. CSE Scheme-23 II Year Syllabus
    {
        "id": "syllabus_cse_s23_ii",
        "title": "CSE Scheme-23 II Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CSE%20S-23%20II%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "CSE",
        "years": ["2", "ii"]
    },
    # 18. CSE Scheme-23 III & IV Year Syllabus
    {
        "id": "syllabus_cse_s23_iii_iv",
        "title": "CSE Scheme-23 III & IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CSE-S-23%20III,IV%20Year%20Syllabus.pdf.pdf",
        "category": "syllabus",
        "branch": "CSE",
        "years": ["3", "4", "iii", "iv"]
    },
    # 19. CSE (AI & ML) Scheme-23 II Year Syllabus
    {
        "id": "syllabus_csm_s23_ii",
        "title": "CSE (AI & ML) Scheme-23 II Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CSE(AI&ML)%20S-23%20II%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "CSM",
        "years": ["2", "ii"]
    },
    # 20. CSE (AI & ML) Scheme-23 III & IV Year Syllabus
    {
        "id": "syllabus_csm_s23_iii_iv",
        "title": "CSE (AI & ML) Scheme-23 III & IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CSE(AI&ML)-S-23-III,IV-Year-Syllabus.pdf",
        "category": "syllabus",
        "branch": "CSM",
        "years": ["3", "4", "iii", "iv"]
    },
    # 21. CSE (Data Science) Scheme-23 II Year Syllabus
    {
        "id": "syllabus_csd_s23_ii",
        "title": "CSE (Data Science) Scheme-23 II Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CSE(DS)%20S%20-23%20II%20Year%20Syllabus.pdf",
        "category": "syllabus",
        "branch": "CSD",
        "years": ["2", "ii"]
    },
    # 22. CSE (Data Science) Scheme-23 III & IV Year Syllabus
    {
        "id": "syllabus_csd_s23_iii_iv",
        "title": "CSE (Data Science) Scheme-23 III & IV Year Syllabus",
        "url": "https://www.gprec.ac.in/scheme-23/CSE(DS)-S-23-III,IV-Year-Syllabus.pdf",
        "category": "syllabus",
        "branch": "CSD",
        "years": ["3", "4", "iii", "iv"]
    },
    # 23. Pre-Placement Training Activities
    {
        "id": "pre_placement_training",
        "title": "List of Pre-Placement Training Activities",
        "url": "https://www.gprec.ac.in/placementdetails/List-of-Pre-Placement-Training-Activities.pdf",
        "category": "placements_training",
        "doc_type": "training"
    },
    # 24. Final Year Internship Consolidated Data
    {
        "id": "internship_2025_26",
        "title": "Final Year Internship Consolidated Data (AY 2025-26)",
        "url": "https://www.gprec.ac.in/placementdetails/Internship/Final-Year-Internship-Consolidated-data-of-AY-2025-26.pdf",
        "category": "internship",
        "doc_type": "internship"
    },
    # 25. Exam Cell PayU Fee Payment Portal
    {
        "id": "exam_fee_payu_portal",
        "title": "GPREC Exam Cell Fee Payment Portal (PayU)",
        "url": "https://examcell.gprec.ac.in/payulogin.aspx",
        "category": "examinations",
        "doc_type": "portal"
    }
]


def detect_query_branch(q_lower: str) -> Optional[str]:
    """Identifies specific engineering branch mentioned in a syllabus query."""
    # Check AI & ML / CSM first
    if any(k in q_lower for k in ["ai&ml", "aiml", "ai and ml", "ai/ml", "csm", "artificial intelligence", "machine learning"]):
        return "CSM"
    # Check Data Science / CSD
    if any(k in q_lower for k in ["data science", "datascience", "csd", "cse(ds)", "cse ds", "cse-ds"]):
        return "CSD"
    # Check Pure CSE
    if re.search(r'\b(cse|computer science)\b', q_lower):
        return "CSE"
    # Check ECE
    if re.search(r'\b(ece|electronics and communication|electronics)\b', q_lower):
        return "ECE"
    # Check EEE
    if re.search(r'\b(eee|electrical and electronics|electrical)\b', q_lower):
        return "EEE"
    # Check ME / Mechanical
    if re.search(r'\b(me|mechanical|mech)\b', q_lower):
        return "ME"
    # Check CE / Civil
    if re.search(r'\b(ce|civil)\b', q_lower):
        return "CE"
    return None


def detect_query_year(q_lower: str) -> Optional[str]:
    """Identifies academic year mentioned in query (2, 3, 4)."""
    if any(k in q_lower for k in ["2nd year", "second year", "2 year", "ii year", "ii-year", "year 2", "year ii", "2nd sem", "3rd sem", "4th sem", "iii sem", "iv sem"]):
        return "2"
    if any(k in q_lower for k in ["3rd year", "third year", "3 year", "iii year", "iii-year", "year 3", "year iii", "5th sem", "6th sem", "v sem", "vi sem"]):
        return "3"
    if any(k in q_lower for k in ["4th year", "fourth year", "final year", "4 year", "iv year", "iv-year", "year 4", "year iv", "7th sem", "8th sem", "vii sem", "viii sem"]):
        return "4"
    return None


def find_relevant_curated_links(query: str) -> List[Dict[str, Any]]:
    """
    Matches user query to authoritative official GPREC links and PDFs.
    Returns matched link dictionaries.
    """
    q_lower = query.lower()
    matched: List[Dict[str, Any]] = []

    # 1. Exam Fee Payment Portal
    if (
        ("pay" in q_lower and any(w in q_lower for w in ["exam fee", "examination fee", "exam", "fees"]))
        or "payulogin" in q_lower
        or "payu" in q_lower
        or ("exam fee" in q_lower and any(w in q_lower for w in ["portal", "link", "online", "where", "how"]))
    ):
        portal = next((x for x in CURATED_OFFICIAL_LINKS if x["id"] == "exam_fee_payu_portal"), None)
        if portal and portal not in matched:
            matched.append(portal)

    # 2. EAPCET / EAMCET Cut-off Ranks
    if any(k in q_lower for k in ["eapcet", "eamcet", "cut-off", "cutoff", "cut off", "opening rank", "closing rank", "last rank"]):
        cutoff = next((x for x in CURATED_OFFICIAL_LINKS if x["id"] == "eapcet_cutoff_2022"), None)
        if cutoff and cutoff not in matched:
            matched.append(cutoff)

    # 3. Academic Schedule / Calendar
    if any(k in q_lower for k in [
        "academic schedule", "academic calendar", "academic planner", 
        "schedule 2026", "calendar 2026", "planner 2026", 
        "schedule 2027", "calendar 2027", "semester schedule"
    ]):
        schedule = next((x for x in CURATED_OFFICIAL_LINKS if x["id"] == "academic_schedule_2026_27"), None)
        if schedule and schedule not in matched:
            matched.append(schedule)

    # 4. Scheme 2026 Academic Regulations
    if any(k in q_lower for k in [
        "scheme 2026", "scheme-2026", "s-26", "s26", "scheme 26", 
        "b.tech regulations", "btech regulations", "academic regulations", "regulations 2026"
    ]):
        reg = next((x for x in CURATED_OFFICIAL_LINKS if x["id"] == "scheme_2026_regulations"), None)
        if reg and reg not in matched:
            matched.append(reg)

    # 5. Pre-Placement Training Activities
    if any(k in q_lower for k in [
        "pre-placement", "pre placement", "placement training", "training activities", 
        "crt training", "placement activity", "placement activities"
    ]):
        training = next((x for x in CURATED_OFFICIAL_LINKS if x["id"] == "pre_placement_training"), None)
        if training and training not in matched:
            matched.append(training)

    # 6. Internships
    if any(k in q_lower for k in ["internship", "internships", "intern data", "consolidated internship"]):
        internship = next((x for x in CURATED_OFFICIAL_LINKS if x["id"] == "internship_2025_26"), None)
        if internship and internship not in matched:
            matched.append(internship)

    # 7. Placements (Statistics, Lists, Reports)
    if "placement" in q_lower or "placements" in q_lower or "recruitment" in q_lower:
        # Check if query asks for specific year
        is_2025 = "2025" in q_lower or "2024-25" in q_lower or "latest" in q_lower or "recent" in q_lower or "current" in q_lower
        is_2024 = "2024" in q_lower or "2023-24" in q_lower or "last year" in q_lower
        is_2023 = "2023" in q_lower or "2022-23" in q_lower

        # Summary or list preference
        is_summary_only = "summary" in q_lower or "statistics" in q_lower or "stats" in q_lower or "overview" in q_lower
        is_list_only = "list" in q_lower or "selected" in q_lower or "selections" in q_lower or "company" in q_lower

        if is_2025:
            if not is_list_only:
                matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2025_summary"))
            if not is_summary_only:
                matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2025_list"))
        elif is_2024:
            if not is_list_only:
                matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2024_summary"))
            if not is_summary_only:
                matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2024_list"))
        elif is_2023:
            matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2023_summary"))
        else:
            # General placement question: provide 2025 & 2024 summaries and reports
            matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2025_summary"))
            matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2025_list"))
            matched.append(next(x for x in CURATED_OFFICIAL_LINKS if x["id"] == "placements_2024_summary"))

    # 8. Scheme-23 Syllabus Queries
    is_syllabus_query = any(k in q_lower for k in [
        "syllabus", "curriculum", "course structure", "subjects", 
        "scheme-23", "scheme 23", "s-23", "s23"
    ])
    if is_syllabus_query:
        branch = detect_query_branch(q_lower)
        year = detect_query_year(q_lower)

        syllabus_links = [x for x in CURATED_OFFICIAL_LINKS if x.get("category") == "syllabus"]

        if branch:
            branch_links = [x for x in syllabus_links if x.get("branch") == branch]
            if year:
                year_matched = [x for x in branch_links if year in x.get("years", [])]
                if year_matched:
                    matched.extend(year_matched)
                else:
                    matched.extend(branch_links)
            else:
                matched.extend(branch_links)
        else:
            # If no branch specified, if a year is requested (e.g., "2nd year syllabus")
            if year:
                year_links = [x for x in syllabus_links if year in x.get("years", [])]
                matched.extend(year_links[:4])
            else:
                # General syllabus request: provide the Scheme-2026 regulations and prominent Scheme-23 syllabi
                for syl in syllabus_links:
                    if syl["id"] in ["syllabus_cse_s23_ii", "syllabus_ece_s23_ii", "syllabus_eee_s23_ii", "syllabus_me_s23_ii", "syllabus_ce_s23_ii_iii_iv"]:
                        matched.append(syl)

    # Deduplicate while preserving order
    unique_matched = []
    seen_ids = set()
    for item in matched:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_matched.append(item)

    return unique_matched


def format_curated_links_markdown(links: List[Dict[str, Any]]) -> str:
    """Formats curated link records into clean markdown hyperlinks."""
    if not links:
        return ""
    lines = []
    for link in links:
        title = link.get("title", "Official Link")
        url = link.get("url", "")
        lines.append(f"- [{title}]({url})")
    return "\n".join(lines)
