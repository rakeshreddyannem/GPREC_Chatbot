import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import numpy as np
import hashlib
import faiss
from typing import List

import config
from src.database import DatabaseManager
from src.vectorstore import VectorStore
from ingest import run_ingestion


class FakeEmbedder:
    """Deterministic, lightweight embedder for fast offline testing."""
    def __init__(self, dimension: int = 16):
        self.dimension = dimension

    def embed_text(self, text: str) -> np.ndarray:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.vstack([self.embed_text(t) for t in texts])


@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "test_knowledge.db"
    db = DatabaseManager(db_path=db_path)

    vstore = VectorStore(dimension=16)
    vstore.index_path = tmp_path / "faiss_index.bin"
    vstore.meta_path = tmp_path / "metadata.pkl"
    vstore.index = faiss.IndexFlatL2(16)
    vstore.metadata = []
    vstore.bm25 = None

    fake_embedder = FakeEmbedder(dimension=16)
    pdf_dir = tmp_path / "pdf_data"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    return {
        "db": db,
        "vstore": vstore,
        "embedder": fake_embedder,
        "pdf_dir": pdf_dir,
        "tmp_path": tmp_path
    }


def test_update_flow_pages(test_env):
    db = test_env["db"]
    vstore = test_env["vstore"]
    embedder = test_env["embedder"]
    pdf_dir = test_env["pdf_dir"]

    # 1. Seed 3 initial pages in the database
    p1_url = "https://gprec.ac.in/page1"
    p2_url = "https://gprec.ac.in/page2"
    p3_url = "https://gprec.ac.in/page3"

    p1_old_text = "Original content: Artificial Intelligence and Machine Learning curriculum at GPREC college."
    p2_text = "Electrical and Electronics Engineering laboratories, faculty members, and high voltage lab facilities."
    p3_old_text = "Hostel accommodation rules, mess timings, and student admission guidelines for boys and girls."

    db.upsert_page({
        "source_url": p1_url,
        "title": "AI & ML Department",
        "clean_text": p1_old_text,
        "content_hash": hashlib.sha256(p1_old_text.encode("utf-8")).hexdigest(),
        "version": 1,
        "status": "NEW",
        "is_current": 1
    })

    db.upsert_page({
        "source_url": p2_url,
        "title": "EEE Department",
        "clean_text": p2_text,
        "content_hash": hashlib.sha256(p2_text.encode("utf-8")).hexdigest(),
        "version": 1,
        "status": "NEW",
        "is_current": 1
    })

    db.upsert_page({
        "source_url": p3_url,
        "title": "Hostel & Campus",
        "clean_text": p3_old_text,
        "content_hash": hashlib.sha256(p3_old_text.encode("utf-8")).hexdigest(),
        "version": 1,
        "status": "NEW",
        "is_current": 1
    })

    # Run initial ingestion
    r1 = run_ingestion(db=db, vstore=vstore, embedder=embedder, pdf_dir=pdf_dir)
    assert r1["new_count"] == 3
    assert r1["modified_count"] == 0
    assert r1["removed_count"] == 0
    assert vstore.index.ntotal == len(vstore.metadata)
    assert vstore.index.ntotal > 0

    p2_initial_chunks = sum(1 for m in vstore.metadata if m.get("source_url") == p2_url)
    p3_initial_chunks = sum(1 for m in vstore.metadata if m.get("source_url") == p3_url)
    assert p2_initial_chunks > 0
    assert p3_initial_chunks > 0

    # Every chunk must have content_hash and version
    for chunk in vstore.metadata:
        assert "content_hash" in chunk and chunk["content_hash"]
        assert "version" in chunk and chunk["version"] >= 1

    # -------------------------------------------------------------------------
    # (a) Modify one page (Page 1)
    # -------------------------------------------------------------------------
    p1_new_text = "Updated content: Quantum Computing and Advanced Robotics research center at GPREC institution."
    new_hash_p1 = hashlib.sha256(p1_new_text.encode("utf-8")).hexdigest()

    db.upsert_page({
        "source_url": p1_url,
        "title": "Quantum Robotics Center",
        "clean_text": p1_new_text,
        "content_hash": new_hash_p1,
        "version": 2,
        "status": "MODIFIED",
        "is_current": 1
    })

    r2 = run_ingestion(db=db, vstore=vstore, embedder=embedder, pdf_dir=pdf_dir)
    assert vstore.index.ntotal == len(vstore.metadata)
    assert r2["modified_count"] == 1
    assert r2["new_count"] == 0

    # Old text is gone
    assert not any("Artificial Intelligence and Machine Learning" in m.get("content", "") for m in vstore.metadata)

    # New text is present and searchable
    results = vstore.search(embedder.embed_text("Quantum Computing"), query_text="Quantum Computing", top_k=5)
    assert any("Quantum Computing" in res.get("content", "") for res in results)

    # Check updated metadata version and hash on page 1 chunks
    p1_chunks = [m for m in vstore.metadata if m.get("source_url") == p1_url]
    assert len(p1_chunks) > 0
    for c in p1_chunks:
        assert c["version"] == 2
        assert c["content_hash"] == new_hash_p1

    # -------------------------------------------------------------------------
    # (b) Remove one page (Page 3)
    # -------------------------------------------------------------------------
    db.set_page_current(p3_url, is_current=0, status="REMOVED")

    r3 = run_ingestion(db=db, vstore=vstore, embedder=embedder, pdf_dir=pdf_dir)
    assert vstore.index.ntotal == len(vstore.metadata)
    assert r3["removed_count"] == 1

    # Assert none of Page 3's chunks remain
    page3_remaining = sum(1 for m in vstore.metadata if m.get("source_url") == p3_url)
    assert page3_remaining == 0
    assert not any("Hostel accommodation rules" in m.get("content", "") for m in vstore.metadata)

    # -------------------------------------------------------------------------
    # (c) Unchanged pages keep the same chunk count
    # -------------------------------------------------------------------------
    page2_final_chunks = sum(1 for m in vstore.metadata if m.get("source_url") == p2_url)
    assert page2_final_chunks == p2_initial_chunks
    assert r3["unchanged_count"] >= 1

    # Final assertion after all operations
    assert vstore.index.ntotal == len(vstore.metadata)


def test_vectorstore_remove_by_urls_direct(test_env):
    """Directly verifies remove_by_urls reconstructs index and keeps 1:1 alignment."""
    vstore = test_env["vstore"]
    embedder = test_env["embedder"]

    chunks = [
        {"source_url": "url_A", "content": "text chunk A1", "content_hash": "hA", "version": 1},
        {"source_url": "url_A", "content": "text chunk A2", "content_hash": "hA", "version": 1},
        {"source_url": "url_B", "content": "text chunk B1", "content_hash": "hB", "version": 1},
        {"source_url": "url_C", "content": "text chunk C1", "content_hash": "hC", "version": 1},
        {"source_url": "url_C", "content": "text chunk C2", "content_hash": "hC", "version": 1},
    ]
    texts = [c["content"] for c in chunks]
    vecs = embedder.embed_batch(texts)

    vstore.add_chunks(chunks, vecs, save=True)
    assert vstore.index.ntotal == len(vstore.metadata) == 5

    # 1. Remove url_A (2 chunks)
    removed = vstore.remove_by_urls(["url_A"], save=True)
    assert removed == 2
    assert vstore.index.ntotal == len(vstore.metadata) == 3
    remaining_urls = {m["source_url"] for m in vstore.metadata}
    assert remaining_urls == {"url_B", "url_C"}

    # 2. Removing nonexistent URL returns 0 and does not change index
    removed_none = vstore.remove_by_urls(["url_Z"], save=True)
    assert removed_none == 0
    assert vstore.index.ntotal == len(vstore.metadata) == 3

    # 3. Remove all remaining
    removed_all = vstore.remove_by_urls(["url_B", "url_C"], save=True)
    assert removed_all == 3
    assert vstore.index.ntotal == len(vstore.metadata) == 0


def test_documents_incremental_update(test_env, tmp_path, monkeypatch):
    """Tests document incremental updates: NEW, MODIFIED, and REMOVED."""
    db = test_env["db"]
    vstore = test_env["vstore"]
    embedder = test_env["embedder"]
    pdf_dir = test_env["pdf_dir"]

    # Mock PDFProcessor.extract_text_from_pdf for fast offline testing
    def mock_extract(self, path):
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
        return [{"page_num": 1, "content": f"Extracted document text from {Path(path).name}: {content}"}]

    monkeypatch.setattr("src.pdf_loader.PDFProcessor.extract_text_from_pdf", mock_extract)

    # Create dummy pdf files
    pdf1 = tmp_path / "exam_notice.pdf"
    pdf1.write_bytes(b"dummy pdf 1 content for end semester examinations schedule")

    pdf2 = tmp_path / "timetable.pdf"
    pdf2.write_bytes(b"dummy pdf 2 content for mid term sessional timetable")

    doc1_url = "https://gprec.ac.in/docs/exam_notice.pdf"
    doc2_url = "https://gprec.ac.in/docs/timetable.pdf"

    hash1 = hashlib.sha256(pdf1.read_bytes()).hexdigest()
    hash2 = hashlib.sha256(pdf2.read_bytes()).hexdigest()

    db.upsert_document({
        "document_url": doc1_url,
        "title": "Semester Examination Notice",
        "status": "downloaded",
        "filepath": str(pdf1),
        "content_hash": hash1,
        "version": 1
    })

    db.upsert_document({
        "document_url": doc2_url,
        "title": "Sessional Timetable",
        "status": "downloaded",
        "filepath": str(pdf2),
        "content_hash": hash2,
        "version": 1
    })

    # Ingest docs
    r1 = run_ingestion(db=db, vstore=vstore, embedder=embedder, pdf_dir=pdf_dir)
    assert vstore.index.ntotal == len(vstore.metadata)
    assert any(m.get("source_url") == doc1_url for m in vstore.metadata)
    assert any(m.get("source_url") == doc2_url for m in vstore.metadata)

    # Modify doc1
    pdf1.write_bytes(b"%PDF-1.4 REVISED exam notice with new dates")
    hash1_v2 = hashlib.sha256(pdf1.read_bytes()).hexdigest()
    db.upsert_document({
        "document_url": doc1_url,
        "title": "Revised Semester Examination Notice",
        "status": "MODIFIED",
        "filepath": str(pdf1),
        "content_hash": hash1_v2,
        "version": 2
    })

    r2 = run_ingestion(db=db, vstore=vstore, embedder=embedder, pdf_dir=pdf_dir)
    assert vstore.index.ntotal == len(vstore.metadata)
    assert r2["modified_count"] == 1

    # Remove doc2
    db.upsert_document({
        "document_url": doc2_url,
        "title": "Sessional Timetable",
        "status": "REMOVED",
        "filepath": str(pdf2),
        "content_hash": hash2,
        "version": 1
    })

    r3 = run_ingestion(db=db, vstore=vstore, embedder=embedder, pdf_dir=pdf_dir)
    assert vstore.index.ntotal == len(vstore.metadata)
    assert not any(m.get("source_url") == doc2_url for m in vstore.metadata)
