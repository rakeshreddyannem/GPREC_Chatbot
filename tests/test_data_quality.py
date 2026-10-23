import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.data_quality import (
    BoilerplateCleaner, SectionTitleExtractor, 
    ChunkDeduplicator, CoverageAuditor
)
from src.database import DatabaseManager

def test_boilerplate_cleaner():
    raw_text = """
    Skip to main content
    G. Pulla Reddy Engineering College (Autonomous) Kurnool, Andhra Pradesh
    Phone: +91 8518 270957
    The department has 12 state-of-the-art laboratories.
    Follow us on Facebook Twitter YouTube
    Copyright © 2026 G. Pulla Reddy Engineering College. All rights reserved.
    """
    cleaned = BoilerplateCleaner.clean_text(raw_text)
    assert "Skip to main content" not in cleaned
    assert "Follow us on Facebook" not in cleaned
    assert "All rights reserved" not in cleaned
    assert "12 state-of-the-art laboratories" in cleaned

def test_section_title_extractor():
    base_title = "Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College"
    content = "The department has Assistant Professors who specialize in Power Systems and IoT."
    title = SectionTitleExtractor.derive_title(base_title, content, "https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/")
    assert "EEE" in title
    assert "Assistant Professors" in title

def test_chunk_deduplication():
    chunk_1 = {
        "content": "GPREC has excellent placements with top recruiters like TCS, Infosys, and Wipro visiting each academic year."
    }
    # Exact duplicate
    chunk_2 = {
        "content": "GPREC has excellent placements with top recruiters like TCS, Infosys, and Wipro visiting each academic year."
    }
    # Near duplicate (minor stopword variations)
    chunk_3 = {
        "content": "GPREC has excellent placements with top recruiters like TCS, Infosys, Wipro visiting every academic year."
    }
    # Completely distinct chunk
    chunk_4 = {
        "content": "The central library holds over 65,000 volumes of books, 150 print journals, and IEEE digital library access."
    }

    chunks = [chunk_1, chunk_2, chunk_3, chunk_4]
    deduped = ChunkDeduplicator.deduplicate_chunks(chunks, similarity_threshold=0.85)
    assert len(deduped) == 2  # Only one placement chunk and one library chunk kept
    assert any("library" in c["content"] for c in deduped)

def test_verified_facts_leadership_principal(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "SEED_DEMO_DATA", True)
    test_db = tmp_path / "test_facts.db"
    db = DatabaseManager(db_path=test_db)
    db._seed_verified_facts()
    facts = db.get_matching_verified_facts("who is the principal of this college")
    assert len(facts) >= 1
    assert any("Sreenivasa Reddy" in f["value"] for f in facts)

def test_coverage_auditor(tmp_path):
    test_db = tmp_path / "test_coverage.db"
    db = DatabaseManager(db_path=test_db)
    # Populate test fixture pages with sufficient content (>= 200 bytes) for audited domains
    db.upsert_page({
        "source_url": "https://gprec.ac.in/departments/eee",
        "title": "EEE department faculty",
        "department": "EEE",
        "clean_text": "Electrical and Electronics Engineering faculty members and laboratory infrastructure. " * 10
    })
    db.upsert_page({
        "source_url": "https://gprec.ac.in/placements",
        "title": "Placement statistics / recruiters",
        "department": "T&P",
        "clean_text": "Placement training and recruitment statistics for top companies visiting GPREC college. " * 10
    })
    audit = CoverageAuditor.audit_coverage(db)
    assert "EEE department faculty" in audit
    assert "Library resources & timings" in audit
    assert "Placement statistics / recruiters" in audit
    # Domains with seeded test pages are PRESENT
    assert audit["EEE department faculty"]["status"] == "PRESENT"
    assert audit["Placement statistics / recruiters"]["status"] == "PRESENT"
    # Unpopulated domain is correctly audited as MISSING
    assert audit["Library resources & timings"]["status"] == "MISSING"

def test_entity_directory(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "SEED_DEMO_DATA", True)
    test_db = tmp_path / "test_entities.db"
    db = DatabaseManager(db_path=test_db)
    db._seed_entity_directory()
    principal_entities = db.search_entity_directory("who is the principal of this college")
    assert len(principal_entities) >= 1
    assert "Sreenivasa Reddy" in principal_entities[0]["name"]
    assert principal_entities[0]["role"] == "Principal"

    eee_hod_entities = db.search_entity_directory("who is the HOD of EEE")
    assert len(eee_hod_entities) >= 1
    assert "Kishor" in eee_hod_entities[0]["name"]
    assert eee_hod_entities[0]["department"] == "EEE"
