import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest
from src.rag_pipeline import clean_answer

def test_filler_openers_removal():
    """Verify clean_answer removes various filler openers at the start of response."""
    raw = "Based on the provided context, the first semester commences in August 2026."
    expected = "The first semester commences in August 2026."
    assert clean_answer(raw) == expected

def test_multiple_openers_removal():
    """Verify clean_answer handles stacked greetings and filler phrases."""
    raw = "Sure! According to the documents, Dr. B. Sreenivasa Reddy is the Principal of the college."
    expected = "Dr. B. Sreenivasa Reddy is the Principal of the college."
    assert clean_answer(raw) == expected

def test_certainly_and_great_question_removal():
    """Verify conversational openers like 'Certainly!' and 'Great question' are removed."""
    raw = "Great question! The college offers B.Tech programs in 7 specializations."
    assert clean_answer(raw) == "The college offers B.Tech programs in 7 specializations."

    raw2 = "Certainly! Regular classes run from 9:00 AM to 4:40 PM."
    assert clean_answer(raw2) == "Regular classes run from 9:00 AM to 4:40 PM."

def test_strip_source_and_retrieved_lines():
    """Verify Source:, Sources:, Context:, and Retrieved lines are removed."""
    raw = (
        "The academic calendar was published on 15 July 2026.\n"
        "Source: https://gprec.ac.in/academic-calendar\n"
        "Retrieved from College Exam Cell\n"
        "Classes begin next week."
    )
    cleaned = clean_answer(raw)
    assert "Source:" not in cleaned
    assert "Retrieved" not in cleaned
    assert "15 July 2026" in cleaned
    assert "Classes begin next week." in cleaned

def test_remove_urls_and_markdown_links():
    """Verify raw URLs and download links are stripped from the answer body."""
    raw = "The timetable is available at https://gprec.ac.in/exam_cell/timetable.pdf for student review."
    cleaned = clean_answer(raw)
    assert "https://" not in cleaned
    assert "The timetable is available at" in cleaned

    raw_md = "You can download the PDF from [Timetable Document](https://gprec.ac.in/timetable.pdf)."
    cleaned_md = clean_answer(raw_md)
    assert "https://" not in cleaned_md
    assert "Timetable Document" in cleaned_md

def test_remove_file_paths():
    """Verify local file paths and server paths are removed."""
    raw = "Refer to /var/www/notices/notice_2026.pdf and C:\\docs\\regulations.pdf for details."
    cleaned = clean_answer(raw)
    assert "/var/www" not in cleaned
    assert "C:\\docs" not in cleaned
    assert "for details." in cleaned

def test_collapse_excess_blank_lines():
    """Verify 3 or more blank lines collapse into a single blank line."""
    raw = "First paragraph.\n\n\n\n\n\nSecond paragraph.\n\n\nThird paragraph."
    expected = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    assert clean_answer(raw) == expected

def test_strip_trailing_offers():
    """Verify polite trailing offers and sign-offs are stripped at the end."""
    raw = "The semester tuition fee is ₹70,000.\n\nLet me know if you need anything else!"
    expected = "The semester tuition fee is ₹70,000."
    assert clean_answer(raw) == expected

    raw2 = "The library closes at 8:00 PM on weekdays.\n\nHope this helps!"
    assert clean_answer(raw2) == "The library closes at 8:00 PM on weekdays."

    raw3 = "Examinations will conclude on 25 May 2026. Feel free to ask if you have any questions."
    assert clean_answer(raw3) == "Examinations will conclude on 25 May 2026."

def test_preserve_numbers_dates_and_currencies():
    """CRITICAL: Numbers, amounts (₹), dates, percentages, and counts must remain 100% untouched."""
    raw = (
        "Based on the provided context, the annual tuition fee is ₹70,000 for the 2025-2026 academic year. "
        "A total of 120 seats are approved, with an intake of 60 students per section. "
        "The cutoff rank was 14,520 in Phase 1 on 18-09-2025."
    )
    cleaned = clean_answer(raw)
    assert "₹70,000" in cleaned
    assert "2025-2026" in cleaned
    assert "120" in cleaned
    assert "60" in cleaned
    assert "14,520" in cleaned
    assert "18-09-2025" in cleaned

def test_preserve_names_and_quoted_text():
    """Verify names, qualifications, and quoted text are preserved without alteration."""
    raw = 'According to the documents, Dr. K. Govardhan Rao stated "Autonomous Status was renewed" in 2024.'
    cleaned = clean_answer(raw)
    assert "Dr. K. Govardhan Rao" in cleaned
    assert '"Autonomous Status was renewed"' in cleaned
    assert "in 2024." in cleaned

def test_empty_and_already_clean_text():
    """Verify empty strings and clean text pass through correctly."""
    assert clean_answer("") == ""
    assert clean_answer(None) == ""
    assert clean_answer("   \n\n   ") == ""
    clean_text = "The department has 28 teaching faculty members."
    assert clean_answer(clean_text) == clean_text

def test_bad_example_quality_cleanup():
    """Verify clean_answer cleans the real bad example from the specification."""
    bad_example = (
        "Based on the official GPREC sources, the Head of the Department (HoD) of Electrical and Electronics Engineering (EEE) is Dr. G. Kishor (also referenced as G Kishor).\n\n"
        "Sources:\n"
        "- The department overview page states: \"The department is headed by Dr. G.Kishor.\" 【3†L10-L13】\n"
        "- A faculty achievement note confirms: \"G Kishor, HoD of EEE Dept, of GPREC successfully supervised Sri. R Rohith for obtaining Ph.D degree in Electrical Engineering from JNTUA, Anathapuramu in the month of Jan 2026.\" 【1†L1-L4】\n\n"
        "The EEE department was established in 1994, has an intake of 120, and comprises a faculty pool of 17 Ph.D. holders and 12 M.Tech. holders (4 Professors, 8 Associate Professors, 17 Assistant Professors). 【3†L7-L15】\n\n"
        "Confidence: High"
    )
    cleaned = clean_answer(bad_example)
    assert "Dr. G. Kishor" in cleaned
    assert "Sources" not in cleaned
    assert "【" not in cleaned
    assert "Based on" not in cleaned
    assert "Confidence" not in cleaned
    assert "also referenced" not in cleaned

def test_numbers_and_dates_unchanged():
    """Case 1: Numbers, dates, years, and counts must remain strictly unchanged."""
    raw = "The EEE department was established in 1994, has an intake of 120, and the notification was issued on 18-09-2025."
    cleaned = clean_answer(raw)
    assert "1994" in cleaned
    assert "120" in cleaned
    assert "18-09-2025" in cleaned
    assert cleaned == raw

def test_currency_and_fees_unchanged():
    """Case 2: Currency (₹), amounts, and percentages stay unchanged."""
    raw = "The annual tuition fee is ₹70,000 for the academic year 2025-2026 with a minimum of 75% attendance."
    cleaned = clean_answer(raw)
    assert "₹70,000" in cleaned
    assert "2025-2026" in cleaned
    assert "75%" in cleaned
    assert cleaned == raw

def test_legitimate_sentence_with_source_stays():
    """Case 3: A legitimate sentence that contains the word 'source' must stay intact."""
    raw = "The rooftop solar panels serve as a primary source of renewable energy for the laboratory."
    cleaned = clean_answer(raw)
    assert "primary source of renewable energy" in cleaned
    assert cleaned == raw

    raw2 = "The central library is a valuable source of research journals and reference books."
    cleaned2 = clean_answer(raw2)
    assert "valuable source of research journals" in cleaned2
    assert cleaned2 == raw2

def test_already_clean_answer_identical():
    """Case 4: An answer that is already clean must stay identical."""
    clean_target = "The HOD of the Electrical and Electronics Engineering department is **Dr. G. Kishor**. The department was established in 1994 and has an intake of 120."
    assert clean_answer(clean_target) == clean_target

def test_empty_string_does_not_crash():
    """Case 5: Empty string and None must return empty string without crashing."""
    assert clean_answer("") == ""
    assert clean_answer("   ") == ""
    assert clean_answer("\n\n\t") == ""
    assert clean_answer(None) == ""

def test_bracketed_numeric_citations_removal():
    """Case 6: Bracketed citation markers like [1], [2], [1, 2] and [1-3] must be removed."""
    raw = "The campus spans 45 acres [1] with modern laboratories [2] and hostel blocks [3]."
    cleaned = clean_answer(raw)
    assert "[1]" not in cleaned
    assert "[2]" not in cleaned
    assert "[3]" not in cleaned
    assert "The campus spans 45 acres with modern laboratories and hostel blocks." == cleaned

def test_parenthetical_source_citations_removal():
    """Case 7: (Source: ...) and (Sources: ...) parentheticals must be deleted."""
    raw = "The library remains open until 8:00 PM on working days (Source: Central Library Rules 2026)."
    cleaned = clean_answer(raw)
    assert "(Source:" not in cleaned
    assert "The library remains open until 8:00 PM on working days." == cleaned

def test_name_variants_removal():
    """Case 8: '(also referenced as ...)' and '(also known as ...)' must be removed."""
    raw = "The department is headed by Dr. G. Kishor (also referenced as G Kishor) and supervised by Dr. B. Sreenivasa Reddy (also known as B S Reddy)."
    cleaned = clean_answer(raw)
    assert "also referenced as" not in cleaned
    assert "also known as" not in cleaned
    assert "Dr. G. Kishor and supervised by Dr. B. Sreenivasa Reddy." in cleaned

def test_multi_block_references_and_evidence_removal():
    """Case 9: References and Evidence blocks with bullets are deleted while preserving subsequent text."""
    raw = (
        "The cutoff rank for CSE was 5,420.\n\n"
        "Evidence:\n"
        "* The admission cutoff sheet lists 5,420 for OC boys.\n"
        "* Allotment records confirm round 1 cutoff.\n\n"
        "Reporting starts on 28 August 2026."
    )
    cleaned = clean_answer(raw)
    assert "Evidence:" not in cleaned
    assert "admission cutoff sheet" not in cleaned
    assert "The cutoff rank for CSE was 5,420." in cleaned
    assert "Reporting starts on 28 August 2026." in cleaned

def test_system_prompt_rules_included():
    """Verify the system prompt in rag_pipeline contains all required answer quality rules."""
    from src.rag_pipeline import RAGPipeline
    # Instantiate without calling __init__ to avoid loading heavy models or needing API keys
    pipeline = RAGPipeline.__new__(RAGPipeline)
    prompt = pipeline.generate_prompt("Who is the HOD of EEE?", [])

    # Assert all requested rules from Section A are present in the prompt
    assert "First sentence is the direct answer to exactly what was asked" in prompt
    assert "Answer only what was asked" in prompt
    assert "Never quote or paraphrase source passages" in prompt
    assert "Never write a Sources or References section" in prompt
    assert "Never write citation markers, line numbers, brackets with numbers or symbols like 【 】" in prompt
    assert 'Never mention "official GPREC sources"' in prompt
    assert "Do not repeat a name in a different spelling" in prompt
    assert "For a simple fact question the whole answer is 1 to 2 sentences" in prompt
    assert "Bold only the key fact (name, date, amount), at most 2 bold items" in prompt

