"""
Timetable Parser and Syllabus Matcher for GPREC AI Student Assistant.
Extracts subjects, sections, faculty, and academic terms from timetable PDFs,
matches them against the syllabus knowledge base, and writes structured records.
"""

import os
import re
import sys
import difflib
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import fitz  # PyMuPDF

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.database import DatabaseManager

ROMAN_MAP = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
    'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10
}


def normalize_title(title: str) -> str:
    """
    Normalizes a subject or course title:
    - Lowercase
    - Removes punctuation and special characters
    - Normalizes internal whitespace
    """
    if not title:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(title).lower())
    return " ".join(clean.split())


def clean_subject_for_matching(title: str) -> str:
    """Cleans up timetable subject string for matching without mutating stored subject name."""
    if not title:
        return ""
    cleaned = re.sub(r'\((?:Professional|Open)?\s*Elective\s*[-–]?[A-Z0-9IVX]+\)', '', title, flags=re.IGNORECASE)
    cleaned = re.sub(r'\((?:PE|OE)\s*[-–]?[A-Z0-9IVX]+\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
    cleaned = re.sub(r'\s*&\s*', ' and ', cleaned)
    cleaned = re.sub(r'[-_\s]2\b', ' - II', cleaned)
    cleaned = re.sub(r'[-_\s]1\b', ' - I', cleaned)
    cleaned = re.sub(r'[-_\s]3\b', ' - III', cleaned)
    return " ".join(cleaned.split())


def match_subject_with_syllabus(
    subject_name: str,
    course_code: Optional[str],
    branch: Optional[str],
    semester: Optional[int],
    syllabus_rows: List[Dict[str, Any]],
    threshold: float = 0.85
) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Matches a timetable subject against syllabus rows:
    1. By course code first (exact/alphanumeric match)
    2. Then by normalised title similarity >= threshold (default 0.85)
    Returns: (matched_course_code, similarity_ratio, matched_syllabus_title)
    Does NOT guess matches below threshold.
    """
    if not syllabus_rows:
        return (None, 0.0, None)

    # 1. Match by course code first
    if course_code:
        norm_code = re.sub(r'[^a-zA-Z0-9]', '', str(course_code)).upper()
        if norm_code:
            for row in syllabus_rows:
                r_code = row.get("course_code")
                if r_code:
                    norm_r_code = re.sub(r'[^a-zA-Z0-9]', '', str(r_code)).upper()
                    if norm_code == norm_r_code:
                        return (r_code, 1.0, row.get("course_title"))

    # Also check if subject_name begins with an exact course code like "CS202" or "EC301"
    clean_sub_str = str(subject_name).strip()
    code_in_sub = re.match(r'^([A-Z]{2,4}\s*\d{3}[A-Z]?)\b', clean_sub_str, re.IGNORECASE)
    if code_in_sub:
        norm_sub_code = re.sub(r'[^a-zA-Z0-9]', '', code_in_sub.group(1)).upper()
        for row in syllabus_rows:
            r_code = row.get("course_code")
            if r_code:
                norm_r_code = re.sub(r'[^a-zA-Z0-9]', '', str(r_code)).upper()
                if norm_sub_code == norm_r_code:
                    return (r_code, 1.0, row.get("course_title"))

    # 2. Match by normalized title similarity
    norm_sub = normalize_title(subject_name)
    norm_sub_cleaned = normalize_title(clean_subject_for_matching(subject_name))
    if not norm_sub and not norm_sub_cleaned:
        return (None, 0.0, None)

    # Prioritize candidate rows by branch or common/all
    target_branch = (branch or "").upper()
    branch_candidates = []
    other_candidates = []

    for r in syllabus_rows:
        r_branch = (r.get("branch") or "").upper()
        if target_branch and (r_branch == target_branch or r_branch in ["COMMON", "ALL", ""]):
            branch_candidates.append(r)
        else:
            other_candidates.append(r)

    candidate_pool = branch_candidates if branch_candidates else syllabus_rows

    best_code = None
    best_ratio = 0.0
    best_title = None

    for row in candidate_pool:
        row_title = row.get("course_title") or ""
        norm_row_title = normalize_title(row_title)
        if not norm_row_title:
            continue

        ratio = difflib.SequenceMatcher(None, norm_sub, norm_row_title).ratio()
        if norm_sub_cleaned and norm_sub_cleaned != norm_sub:
            ratio = max(ratio, difflib.SequenceMatcher(None, norm_sub_cleaned, norm_row_title).ratio())

        # Compare against title without parenthetical abbreviation, e.g. "ADVANCED DATA STRUCTURES"
        base_title = re.sub(r'\([A-Za-z0-9\s\-&]+\)', '', row_title).strip()
        norm_base = normalize_title(base_title)
        if norm_base:
            base_ratio = difflib.SequenceMatcher(None, norm_sub, norm_base).ratio()
            if norm_sub_cleaned and norm_sub_cleaned != norm_sub:
                base_ratio = max(base_ratio, difflib.SequenceMatcher(None, norm_sub_cleaned, norm_base).ratio())
            ratio = max(ratio, base_ratio)

        # Check abbreviation parenthetical in syllabus title, e.g. (ADS) vs "ADS"
        abbr_match = re.search(r'\(([A-Za-z0-9\-]{2,8})\)', row_title)
        if abbr_match:
            abbr = abbr_match.group(1).upper()
            if clean_sub_str.upper() == abbr:
                ratio = max(ratio, 1.0)

        if ratio > best_ratio:
            best_ratio = ratio
            best_code = row.get("course_code")
            best_title = row_title

    # Fallback to other branches if not matched
    if best_ratio < threshold and branch_candidates and other_candidates:
        for row in other_candidates:
            row_title = row.get("course_title") or ""
            norm_row_title = normalize_title(row_title)
            if not norm_row_title:
                continue
            ratio = difflib.SequenceMatcher(None, norm_sub, norm_row_title).ratio()
            if norm_sub_cleaned and norm_sub_cleaned != norm_sub:
                ratio = max(ratio, difflib.SequenceMatcher(None, norm_sub_cleaned, norm_row_title).ratio())
            base_title = re.sub(r'\([A-Za-z0-9\s\-&]+\)', '', row_title).strip()
            norm_base = normalize_title(base_title)
            if norm_base:
                base_ratio = difflib.SequenceMatcher(None, norm_sub, norm_base).ratio()
                if norm_sub_cleaned and norm_sub_cleaned != norm_sub:
                    base_ratio = max(base_ratio, difflib.SequenceMatcher(None, norm_sub_cleaned, norm_base).ratio())
                ratio = max(ratio, base_ratio)
            if ratio > best_ratio:
                best_ratio = ratio
                best_code = row.get("course_code")
                best_title = row_title

    if best_ratio >= threshold:
        return (best_code, round(best_ratio, 3), best_title)
    return (None, round(best_ratio, 3), None)


class TimetableParser:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.syllabus_cache = self._load_syllabus_rows()

    def _load_syllabus_rows(self) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT course_code, course_title, branch, semester
                FROM syllabus
                WHERE course_title IS NOT NULL AND course_title != ''
            """)
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def extract_page_metadata(page_text: str, filename: str) -> Dict[str, Any]:
        """Extracts Branch, Year, Semester, Section, Academic Year from page header text."""
        lines = [l.strip() for l in page_text.splitlines() if l.strip()]
        full_text = "\n".join(lines)

        # Academic Year
        ay_match = re.search(r'academic\s*year\s*[:\-]?\s*([0-9]{4}\s*[\-–]\s*[0-9]{2,4})', full_text, re.IGNORECASE)
        if not ay_match:
            ay_match = re.search(r'\b(202[0-9]\s*[\-–]\s*202[0-9]|202[0-9]\s*[\-–]\s*[0-9]{2})\b', full_text)
        academic_year = ay_match.group(1).replace("–", "-").strip() if ay_match else "2023-2024"

        # Department / Branch
        branch = "UNKNOWN"
        upper_text = full_text.upper()
        if "COMPUTER SCIENCE" in upper_text or "CSE" in upper_text:
            branch = "CSE"
        if "ELECTRONICS" in upper_text and "COMMUNICATION" in upper_text:
            branch = "ECE"
        elif "ELECTRICAL" in upper_text and "ELECTRONICS" in upper_text:
            branch = "EEE"
        elif "CIVIL ENGINEERING" in upper_text or "CIVIL" in upper_text:
            branch = "CE"
        elif "MECHANICAL ENGINEERING" in upper_text or "MECHANICAL" in upper_text:
            branch = "ME"

        # Refine sub-branch (CSM)
        class_line_match = re.search(r'CLASS\s*[:\-]?\s*([^\n\r]+)', full_text, re.IGNORECASE)
        class_line = class_line_match.group(1).strip() if class_line_match else ""

        if "CSM" in class_line.upper() or "AI&ML" in class_line.upper() or "AI & ML" in full_text.upper():
            branch = "CSM"

        # Semester
        sem = None
        sem_match = re.search(r'\b(I|II|III|IV|V|VI|VII|VIII)\s*(?:SEM|SEMESTER)\b', full_text, re.IGNORECASE)
        if not sem_match:
            sem_match = re.search(r'\b([1-8])(?:st|nd|rd|th)?\s*(?:SEM|SEMESTER)\b', full_text, re.IGNORECASE)
            if sem_match:
                sem = int(sem_match.group(1))
        else:
            sem = ROMAN_MAP.get(sem_match.group(1).upper())

        year = None
        if sem:
            year = (sem + 1) // 2
        else:
            yr_match = re.search(r'\b(I|II|III|IV)\s*(?:YEAR|B\.?\s*TECH)\b', full_text, re.IGNORECASE)
            if yr_match:
                year = ROMAN_MAP.get(yr_match.group(1).upper())
                if year:
                    sem = (year * 2) - 1

        # Section
        sec = None
        sec_match = re.search(r'(?:SEC|SECTION)\s*[-:]?\s*([A-D])\b', class_line, re.IGNORECASE)
        if not sec_match:
            sec_match = re.search(r'\b([A-D])\s*SECTION\b', class_line, re.IGNORECASE)
        if not sec_match:
            sec_match = re.search(r'[-_]([A-D])\b', class_line)
        if not sec_match:
            sec_match = re.search(r'CLASS[^\n\r]*?[-_\s]([A-D])\b', full_text, re.IGNORECASE)
        if sec_match:
            sec = sec_match.group(1).upper()

        return {
            "branch": branch,
            "year": year or 1,
            "semester": sem or 1,
            "section": sec,
            "academic_year": academic_year,
            "class_line": class_line
        }

    @staticmethod
    def clean_subject_name(s: str) -> str:
        if not s:
            return ""
        s = re.sub(r'([A-Za-z]{3,})(of|through|and|for)([A-Z])', r'\1 \2 \3', s)
        s = re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', s)
        s = re.sub(r'([A-Za-z])([&])', r'\1 & ', s)
        s = re.sub(r'([&])([A-Za-z])', r' & \1', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def parse_legend_entries(page_text: str) -> List[Dict[str, Any]]:
        """
        Parses theory and practical subjects from the timetable page legend.
        Handles both multiline table layouts and single-line mappings.
        """
        subjects = []
        lines = [l.strip() for l in page_text.splitlines() if l.strip()]

        excluded_keys = {
            "CLASS", "NOTE", "LECTURE", "DAY", "TIME", "GPREC", "G.PULLA", "G. PULLA",
            "DEPARTMENT", "REVISION", "PREPARED", "VERIFIED", "APPROVED", "PRINCIPAL",
            "HOD", "MON", "TUE", "WED", "THU", "FRI", "SAT", "VENUE", "TEA", "BREAK", "LUNCH", "FRS"
        }

        # 1. Multiline colon pattern:
        # Line i-1: ABBR (e.g. ADS, DBS, OOPJ, MEFA)
        # Line i: : Title (e.g. :Advanced Data Structures)
        for i in range(1, len(lines)):
            curr = lines[i]
            prev = lines[i-1]

            if curr.startswith(":") and len(curr) > 2:
                title = curr.lstrip(":").strip()
                abbr = prev.strip()

                if any(ex in abbr.upper() for ex in excluded_keys) or re.match(r'^\d+:\d+', abbr):
                    continue
                if re.match(r'^(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)', title):
                    continue

                faculty = None
                if i + 2 < len(lines):
                    cand = lines[i+2]
                    if re.match(r'^(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)', cand):
                        faculty = cand
                    elif cand.startswith(":") and re.match(r'^(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)', cand.lstrip(":").strip()):
                        faculty = cand.lstrip(":").strip()
                if not faculty and i + 1 < len(lines):
                    cand = lines[i+1]
                    if re.match(r'^(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)', cand):
                        faculty = cand
                    elif cand.startswith(":") and re.match(r'^(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)', cand.lstrip(":").strip()):
                        faculty = cand.lstrip(":").strip()

                course_code = None
                if re.match(r'^[A-Z]{2,4}\s*\d{3}[A-Z]?$', abbr):
                    course_code = abbr.replace(" ", "")

                subjects.append({
                    "abbr": abbr,
                    "course_code": course_code,
                    "subject_name": title,
                    "faculty": faculty
                })

        # 2. Single-line colon pattern: ABBR : Title [Faculty]
        for line in lines:
            if line.startswith(":"):
                continue
            m = re.match(r'^([A-Za-z][A-Za-z0-9\(\)\-]{1,9})\s*:\s*(.+)$', line)
            if m:
                abbr = m.group(1).strip()
                rest = m.group(2).strip()
                if any(ex in abbr.upper() for ex in excluded_keys) or re.match(r'^\d+:\d+', line):
                    continue
                if re.match(r'^(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)', rest):
                    continue

                sec_colon = re.search(r'\s+([a-z]{2,5})\s*:\s*(.+)$', rest)
                faculty = None
                title = rest
                if sec_colon:
                    title = rest[:sec_colon.start()].strip()
                    faculty = sec_colon.group(2).strip()
                else:
                    fac_match = re.search(r'\b(Dr\.|Sri|Smt|Prof\.|Ms\.|Mr\.)\s+[A-Za-z\.\s]+$', rest)
                    if fac_match:
                        faculty = fac_match.group(0).strip()
                        title = rest[:fac_match.start()].strip()
                        title = re.sub(r'\s+[A-Z]{2,4}$', '', title).strip()

                course_code = None
                if re.match(r'^[A-Z]{2,4}\s*\d{3}[A-Z]?$', abbr):
                    course_code = abbr.replace(" ", "")

                subjects.append({"abbr": abbr, "course_code": course_code, "subject_name": title, "faculty": faculty})

        # 3. Numbered pattern (Civil / ME / ECE):
        num_matches = re.findall(r'(?:^|\n)\s*(\d+)\s+([A-Za-z0-9\(\)\-]{2,10})\s+([A-Za-z][A-Za-z0-9\s,&/\(\)\-]+?)(?=\s+[a-z]{2,4}\b|\s+\d+\s+[A-Z]|\n|$)', page_text)
        for _, abbr, title in num_matches:
            clean_title = title.strip()
            if len(clean_title) > 3 and not any(clean_title.upper().startswith(p) for p in excluded_keys):
                course_code = None
                if re.match(r'^[A-Z]{2,4}\s*\d{3}[A-Z]?$', abbr):
                    course_code = abbr.replace(" ", "")
                subjects.append({"abbr": abbr, "course_code": course_code, "subject_name": clean_title, "faculty": None})

        # 4. Direct Course code lines (e.g. EC201, BS204, HSM201)
        for line in lines:
            code_line = re.match(r'^([A-Z]{2,4}\s*\d{3}[A-Z]?)\s+([A-Za-z][A-Za-z0-9\s\(\)\-&]+)$', line)
            if code_line:
                code = code_line.group(1).replace(" ", "")
                title = code_line.group(2).strip()
                if not any(ex in title.upper() for ex in excluded_keys):
                    subjects.append({"abbr": code, "course_code": code, "subject_name": title, "faculty": None})

        # Deduplicate and clean subject names
        unique = []
        seen = set()
        for s in subjects:
            s["subject_name"] = self.clean_subject_name(s.get("subject_name", ""))
            k = (s["abbr"].upper(), s["subject_name"].lower())
            if k not in seen and len(s["subject_name"]) >= 2:
                seen.add(k)
                unique.append(s)
        return unique

    def parse_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Parses a single timetable PDF and returns structured subject rows."""
        parsed_rows = []
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return [{
                "branch": "UNKNOWN", "year": 0, "semester": 0, "section": None,
                "academic_year": "2023-2024", "course_code": None, "subject_name": "Corrupted PDF",
                "faculty": None, "source_file": pdf_path.name, "page_num": 0, "needs_review": 1,
                "is_current_semester": 1
            }]

        page_count = len(doc)
        if page_count == 0:
            return [{
                "branch": "UNKNOWN", "year": 0, "semester": 0, "section": None,
                "academic_year": "2023-2024", "course_code": None, "subject_name": "Empty 0-page PDF",
                "faculty": None, "source_file": pdf_path.name, "page_num": 0, "needs_review": 1,
                "is_current_semester": 1
            }]

        for pno in range(page_count):
            page = doc[pno]
            text = page.get_text("text")
            has_text = len(text.strip()) > 30

            meta = self.extract_page_metadata(text, pdf_path.name)

            if not has_text:
                parsed_rows.append({
                    "branch": meta["branch"],
                    "year": meta["year"],
                    "semester": meta["semester"],
                    "section": meta["section"],
                    "academic_year": meta["academic_year"],
                    "course_code": None,
                    "subject_name": f"Scanned Timetable Page {pno+1}",
                    "faculty": None,
                    "source_file": pdf_path.name,
                    "page_num": pno + 1,
                    "needs_review": 1,
                    "is_current_semester": 1,
                    "match_status": "SCANNED_NEEDS_OCR"
                })
                continue

            entries = self.parse_legend_entries(text)

            for item in entries:
                # Match against syllabus
                matched_code, score, matched_title = match_subject_with_syllabus(
                    subject_name=item["subject_name"],
                    course_code=item.get("course_code"),
                    branch=meta["branch"],
                    semester=meta["semester"],
                    syllabus_rows=self.syllabus_cache,
                    threshold=0.85
                )

                parsed_rows.append({
                    "branch": meta["branch"],
                    "year": meta["year"],
                    "semester": meta["semester"],
                    "section": meta["section"],
                    "academic_year": meta["academic_year"],
                    "course_code": matched_code or item.get("course_code"),
                    "subject_name": item["subject_name"],
                    "faculty": item.get("faculty"),
                    "source_file": pdf_path.name,
                    "page_num": pno + 1,
                    "needs_review": 1 if not matched_code else 0,
                    "is_current_semester": 1,
                    "matched_syllabus_title": matched_title,
                    "match_score": score
                })

        return parsed_rows

    def parse_all_pdfs_and_save(self, pdf_paths: List[Path]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Parses all PDFs, saves records to timetable_subjects table, and generates markdown report."""
        all_rows = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM timetable_subjects")
            conn.commit()

        for path in pdf_paths:
            rows = self.parse_pdf(path)
            for r in rows:
                self.db.insert_timetable_subject(r)
                all_rows.append(r)

        matched_rows = [r for r in all_rows if r.get("course_code")]
        unmatched_rows = [r for r in all_rows if not r.get("course_code")]

        # Generate report
        self.generate_markdown_report(all_rows, Path("data/reports/timetable_subjects.md"))
        return (matched_rows, unmatched_rows)

    @staticmethod
    def generate_markdown_report(rows: List[Dict[str, Any]], report_path: Path):
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Timetable Subjects & Syllabus Mapping Report",
            "",
            "This report details all subjects extracted from the timetable PDFs, organized per **Branch, Year, and Semester**, including matched syllabus course codes and review items.",
            "",
            "## Summary Metrics",
            f"- **Total Timetable Entries Extracted**: {len(rows)}",
            f"- **Syllabus Matched Entries**: {len([r for r in rows if r.get('course_code')])}",
            f"- **Unmatched / Review Required**: {len([r for r in rows if not r.get('course_code')])}",
            "",
            "---",
            ""
        ]

        grouped: Dict[Tuple[str, int, int], List[Dict[str, Any]]] = {}
        for r in rows:
            key = (r.get("branch", "UNKNOWN"), r.get("year", 0), r.get("semester", 0))
            grouped.setdefault(key, []).append(r)

        for (branch, year, semester), items in sorted(grouped.items()):
            lines.append(f"### Branch: {branch} | Year: {year} | Semester: {semester}")
            lines.append("| Subject Name | Matched Course Code | Faculty | Section | Matched Syllabus Title | Match Status |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

            for item in items:
                status = "✅ Matched" if item.get("course_code") else "⚠️ Unmatched"
                code = item.get("course_code") or "-"
                fac = item.get("faculty") or "-"
                sec = item.get("section") or "-"
                title = item.get("matched_syllabus_title") or "-"
                lines.append(f"| {item.get('subject_name')} | **{code}** | {fac} | {sec} | {title} | {status} |")
            lines.append("")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report written to {report_path}")


def run_pipeline():
    """Runs end-to-end timetable parsing and syllabus matching."""
    db = DatabaseManager()
    parser = TimetableParser(db)
    
    tt_dir = Path("timetable_pdfs")
    if tt_dir.exists():
        text_pdfs = sorted(list(tt_dir.glob("*.pdf")))
    else:
        text_pdfs = [
            Path("data/pdf/ea8fb5a3afae518cbad00e8563bf1b49.pdf"),
            Path("data/pdf/50096d38c057dab2550204ce70676a12.pdf"),
            Path("data/pdf/d01aaee9116381668a3df12235b68041.pdf"),
            Path("data/pdf/0c819bae55dc3dd42deaaac3de5a7b0c.pdf"),
            Path("data/pdf/3fe463abe3b0518c12d7f1fcc56d4968.pdf"),
            Path("data/pdf/65c5c42e27935525aaa2b387d8afb13d.pdf"),
            Path("data/pdf/b2b6f8450d6a34f20b45d6126505b061.pdf"),
            Path("data/pdf/d09bb2cc13ca46370f7df11c69676d1a.pdf"),
            Path("data/pdf/89fc6dcd1d0aaea1b874ed83a765e228.pdf"),
            Path("data/pdf/914a59cb2254aca57f386399994882c6.pdf"),
        ]

    matched, unmatched = parser.parse_all_pdfs_and_save(text_pdfs)
    print(f"\nPipeline Finished: Matched = {len(matched)}, Unmatched = {len(unmatched)}")
    return matched, unmatched


if __name__ == "__main__":
    run_pipeline()
