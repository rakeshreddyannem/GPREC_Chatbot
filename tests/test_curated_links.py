import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pytest
from typing import List
from src.curated_links import (
    CURATED_OFFICIAL_LINKS,
    find_relevant_curated_links,
    format_curated_links_markdown
)
from src.reliability import ResponseType
from src.rag_pipeline import RAGPipeline
from src.database import DatabaseManager


def test_curated_links_inventory():
    """Verify all 25 official links requested by user are present and correctly formed."""
    urls = [item["url"] for item in CURATED_OFFICIAL_LINKS]
    assert len(urls) == 25, f"Expected 25 unique links, found {len(urls)}"
    assert len(set(urls)) == 25, "Duplicate URLs found in CURATED_OFFICIAL_LINKS"

    expected_urls = [
        "https://www.gprec.ac.in/placementdetails/2025-placements.pdf",
        "https://www.gprec.ac.in/placementdetails/2025%20-%20Summary.pdf",
        "https://www.gprec.ac.in/placementdetails/2024-placements.pdf",
        "https://www.gprec.ac.in/placementdetails/2024%20-%20Summary.pdf",
        "https://www.gprec.ac.in/placementdetails/2023-Summary.pdf",
        "https://www.gprec.ac.in/collegepdf/EAPCET-2022-PHASE-1-CUT-OFF-Ranks.pdf",
        "https://www.gprec.ac.in/academicplanner/ACADEMIC%20SCHEDULE-2026-2027.pdf",
        "https://www.gprec.ac.in/scheme-2026/B.Tech-Scheme-2026-Regulations.pdf",
        "https://www.gprec.ac.in/scheme-23/CE-S-23-II-III-IV-Year-Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/EEE-S23-III-IV-Year-Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/EEE%20S-23%20II%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/ME%20S-23%20II%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/ME-S23-III-Year-Syllabus.pdf.pdf",
        "https://www.gprec.ac.in/scheme-23/SYLLABUS-FOR-IV-%20B.Tech.pdf",
        "https://www.gprec.ac.in/scheme-23/ECE%20S-23%20II%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/ECE%20S-23%20III,IV%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/CSE%20S-23%20II%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/CSE-S-23%20III,IV%20Year%20Syllabus.pdf.pdf",
        "https://www.gprec.ac.in/scheme-23/CSE(AI&ML)%20S-23%20II%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/CSE(AI&ML)-S-23-III,IV-Year-Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/CSE(DS)%20S%20-23%20II%20Year%20Syllabus.pdf",
        "https://www.gprec.ac.in/scheme-23/CSE(DS)-S-23-III,IV-Year-Syllabus.pdf",
        "https://www.gprec.ac.in/placementdetails/List-of-Pre-Placement-Training-Activities.pdf",
        "https://www.gprec.ac.in/placementdetails/Internship/Final-Year-Internship-Consolidated-data-of-AY-2025-26.pdf",
        "https://examcell.gprec.ac.in/payulogin.aspx",
    ]

    for expected in expected_urls:
        assert expected in urls, f"Missing requested URL: {expected}"


def test_exam_fee_payu_portal_matching():
    """Verify questions about paying exam fee return the PayU portal hyperlink."""
    queries = [
        "How can I pay my exam fees online?",
        "Where to pay exam fee?",
        "exam fee payment link",
        "payulogin portal for exam cell",
    ]
    for q in queries:
        links = find_relevant_curated_links(q)
        assert any(l["url"] == "https://examcell.gprec.ac.in/payulogin.aspx" for l in links), f"Failed for query: {q}"
        md = format_curated_links_markdown(links)
        assert "[GPREC Exam Cell Fee Payment Portal (PayU)](https://examcell.gprec.ac.in/payulogin.aspx)" in md


def test_eapcet_cutoff_matching():
    """Verify questions regarding EAPCET cutoff ranks return Phase-1 cutoff PDF."""
    links = find_relevant_curated_links("What were the EAPCET cut off ranks for admission?")
    assert any(l["url"] == "https://www.gprec.ac.in/collegepdf/EAPCET-2022-PHASE-1-CUT-OFF-Ranks.pdf" for l in links)


def test_academic_schedule_matching():
    """Verify questions regarding academic schedule/calendar return 2026-2027 PDF."""
    links = find_relevant_curated_links("Can you give me the academic schedule for 2026-2027?")
    assert any(l["url"] == "https://www.gprec.ac.in/academicplanner/ACADEMIC%20SCHEDULE-2026-2027.pdf" for l in links)


def test_scheme_2026_regulations_matching():
    """Verify questions regarding Scheme 2026 regulations return B.Tech Scheme-2026 Regulations PDF."""
    links = find_relevant_curated_links("What are the Scheme 2026 academic regulations for B.Tech?")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-2026/B.Tech-Scheme-2026-Regulations.pdf" for l in links)


def test_placements_and_internship_matching():
    """Verify placement reports, summaries, pre-placement training and internship queries."""
    # 2025
    links_2025 = find_relevant_curated_links("What are the placement statistics for 2025?")
    assert any("2025%20-%20Summary.pdf" in l["url"] for l in links_2025)

    # 2024
    links_2024 = find_relevant_curated_links("Give me the 2024 placement selections list")
    assert any("2024-placements.pdf" in l["url"] for l in links_2024)

    # 2023
    links_2023 = find_relevant_curated_links("Show me 2023 placement summary")
    assert any("2023-Summary.pdf" in l["url"] for l in links_2023)

    # Pre-placement training
    links_train = find_relevant_curated_links("What pre-placement training activities are conducted?")
    assert any("List-of-Pre-Placement-Training-Activities.pdf" in l["url"] for l in links_train)

    # Final year internship
    links_intern = find_relevant_curated_links("Where can I find final year internship consolidated data?")
    assert any("Final-Year-Internship-Consolidated-data-of-AY-2025-26.pdf" in l["url"] for l in links_intern)


def test_syllabus_matching_by_branch_and_year():
    """Verify syllabus queries for all branches and years return exact PDF links."""
    # CSE 2nd Year
    cse2 = find_relevant_curated_links("Give me the CSE 2nd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CSE%20S-23%20II%20Year%20Syllabus.pdf" for l in cse2)

    # CSE 3rd/4th Year
    cse3 = find_relevant_curated_links("What is the syllabus for CSE 3rd year?")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CSE-S-23%20III,IV%20Year%20Syllabus.pdf.pdf" for l in cse3)

    # CSE (AI & ML) 2nd Year
    csm2 = find_relevant_curated_links("Give me CSE AI&ML 2nd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CSE(AI&ML)%20S-23%20II%20Year%20Syllabus.pdf" for l in csm2)

    # CSE (AI & ML) 3rd Year
    csm3 = find_relevant_curated_links("Give me CSM 3rd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CSE(AI&ML)-S-23-III,IV-Year-Syllabus.pdf" for l in csm3)

    # CSE (Data Science) 2nd Year
    csd2 = find_relevant_curated_links("Where is the CSE Data Science 2nd year syllabus?")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CSE(DS)%20S%20-23%20II%20Year%20Syllabus.pdf" for l in csd2)

    # CSE (Data Science) 4th Year
    csd4 = find_relevant_curated_links("Where is CSD 4th year syllabus?")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CSE(DS)-S-23-III,IV-Year-Syllabus.pdf" for l in csd4)

    # Civil Engineering
    ce = find_relevant_curated_links("Civil engineering syllabus Scheme-23")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/CE-S-23-II-III-IV-Year-Syllabus.pdf" for l in ce)

    # EEE 2nd Year
    eee2 = find_relevant_curated_links("EEE 2nd year syllabus Scheme-23")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/EEE%20S-23%20II%20Year%20Syllabus.pdf" for l in eee2)

    # EEE 3rd Year
    eee3 = find_relevant_curated_links("EEE 3rd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/EEE-S23-III-IV-Year-Syllabus.pdf" for l in eee3)

    # Mechanical 2nd Year
    me2 = find_relevant_curated_links("Mechanical engineering 2nd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/ME%20S-23%20II%20Year%20Syllabus.pdf" for l in me2)

    # Mechanical 3rd Year
    me3 = find_relevant_curated_links("Mechanical engineering 3rd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/ME-S23-III-Year-Syllabus.pdf.pdf" for l in me3)

    # Mechanical 4th Year
    me4 = find_relevant_curated_links("Mechanical engineering 4th year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/SYLLABUS-FOR-IV-%20B.Tech.pdf" for l in me4)

    # ECE 2nd Year
    ece2 = find_relevant_curated_links("ECE 2nd year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/ECE%20S-23%20II%20Year%20Syllabus.pdf" for l in ece2)

    # ECE 4th Year
    ece4 = find_relevant_curated_links("ECE 4th year syllabus")
    assert any(l["url"] == "https://www.gprec.ac.in/scheme-23/ECE%20S-23%20III,IV%20Year%20Syllabus.pdf" for l in ece4)


def test_rag_pipeline_returns_hyperlinks_offline(tmp_path):
    """Verify RAG pipeline provides clickable markdown hyperlinks for queries matching curated links."""
    class MockEmbedder:
        def embed_text(self, text):
            return [0.0] * 384

    class MockVectorStore:
        def search(self, *args, **kwargs):
            return []

    pipeline = RAGPipeline(
        embedder=MockEmbedder(),
        vstore=MockVectorStore(),
        db=DatabaseManager(db_path=tmp_path / "test_curated.db")
    )
    # Ensure LLM client is None (offline mode)
    pipeline.client = None

    # 1. Exam fee payment query
    res_fee = pipeline.answer_question("Where can I pay exam fees online?")
    assert res_fee["response_type"] == ResponseType.ANSWERED
    assert res_fee["confidence"] == "High"
    assert "[GPREC Exam Cell Fee Payment Portal (PayU)](https://examcell.gprec.ac.in/payulogin.aspx)" in res_fee["answer"]
    assert any(s["source_url"] == "https://examcell.gprec.ac.in/payulogin.aspx" for s in res_fee["sources"])

    # 2. Syllabus query
    res_syl = pipeline.answer_question("Give me the CSE 2nd year syllabus")
    assert res_syl["response_type"] == ResponseType.ANSWERED
    assert res_syl["confidence"] == "High"
    assert "https://www.gprec.ac.in/scheme-23/CSE%20S-23%20II%20Year%20Syllabus.pdf" in res_syl["answer"]
    assert any("CSE%20S-23%20II%20Year%20Syllabus.pdf" in s["source_url"] for s in res_syl["sources"])
