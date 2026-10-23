import sys
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from src.database import DatabaseManager
from src.chunker import DocumentChunker
from src.embeddings import Embedder
from src.vectorstore import VectorStore
from src.pdf_loader import PDFProcessor
from src.syllabus_parser import SyllabusParser

def is_syllabus_pdf(doc: dict) -> bool:
    """Heuristic to check if a document is a syllabus/regulation PDF."""
    text_to_check = ((doc.get('document_url') or '') + " " + (doc.get('title') or '') + " " + (doc.get('link_text') or '')).lower()
    keywords = ['syllabus', 'regulation', 'curriculum', 'r20', 'r23', 'scheme', 'course structure']
    return any(k in text_to_check for k in keywords)

def run_ingestion(
    db: Optional[DatabaseManager] = None,
    vstore: Optional[VectorStore] = None,
    embedder: Optional[Embedder] = None,
    pdf_dir: Optional[Path] = None,
    batch_size: int = 32
) -> Dict[str, Any]:
    print("Initializing Database, Chunker, Embedder, and VectorStore...")
    db = db or DatabaseManager()
    embedder = embedder or Embedder()
    vstore = vstore or VectorStore(dimension=embedder.dimension)
    target_pdf_dir = pdf_dir if pdf_dir is not None else config.PDF_DATA_DIR
    chunker = DocumentChunker()
    pdf_processor = PDFProcessor()
    syllabus_parser = SyllabusParser()

    # Map indexed URLs to list of their chunk metadata in vstore
    indexed_chunks_by_url: Dict[str, List[Dict[str, Any]]] = {}
    for meta in vstore.metadata:
        url = meta.get("source_url") or meta.get("document_url")
        if url:
            indexed_chunks_by_url.setdefault(url, []).append(meta)

    print(f"Index currently holds {vstore.index.ntotal if vstore.index else 0} vectors across {len(indexed_chunks_by_url)} unique URLs.")

    new_items: List[Dict[str, Any]] = []
    modified_items: List[Dict[str, Any]] = []
    removed_items: List[Dict[str, Any]] = []
    unchanged_items: List[Dict[str, Any]] = []

    urls_to_remove: Set[str] = set()
    pages_to_embed: List[Dict[str, Any]] = []
    docs_to_embed: List[Dict[str, Any]] = []
    manual_pdfs_to_embed: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # 1. Process Website Pages from Database
    # -------------------------------------------------------------
    all_pages = db.get_all_pages()
    for page in all_pages:
        url = page.get("source_url", "")
        if not url:
            continue
        title = page.get("title") or url
        is_curr = page.get("is_current", 1)
        status = (page.get("status") or "").upper()
        clean_text = page.get("clean_text") or ""
        db_hash = page.get("content_hash") or ""
        if not db_hash and clean_text:
            db_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
            page["content_hash"] = db_hash

        if is_curr == 0 or status == "REMOVED":
            # Page has disappeared or was marked removed
            if url in indexed_chunks_by_url:
                urls_to_remove.add(url)
                removed_items.append({"url": url, "title": title, "type": "page"})
            if is_curr != 0:
                db.set_page_current(url, is_current=0, status="REMOVED")
        elif url in indexed_chunks_by_url:
            stored_chunks = indexed_chunks_by_url[url]
            stored_hash = next((c.get("content_hash") for c in stored_chunks if c.get("content_hash")), "")
            is_modified = (status == "MODIFIED") or (bool(db_hash) and bool(stored_hash) and db_hash != stored_hash)
            if is_modified:
                urls_to_remove.add(url)
                pages_to_embed.append(page)
                modified_items.append({"url": url, "title": title, "type": "page"})
            else:
                unchanged_items.append({"url": url, "title": title, "type": "page"})
        else:
            # New page not yet indexed
            pages_to_embed.append(page)
            new_items.append({"url": url, "title": title, "type": "page"})

    # -------------------------------------------------------------
    # 2. Process Crawled Documents (PDFs) from Database
    # -------------------------------------------------------------
    documents = db.get_all_documents()
    for doc in documents:
        doc_url = doc.get("document_url", "")
        if not doc_url or not doc_url.lower().endswith(".pdf"):
            continue
        title = doc.get("title") or doc.get("link_text") or doc_url
        is_curr = doc.get("is_current", 1)
        status = (doc.get("status") or "").upper()
        doc_hash = doc.get("content_hash") or ""

        # Download / locate file
        filepath_str = doc.get("filepath")
        filepath = Path(filepath_str) if filepath_str else None
        
        # If needed for embedding and not yet downloaded
        if (is_curr == 1 and status != "REMOVED") and (not filepath or not filepath.exists()):
            try:
                filepath = pdf_processor.download_pdf(doc_url)
                if filepath:
                    doc["filepath"] = str(filepath)
                    doc["status"] = "downloaded"
                    db.upsert_document(doc)
            except Exception as e:
                print(f"Failed to download doc {doc_url}: {e}")

        if filepath and filepath.exists() and not doc_hash:
            try:
                doc_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
                doc["content_hash"] = doc_hash
                db.upsert_document(doc)
            except Exception:
                pass

        if is_curr == 0 or status in ["REMOVED", "404"]:
            if doc_url in indexed_chunks_by_url:
                urls_to_remove.add(doc_url)
                removed_items.append({"url": doc_url, "title": title, "type": "document"})
        elif doc_url in indexed_chunks_by_url:
            stored_chunks = indexed_chunks_by_url[doc_url]
            stored_hash = next((c.get("content_hash") for c in stored_chunks if c.get("content_hash")), "")
            is_modified = (status == "MODIFIED") or (bool(doc_hash) and bool(stored_hash) and doc_hash != stored_hash)
            if is_modified:
                urls_to_remove.add(doc_url)
                docs_to_embed.append(doc)
                modified_items.append({"url": doc_url, "title": title, "type": "document"})
            else:
                unchanged_items.append({"url": doc_url, "title": title, "type": "document"})
        else:
            docs_to_embed.append(doc)
            new_items.append({"url": doc_url, "title": title, "type": "document"})

    # -------------------------------------------------------------
    # 3. Process Manually Dropped PDFs in data/pdf/
    # -------------------------------------------------------------
    if target_pdf_dir and target_pdf_dir.exists():
        manual_pdfs = list(target_pdf_dir.glob("*.pdf"))
        for pdf_path in manual_pdfs:
            # Skip if it matches a downloaded crawler PDF
            if any(d.get("filepath") == str(pdf_path) for d in documents):
                continue
            source_url = f"file://{pdf_path.name}"
            title = pdf_path.stem
            try:
                file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            except Exception:
                file_hash = ""

            if source_url in indexed_chunks_by_url:
                stored_chunks = indexed_chunks_by_url[source_url]
                stored_hash = next((c.get("content_hash") for c in stored_chunks if c.get("content_hash")), "")
                if file_hash and stored_hash and stored_hash != file_hash:
                    urls_to_remove.add(source_url)
                    manual_pdfs_to_embed.append({"path": pdf_path, "url": source_url, "hash": file_hash})
                    modified_items.append({"url": source_url, "title": title, "type": "manual_pdf"})
                else:
                    unchanged_items.append({"url": source_url, "title": title, "type": "manual_pdf"})
            else:
                manual_pdfs_to_embed.append({"path": pdf_path, "url": source_url, "hash": file_hash})
                new_items.append({"url": source_url, "title": title, "type": "manual_pdf"})

        # Check if any indexed manual PDF was deleted from disk
        for indexed_url in indexed_chunks_by_url:
            if indexed_url.startswith("file://"):
                fname = indexed_url.replace("file://", "")
                if not (target_pdf_dir / fname).exists():
                    urls_to_remove.add(indexed_url)
                    removed_items.append({"url": indexed_url, "title": fname, "type": "manual_pdf"})

    print(f"\n--- Ingestion Plan ---")
    print(f"NEW items:       {len(new_items)}")
    print(f"MODIFIED items:  {len(modified_items)}")
    print(f"REMOVED items:   {len(removed_items)}")
    print(f"UNCHANGED items: {len(unchanged_items)}")

    # -------------------------------------------------------------
    # 4. Remove Chunks for Modified / Removed URLs
    # -------------------------------------------------------------
    if urls_to_remove:
        chunks_removed = vstore.remove_by_urls(urls_to_remove, save=False)
        print(f"Removed {chunks_removed} old chunks from index for {len(urls_to_remove)} URLs.")

    # -------------------------------------------------------------
    # 5. Generate Chunks for NEW and MODIFIED Items
    # -------------------------------------------------------------
    all_chunks = []

    # Pages
    for page in tqdm(pages_to_embed, desc="Chunking Pages"):
        chunks = chunker.chunk_page(page)
        all_chunks.extend(chunks)

    # Documents
    for doc in tqdm(docs_to_embed, desc="Processing Crawled Docs"):
        filepath_str = doc.get("filepath")
        filepath = Path(filepath_str) if filepath_str else None
        if not filepath or not filepath.exists():
            continue
        pages_text = pdf_processor.extract_text_from_pdf(filepath)
        doc_metadata = {
            "source_url": doc["document_url"],
            "title": doc.get("title") or doc.get("link_text") or filepath.stem,
            "category": doc.get("category", "Document"),
            "department": doc.get("department", "General"),
            "published_date": doc.get("published_date", ""),
            "last_checked": doc.get("last_checked", ""),
            "content_hash": doc.get("content_hash") or hashlib.sha256(filepath.read_bytes()).hexdigest(),
            "version": doc.get("version", 1),
            "is_current": 1,
            "link_text": doc.get("link_text", "")
        }

        # Syllabus parsing if applicable
        if is_syllabus_pdf(doc):
            for p in pages_text:
                if len(p["content"].strip()) > 100:
                    syllabus_entries = syllabus_parser.parse_page(
                        page_text=p["content"],
                        page_num=p["page_num"],
                        doc_url=doc["document_url"],
                        doc_metadata=doc_metadata
                    )
                    for entry in syllabus_entries:
                        db.upsert_syllabus(entry)

        pdf_chunks = chunker.chunk_pdf(doc_metadata, pages_text)
        all_chunks.extend(pdf_chunks)

    # Manual PDFs
    for m in tqdm(manual_pdfs_to_embed, desc="Processing Manual PDFs"):
        pdf_path = m["path"]
        source_url = m["url"]
        file_hash = m["hash"]
        pages_text = pdf_processor.extract_text_from_pdf(pdf_path)
        pdf_metadata = {
            "source_url": source_url,
            "title": pdf_path.stem,
            "category": "Manual PDFs",
            "department": "General",
            "content_hash": file_hash,
            "version": 1,
            "is_current": 1,
        }
        pdf_chunks = chunker.chunk_pdf(pdf_metadata, pages_text)
        all_chunks.extend(pdf_chunks)

    # -------------------------------------------------------------
    # 6. Embed and Add Chunks (save=False per batch)
    # -------------------------------------------------------------
    if all_chunks:
        print(f"\nEmbedding and adding {len(all_chunks)} chunks in batches of {batch_size} (save=False)...")
        for i in tqdm(range(0, len(all_chunks), batch_size), desc="Embedding"):
            batch_chunks = all_chunks[i:i+batch_size]
            batch_texts = [c["content"] for c in batch_chunks]
            embeddings = embedder.embed_batch(batch_texts)
            vstore.add_chunks(batch_chunks, embeddings, save=False)

    # -------------------------------------------------------------
    # 7. Save Index Once at the End
    # -------------------------------------------------------------
    if urls_to_remove or all_chunks:
        print("Saving FAISS index, metadata, and BM25 index...")
        vstore.save()
        cleared = db.clear_answer_cache()
        print(f"Answer cache cleared ({cleared} entries removed) due to knowledge base update.")

    # -------------------------------------------------------------
    # 8. Assert Consistency
    # -------------------------------------------------------------
    if vstore.index is not None:
        assert vstore.index.ntotal == len(vstore.metadata), (
            f"FAISS index vectors ({vstore.index.ntotal}) and metadata items ({len(vstore.metadata)}) out of sync!"
        )

    print(f"\nIngestion Complete. Index total vectors: {vstore.index.ntotal if vstore.index else 0}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "new_count": len(new_items),
        "modified_count": len(modified_items),
        "removed_count": len(removed_items),
        "unchanged_count": len(unchanged_items),
        "total_chunks": vstore.index.ntotal if vstore.index else 0,
        "new": new_items,
        "modified": modified_items,
        "removed": removed_items,
        "unchanged": unchanged_items
    }
    return report

if __name__ == "__main__":
    run_ingestion()
