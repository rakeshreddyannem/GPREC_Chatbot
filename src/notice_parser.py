import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dateutil import parser as date_parser

class NoticeParser:
    """
    Parses notices into structured attributes:
    notice_type, program, semester, scheme_regulation, exam_month_year,
    published_date, attachment_urls, is_active.
    """

    TYPE_PATTERNS = [
        ("seating plan", [
            r'seating\s*(?:plan|arrangement)', r'hall\s*arrangement', r'room\s*allocation'
        ]),
        ("revaluation", [
            r'revaluation', r'recounting', r'script\s*verification', r'personal\s*verification'
        ]),
        ("hall ticket", [
            r'hall\s*tickets?', r'admit\s*cards?'
        ]),
        ("fee notification", [
            r'fee\s*notification', r'tuition\s*fee', r'exam(?:ination)?\s*fee', 
            r'condonation\s*fee', r'fee\s*structure', r'payment\s*of\s*fee'
        ]),
        ("timetable", [
            r'time\s*table', r'timetable', r'exam(?:ination)?\s*schedule', 
            r'schedule\s*of\s*(?:end\s*)?exam', r'dates\s*of\s*exam'
        ]),
        ("results", [
            r'results?', r'grade\s*cards?', r'marks\s*memos?', r'provisional\s*list'
        ]),
        ("event", [
            r'workshop', r'symposium', r'conference', r'seminar', 
            r'guest\s*lecture', r'webinar', r'fest\b', r'sports\b'
        ]),
        ("circular", [
            r'circular', r'academic\s*calendar', r'holiday', r'commencement', 
            r'instructions\s*to\s*candidates', r'postponement', r'notice\b'
        ])
    ]

    PROGRAM_PATTERNS = [
        ("B.Tech", [r'\bb\.?\s*tech\b', r'\bbachelor\s+of\s+technology\b']),
        ("M.Tech", [r'\bm\.?\s*tech\b', r'\bmaster\s+of\s+technology\b']),
        ("MBA", [r'\bmba\b', r'\bmaster\s+of\s+business\b']),
        ("MCA", [r'\bmca\b', r'\bmaster\s+of\s+computer\s+applications\b']),
    ]

    SEMESTER_PATTERNS = [
        ("VIII Sem", [r'\b(?:viii|8th|8)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b4th\s*year\s*2nd\s*sem\b']),
        ("VII Sem", [r'\b(?:vii|7th|7)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b4th\s*year\s*1st\s*sem\b']),
        ("VI Sem", [r'\b(?:vi|6th|6)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b3rd\s*year\s*2nd\s*sem\b']),
        ("V Sem", [r'\b(?:v|5th|5)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b3rd\s*year\s*1st\s*sem\b']),
        ("IV Sem", [r'\b(?:iv|4th|4)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b2nd\s*year\s*2nd\s*sem\b']),
        ("III Sem", [r'\b(?:iii|3rd|3)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b2nd\s*year\s*1st\s*sem\b']),
        ("II Sem", [r'\b(?:ii|2nd|2)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b1st\s*year\s*2nd\s*sem\b']),
        ("I Sem", [r'\b(?:i|1st|1)\s*(?:[-/]?\s*sem(?:ester)?|\s+sem)\b', r'\b1st\s*year\s*1st\s*sem\b']),
    ]

    REGULATION_PATTERNS = [
        ("R23", r'\bR\s*23\b'),
        ("R20", r'\bR\s*20\b'),
        ("R19", r'\bR\s*19\b'),
        ("R18", r'\bR\s*18\b'),
        ("R15", r'\bR\s*15\b'),
        ("R13", r'\bR\s*13\b')
    ]

    @classmethod
    def classify_notice_type(cls, title: str, text: str = "") -> str:
        combined = f"{title} {text}".lower()
        for ntype, patterns in cls.TYPE_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, combined, re.I):
                    return ntype
        return "circular"

    @classmethod
    def extract_program(cls, title: str, text: str = "") -> Optional[str]:
        combined = f"{title} {text}".lower()
        for prog, patterns in cls.PROGRAM_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, combined, re.I):
                    return prog
        return None

    @classmethod
    def extract_semester(cls, title: str, text: str = "") -> Optional[str]:
        combined = f"{title} {text}".lower()
        for sem, patterns in cls.SEMESTER_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, combined, re.I):
                    return sem
        return None

    @classmethod
    def extract_regulation(cls, title: str, text: str = "") -> Optional[str]:
        combined = f"{title} {text}".upper()
        for reg, pattern in cls.REGULATION_PATTERNS:
            if re.search(pattern, combined):
                return reg
        return None

    @classmethod
    def extract_exam_month_year(cls, title: str, text: str = "") -> Optional[str]:
        combined = f"{title} {text}"
        months = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        # Examples: "April 2026", "Nov/Dec 2025", "May - 2024"
        pattern = rf'({months}(?:\s*[/&-]\s*{months})?[\s,-]+\d{{4}})'
        match = re.search(pattern, combined, re.I)
        if match:
            return re.sub(r'\s+', ' ', match.group(1)).strip()
        return None

    @classmethod
    def extract_published_date(cls, title: str, text: str = "", default_date: str = "") -> Optional[str]:
        combined = f"{title} {text}"
        # Matches dd-mm-yyyy or yyyy-mm-dd or "20 Mar 2026"
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b',
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{4})\b'
        ]
        for pat in date_patterns:
            m = re.search(pat, combined, re.I)
            if m:
                raw_str = m.group(1)
                try:
                    dt = date_parser.parse(raw_str, fuzzy=True, dayfirst=True)
                    # Sanity check: must be a reasonable year
                    if 2018 <= dt.year <= 2030:
                        return dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

        if default_date:
            try:
                dt = date_parser.parse(default_date, fuzzy=True)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                return default_date[:10]
        return None

    @classmethod
    def parse_notice(
        cls,
        title: str,
        text: str = "",
        source_page: str = "",
        published_date: str = "",
        attachment_urls: Optional[List[str]] = None,
        is_active: int = 1
    ) -> Dict[str, Any]:
        """
        Parses all fields into a structured dictionary matching the NOTICES table schema.
        """
        clean_title = re.sub(r'\s+', ' ', title or "").strip()
        clean_text = text.strip() if text else clean_title

        ntype = cls.classify_notice_type(clean_title, clean_text)
        program = cls.extract_program(clean_title, clean_text)
        semester = cls.extract_semester(clean_title, clean_text)
        regulation = cls.extract_regulation(clean_title, clean_text)
        exam_month_year = cls.extract_exam_month_year(clean_title, clean_text)
        pub_date = cls.extract_published_date(clean_title, clean_text, default_date=published_date)

        att_list = attachment_urls or []
        if not att_list:
            # Check if text contains pdf link
            found_urls = re.findall(r'https?://[^\s<>"]+\.pdf', clean_text, re.I)
            if found_urls:
                att_list = list(set(found_urls))

        att_urls_str = ",".join(att_list) if att_list else ""

        return {
            "title": clean_title,
            "notice_type": ntype,
            "program": program,
            "semester": semester,
            "scheme_regulation": regulation,
            "exam_month_year": exam_month_year,
            "published_date": pub_date,
            "attachment_urls": att_urls_str,
            "source_page": source_page,
            "raw_text": clean_text,
            "is_active": is_active
        }
