import re
from typing import List, Dict, Any

import config

from .data_quality import BoilerplateCleaner, SectionTitleExtractor, ChunkDeduplicator

class DocumentChunker:
    def __init__(self, chunk_size: int = config.DEFAULT_CHUNK_SIZE, overlap: int = config.DEFAULT_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split_text(self, text: str) -> List[str]:
        """Simple word-based splitting with overlap."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + self.chunk_size])
            chunks.append(chunk)
            i += self.chunk_size - self.overlap
            if i < 0: 
                break
        return chunks

    def chunk_page(self, page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Cleans boilerplate, splits page content into chunks, adds section titles, and deduplicates."""
        raw_text = page_data.get("clean_text", "")
        if not raw_text:
            return []

        # 1. Clean boilerplate (headers, footers, social media, cookie notices)
        clean_text = BoilerplateCleaner.clean_text(raw_text)
        if not clean_text:
            clean_text = raw_text

        chunks_text = self.split_text(clean_text)
        chunk_docs = []
        base_title = page_data.get("title", "")
        source_url = page_data.get("source_url", "")

        for idx, c_text in enumerate(chunks_text):
            # 2. Derive section-level title
            section_title = SectionTitleExtractor.derive_title(base_title, c_text, source_url)

            chunk_doc = {
                "chunk_id": f"{source_url}#chunk{idx}",
                "source_url": source_url,
                "title": section_title,
                "category": page_data.get("category", ""),
                "department": page_data.get("department", ""),
                "published_date": page_data.get("published_date", ""),
                "last_checked": page_data.get("last_checked", ""),
                "content_hash": page_data.get("content_hash", ""),
                "version": page_data.get("version", 1),
                "is_current": page_data.get("is_current", 1),
                "content": c_text
            }
            chunk_docs.append(chunk_doc)

        # 3. Deduplicate by content hash and near-duplicate similarity (Jaccard > 0.85)
        return ChunkDeduplicator.deduplicate_chunks(chunk_docs)

    def chunk_pdf(self, pdf_metadata: Dict[str, Any], pages_text: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Splits PDF pages into chunks and attaches metadata."""
        chunk_docs = []
        for p in pages_text:
            page_num = p["page_num"]
            content = p["content"]
            
            if not content:
                continue
                
            chunks_text = self.split_text(content)
            for idx, c_text in enumerate(chunks_text):
                chunk_doc = {
                    "chunk_id": f"{pdf_metadata['source_url']}#page{page_num}_chunk{idx}",
                    "source_url": pdf_metadata["source_url"],
                    "title": pdf_metadata.get("title", f"PDF Document"),
                    "page": page_num,
                    "category": pdf_metadata.get("category", "PDFs"),
                    "department": pdf_metadata.get("department", "General"),
                    "published_date": pdf_metadata.get("published_date", ""),
                    "last_checked": pdf_metadata.get("last_checked", ""),
                    "content_hash": pdf_metadata.get("content_hash", ""),
                    "version": pdf_metadata.get("version", 1),
                    "is_current": pdf_metadata.get("is_current", 1),
                    "content": c_text
                }
                chunk_docs.append(chunk_doc)
                
        return ChunkDeduplicator.deduplicate_chunks(chunk_docs)
