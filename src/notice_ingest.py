import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dateutil import parser as date_parser

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from src.database import DatabaseManager
from src.notice_parser import NoticeParser


def extract_deadline_date(text: str) -> Optional[str]:
    """
    Extracts deadline_date ONLY if a date is clearly written next to
    the words 'last date', 'on or before', or 'due'.
    """
    if not text:
        return None

    deadline_patterns = [
        # "last date ... is/on/: 15-11-2026" or "last date for submission ... 15/11/2026"
        r'(?:last\s+date|closing\s+date)(?:[^\n\r.,;]{0,60}?)(?:is|on|by|:|-)?\s*[:\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{4})',
        # "on or before 15-11-2026" or "on or before: 15/11/2026"
        r'(?:on\s+or\s+before)\s*[:\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{4})',
        # "due date ... is/on/by/: 15-11-2026" or "due by / due on 15-11-2026"
        r'(?:due\s+(?:date|by|on)?)\s*(?:is|on|by|:|-)?\s*[:\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{4})'
    ]

    for pat in deadline_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_date = m.group(1).strip()
            # Clean ordinal suffixes like 5th, 1st, 2nd, 3rd
            raw_date_clean = re.sub(r'(\d+)(?:st|nd|rd|th)\b', r'\1', raw_date, flags=re.I)
            try:
                dt = date_parser.parse(raw_date_clean, fuzzy=True, dayfirst=True)
                if 2020 <= dt.year <= 2030:
                    return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    return None


def clean_notice_title(link_text: str, nearby_text: str, document_url: str) -> str:
    """Derives a clean, readable title for the notice."""
    lt = (link_text or "").strip()
    # If link_text has substantial alphanumeric content and isn't just symbols
    if lt and re.search(r'[A-Za-z0-9]{3,}', lt):
        clean = re.sub(r'\s+', ' ', lt).strip()
        if clean.lower() not in ["download", "pdf", "click here", "link", "view", "here", "|"]:
            return clean

    # Fallback to nearby text if short and descriptive
    nt = (nearby_text or "").strip()
    if nt and re.search(r'[A-Za-z0-9]{3,}', nt):
        clean_nt = re.sub(r'\s+', ' ', nt).strip()
        if len(clean_nt) <= 120 and clean_nt.lower() not in ["download", "pdf", "click here"]:
            return clean_nt
        elif len(clean_nt) > 120:
            first_sentence = clean_nt.split(".")[0].strip()
            if 10 <= len(first_sentence) <= 120:
                return first_sentence

    # Derive from document URL filename stem
    try:
        from urllib.parse import unquote
        stem = Path(unquote(document_url)).stem
        stem = re.sub(r'[_\-]+', ' ', stem).strip()
        if len(stem) >= 3:
            return stem
    except Exception:
        pass

    return lt or "College Notice / Circular"


def infer_department(text: str, default: str = "") -> str:
    """Infers department if explicitly mentioned."""
    if default and default.lower() not in ["general", "none", ""]:
        return default
    t_upper = text.upper()
    dept_map = [
        ("EEE", [r'\bEEE\b', r'ELECTRICAL\s+AND\s+ELECTRONICS']),
        ("ECE", [r'\bECE\b', r'ELECTRONICS\s+AND\s+COMMUNICATION']),
        ("CSE", [r'\bCSE\b', r'COMPUTER\s+SCIENCE\s+AND\s+ENGINEERING']),
        ("ME", [r'\bME\b', r'\bMECH\b', r'MECHANICAL\s+ENGINEERING']),
        ("CE", [r'\bCE\b', r'\bCIVIL\b', r'CIVIL\s+ENGINEERING']),
        ("CSM", [r'\bCSM\b', r'ARTIFICIAL\s+INTELLIGENCE']),
        ("CSD", [r'\bCSD\b', r'DATA\s+SCIENCE']),
        ("MBA", [r'\bMBA\b']),
        ("MCA", [r'\bMCA\b']),
    ]
    for dept_code, patterns in dept_map:
        for p in patterns:
            if re.search(p, t_upper):
                return dept_code
    return "General"


def ingest_notices_from_documents(db: Optional[DatabaseManager] = None) -> Dict[str, Any]:
    """
    Ingests notices from the documents table into the notices and deadlines tables.
    """
    if db is None:
        db = DatabaseManager()

    keywords = [
        "notice", "circular", "notification", "exam",
        "timetable", "schedule", "result", "admission"
    ]
    conditions = []
    for k in keywords:
        conditions.append(f"LOWER(IFNULL(parent_page_url, '')) LIKE '%{k}%'")
        conditions.append(f"LOWER(IFNULL(link_text, '')) LIKE '%{k}%'")
        conditions.append(f"LOWER(IFNULL(category, '')) LIKE '%{k}%'")

    where_clause = " OR ".join(conditions)
    query = f"""
    SELECT document_url, link_text, parent_page_url, nearby_text, category, department, published_date, date_source, last_checked
    FROM documents
    WHERE {where_clause}
    ORDER BY 
        CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC,
        id DESC
    """

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = [dict(r) for r in cursor.fetchall()]

    total_matching = len(rows)
    print(f"============================================================")
    print(f"NOTICE INGESTION: {total_matching} matching document rows found")
    print(f"============================================================\n")

    # 1. Print 10 most recent matching rows
    print("--- 10 Most Recent Matching Document Rows ---")
    for i, r in enumerate(rows[:10], 1):
        dt = r.get("published_date") or "Date not found"
        print(f"{i:2d}. Date: {dt} (source: {r.get('date_source')})")
        print(f"    Title: {r.get('link_text')}")
        print(f"    URL:   {r.get('document_url')}")
        print(f"    Parent Page: {r.get('parent_page_url')}\n")

    now_iso = datetime.now().isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")

    notices_found = 0
    notices_with_date = 0
    notices_without_date = 0
    notices_with_deadline = 0

    for r in rows:
        notices_found += 1
        doc_url = r["document_url"]
        link_text = r.get("link_text") or ""
        nearby_text = r.get("nearby_text") or ""
        parent_page = r.get("parent_page_url") or ""
        raw_pub_date = r.get("published_date") or ""
        date_src = r.get("date_source")

        combined_text = f"{link_text} {nearby_text}".strip()

        # Call NoticeParser.parse_notice
        parsed = NoticeParser.parse_notice(
            title=link_text,
            text=nearby_text,
            source_page=parent_page,
            published_date=raw_pub_date,
            attachment_urls=[doc_url]
        )

        final_title = clean_notice_title(link_text, nearby_text, doc_url)
        final_dept = infer_department(combined_text, default=r.get("department") or "")
        final_cat = r.get("category") or parsed.get("notice_type", "circular").title()

        # Handle published_date: store NULL if no date found, never guess or use today's date
        pub_date = parsed.get("published_date")
        if pub_date:
            notices_with_date += 1
        else:
            pub_date = None
            date_src = None
            notices_without_date += 1

        # Extract deadline_date ONLY if written next to last date / on or before / due
        deadline = extract_deadline_date(combined_text)
        if deadline:
            notices_with_deadline += 1

        notice_record = {
            "title": final_title,
            "notice_type": parsed.get("notice_type", "circular"),
            "program": parsed.get("program"),
            "semester": parsed.get("semester"),
            "scheme_regulation": parsed.get("scheme_regulation"),
            "exam_month_year": parsed.get("exam_month_year"),
            "published_date": pub_date,
            "date_source": date_src,
            "attachment_urls": doc_url,
            "source_page": parent_page,
            "parent_page_url": parent_page,
            "document_url": doc_url,
            "raw_text": combined_text or final_title,
            "is_active": 1,
            "category": final_cat,
            "department": final_dept,
            "deadline_date": deadline,
            "last_checked": now_iso
        }
        db.upsert_notice(notice_record)

        if deadline:
            is_active_deadline = "ACTIVE" if deadline >= today_str else "EXPIRED"
            deadline_record = {
                "title": final_title,
                "category": final_cat,
                "deadline_date": deadline,
                "published_date": pub_date,
                "department": final_dept,
                "source_url": doc_url,
                "status": is_active_deadline,
                "last_checked": now_iso
            }
            db.upsert_deadline(deadline_record)

    # 8. Print short report
    print("============================================================")
    print("NOTICE INGESTION REPORT")
    print("============================================================")
    print(f"Notices found:          {notices_found}")
    print(f"Notices with a date:    {notices_with_date}")
    print(f"Notices without a date: {notices_without_date}")
    print(f"Notices with a deadline:{notices_with_deadline}")
    print("============================================================\n")

    return {
        "notices_found": notices_found,
        "notices_with_date": notices_with_date,
        "notices_without_date": notices_without_date,
        "notices_with_deadline": notices_with_deadline
    }


if __name__ == "__main__":
    ingest_notices_from_documents()
