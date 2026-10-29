import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import re
from urllib.parse import unquote

from src.syllabus_parser import (
    safe_url_encode,
    classify_syllabus_link,
    clean_text,
    ROMAN_MAP
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "syllabus"

def test_url_encoder():
    """Test URL encoder with 5 real-looking addresses containing spaces and &."""
    test_urls = [
        # 1. Path with spaces
        "https://www.gprec.ac.in/scheme-23/EEE S-23 II Year Syllabus.pdf",
        # 2. Path already percent-encoded (must NOT be double-encoded to %2520)
        "https://www.gprec.ac.in/scheme-23/EEE%20S-23%20II%20Year%20Syllabus.pdf",
        # 3. Path with & symbol
        "https://www.gprec.ac.in/scheme-2022/M.Tech-A&Robotics-Syllabus-Scheme-2022.pdf",
        # 4. Path with & and spaces and parentheses
        "https://www.gprec.ac.in/scheme-23/CSE(AI&ML) S-23 II Year Syllabus.pdf",
        # 5. Path with multiple spaces
        "https://www.gprec.ac.in/scheme-2020/GPREC-9X-SCHEME-2020 EEE STRUCTURE_SYLLABUS.pdf"
    ]

    for raw_url in test_urls:
        encoded = safe_url_encode(raw_url)
        # Must not contain raw literal spaces
        assert " " not in encoded, f"Encoded URL contains raw space: {encoded}"
        # Must never contain %2520 (double encoding of %20)
        assert "%2520" not in encoded, f"Double encoded detected: {encoded}"
        # Decoded URL must match raw URL representation
        decoded = unquote(encoded)
        raw_decoded = unquote(raw_url)
        assert decoded == raw_decoded, f"Decoded mismatch: {decoded} != {raw_decoded}"

def test_year_semester_detection():
    """Test detecting headings like 'II Year I Semester', 'III B.Tech II Sem', etc."""
    test_cases = [
        ("II Year I Semester", 2, 3), # Year 2, Sem 3
        ("II Year II Semester", 2, 4), # Year 2, Sem 4
        ("III B.Tech II Sem", 3, 6), # Year 3, Sem 6
        ("I B.Tech I Semester", 1, 1), # Year 1, Sem 1
        ("IV B.Tech I Semester", 4, 7), # Year 4, Sem 7
        ("III Semester : EEE", 2, 3), # Year 2, Sem 3
        ("V Semester: Common for all Branches", 3, 5), # Year 3, Sem 5
        ("VII Semester", 4, 7), # Year 4, Sem 7
    ]

    for heading, expected_year, expected_sem in test_cases:
        # Detect semester
        sem = None
        m_sem = re.search(r'\b(VIII|VII|VI|IV|V|III|II|I)\s*(?:Semester|Sem)\b', heading, re.I)
        if m_sem:
            sem = ROMAN_MAP.get(m_sem.group(1).upper())
        elif "1st sem" in heading.lower() or "first sem" in heading.lower():
            sem = 1
        elif "2nd sem" in heading.lower() or "second sem" in heading.lower():
            sem = 2

        # Detect year
        year = None
        m_yr = re.search(r'\b(IV|III|II|I|\d+)\s*(?:Year|B\.?Tech)\b', heading, re.I)
        if m_yr:
            val = m_yr.group(1).upper()
            year = ROMAN_MAP.get(val, int(val) if val.isdigit() else None)
        
        # If year not directly in string but sem is, calculate year = (sem + 1) // 2
        if sem and not year:
            year = (sem + 1) // 2

        # If sem is relative ("II Sem" in "III B.Tech"):
        if year and sem in (1, 2) and year > 1 and "year" in heading.lower() or "b.tech" in heading.lower():
            # If string had "II Year I Sem", sem was parsed as 1, so absolute sem is (year - 1) * 2 + sem
            if re.search(r'\b(?:I|II)\s*(?:Year|B\.?Tech)\b', heading) and sem in (1, 2):
                pass
            calc_sem = (year - 1) * 2 + sem
            sem = calc_sem

        assert sem == expected_sem, f"Heading '{heading}' expected sem {expected_sem}, got {sem}"
        assert year == expected_year, f"Heading '{heading}' expected year {expected_year}, got {year}"

def test_course_code_and_title_extraction():
    """Test extracting course code and title from 3 layouts."""
    # Layout 1: S23
    s23_file = FIXTURES_DIR / "layout_s23_sample.txt"
    text1 = s23_file.read_text(encoding="utf-8")
    lines1 = [l.strip() for l in text1.split("\n") if l.strip()]
    title1 = lines1[0]
    code1_match = re.search(r'\b([A-Z]{2,6}\d{2,4}[A-Z]?)\b', text1)
    assert "COMPLEX VARIABLES & NUMERICAL METHODS" in title1
    assert code1_match is not None
    assert code1_match.group(1) == "BS205"

    # Layout 2: S23 Common
    s23_common_file = FIXTURES_DIR / "layout_s23_common_sample.txt"
    text2 = s23_common_file.read_text(encoding="utf-8")
    lines2 = [l.strip() for l in text2.split("\n") if l.strip()]
    title2 = lines2[0]
    code2_match = re.search(r'\b([A-Z]{2,6}\d{2,4}[A-Z]?)\b', text2)
    assert "LINEAR ALGEBRA & CALCULUS" in title2
    assert code2_match is not None
    assert code2_match.group(1) == "BS101"

    # Layout 3: S20
    s20_file = FIXTURES_DIR / "layout_s20_sample.txt"
    text3 = s20_file.read_text(encoding="utf-8")
    lines3 = [l.strip() for l in text3.split("\n") if l.strip()]
    title3 = lines3[0]
    code3_match = re.search(r'\b([A-Z]{2,6}\d{2,4}[A-Z]?)\b', text3)
    assert "PROBABILITY AND STATISTICAL ANALYSIS" in title3
    assert code3_match is not None
    assert code3_match.group(1) == "BS202"

def test_unit_splitting():
    """Test unit splitting across the 3 fixture samples."""
    for fixture_name, expected_units in [
        ("layout_s23_sample.txt", 5),
        ("layout_s23_common_sample.txt", 5),
        ("layout_s20_sample.txt", 5)
    ]:
        fpath = FIXTURES_DIR / fixture_name
        content = fpath.read_text(encoding="utf-8")
        unit_splits = list(re.finditer(r'\bUNIT\s*[-–—]\s*([I|V|X]+|\d+)\b', content, re.I))
        assert len(unit_splits) == expected_units, f"{fixture_name} expected {expected_units} units, got {len(unit_splits)}"
        
        # Verify Unit I has title and topics
        u1_start = unit_splits[0].end()
        u1_end = unit_splits[1].start()
        u1_block = content[u1_start:u1_end].strip()
        lines = [l.strip() for l in u1_block.split("\n") if l.strip()]
        assert len(lines) >= 2, f"Unit 1 in {fixture_name} should have title and topics lines"
        u1_title = lines[0]
        u1_topics = " ".join(lines[1:])
        assert len(u1_title) > 3
        assert len(u1_topics) > 10

def test_link_classification():
    """Test link classification for regulations, first year, upper years, skipped links."""
    # 1. Regulations
    c1 = classify_syllabus_link("Scheme-2023", "https://www.gprec.ac.in/scheme-2023/B.Tech.-Scheme-2023-Regulations.pdf", "ACADEMIC REGULATIONS FOR UG (B.Tech)", "EEE")
    assert c1["kind"] == "regulations"
    assert c1["scheme"] == "2023"
    assert c1["status"] == "found"

    # 2. First Year
    c2 = classify_syllabus_link("Scheme-2023", "https://www.gprec.ac.in/scheme-2023/Scheme-2023-I-B.Tech-scheme-Syllabus.pdf", "SYLLABUS FOR I B.Tech : Scheme-2023", "EEE")
    assert c2["kind"] == "first_year"
    assert c2["scheme"] == "2023"
    assert c2["status"] == "found"

    # 3. Upper Years
    c3 = classify_syllabus_link("Scheme-2023", "https://www.gprec.ac.in/scheme-23/EEE S-23 II Year Syllabus.pdf", "SYLLABUS FOR II B.Tech : Scheme-2023", "EEE")
    assert c3["kind"] == "upper_years"
    assert c3["scheme"] == "2023"
    assert c3["status"] == "found"

    # 4. Older scheme (< 2020)
    c4 = classify_syllabus_link("Scheme-2017", "https://www.gprec.ac.in/scheme17_syllabus/S-17 EEE Syllabus.pdf", "SYLLABUS FOR II, III, IV B.Tech", "EEE")
    assert c4["scheme"] == "2017"
    assert c4["status"] == "skipped"
    assert "Older scheme" in c4["reason"]

    # 5. M.Tech Program
    c5 = classify_syllabus_link("Scheme-2022", "https://www.gprec.ac.in/scheme-2022/M.Tech-A&Robotics-Syllabus-Scheme-2022.pdf", "SYLLABUS FOR M.Tech (Automation and Robotics)", "EEE")
    assert c5["program"] == "M.Tech"
    assert c5["status"] == "skipped"
    assert "M.Tech" in c5["reason"]

    # 6. Word Document (.doc)
    c6 = classify_syllabus_link("Scheme-2013", "https://www.gprec.ac.in/Power%20Electronics%20M.Tech%20EEE.doc", "SYLLABUS FOR M.Tech", "EEE")
    assert c6["status"] == "skipped"
    assert ".doc" in c6["reason"]

    # 7. Minor & Honors
    c7 = classify_syllabus_link("Scheme-2023", "https://www.gprec.ac.in/minor_degree/MINOR-In-EEE-Scheme-23.pdf", "Syllabus For Minor Degree in EEE", "EEE")
    assert c7["kind"] == "minor"
    assert c7["status"] == "skipped"
