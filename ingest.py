import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tqdm import tqdm
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

def run_ingestion():
    print("Initializing Database, Chunker, Embedder, and VectorStore...")
    db = DatabaseManager()
    chunker = DocumentChunker()
    embedder = Embedder()
    vstore = VectorStore(dimension=embedder.dimension)
    pdf_processor = PDFProcessor()
    syllabus_parser = SyllabusParser()

    # Build set of already indexed URLs to skip them (Incremental Update)
    existing_urls = {meta.get("source_url") for meta in vstore.metadata if "source_url" in meta}
    print(f"Index currently holds chunks for {len(existing_urls)} unique URLs.")

    # 1. Process Website Pages from Database
    pages = db.get_all_current_pages()
    pages_to_process = [p for p in pages if p['source_url'] not in existing_urls]
    print(f"Found {len(pages_to_process)} new/modified web pages out of {len(pages)} to ingest.")
    
    all_chunks = []
    for page in tqdm(pages_to_process, desc="Chunking Pages"):
        chunks = chunker.chunk_page(page)
        all_chunks.extend(chunks)
        
    # 2. Process Crawled Documents (PDFs) from Database
    documents = db.get_all_documents()
    docs_to_process = [d for d in documents if d['document_url'] not in existing_urls]
    print(f"Found {len(docs_to_process)} new/modified crawled documents out of {len(documents)} to ingest.")
    
    for doc in tqdm(docs_to_process, desc="Processing Crawled Docs"):
        # Only process PDFs
        url = doc['document_url'].lower()
        if not url.endswith('.pdf'):
            continue
            
        # Download if not already downloaded
        filepath_str = doc.get("filepath")
        filepath = Path(filepath_str) if filepath_str else None
        
        if not filepath or not filepath.exists():
            print(f"\nDownloading {doc['document_url']}...")
            filepath = pdf_processor.download_pdf(doc['document_url'])
            if filepath:
                doc['filepath'] = str(filepath)
                doc['status'] = 'downloaded'
                db.upsert_document(doc)
                
        if filepath and filepath.exists():
            pages_text = pdf_processor.extract_text_from_pdf(filepath)
            doc_metadata = {
                "source_url": doc['document_url'],
                "title": doc.get('title') or doc.get('link_text') or filepath.stem,
                "category": doc.get('category', 'Document'),
                "department": doc.get('department', 'General'),
                "version": doc.get('version', 1),
                "is_current": 1,
                "link_text": doc.get('link_text', '')
            }
            
            # Syllabus parsing
            if is_syllabus_pdf(doc):
                print(f"Parsing syllabus for {doc['document_url']}...")
                for p in pages_text:
                    if len(p['content'].strip()) > 100:
                        syllabus_entries = syllabus_parser.parse_page(
                            page_text=p['content'], 
                            page_num=p['page_num'], 
                            doc_url=doc['document_url'], 
                            doc_metadata=doc_metadata
                        )
                        for entry in syllabus_entries:
                            db.upsert_syllabus(entry)
            
            pdf_chunks = chunker.chunk_pdf(doc_metadata, pages_text)
            all_chunks.extend(pdf_chunks)

    # 3. Process Manually Dropped PDFs in data/pdf/
    manual_pdfs = list(config.PDF_DATA_DIR.glob("*.pdf"))
    if manual_pdfs:
        print(f"Found {len(manual_pdfs)} local PDFs in {config.PDF_DATA_DIR}")
        for pdf_path in tqdm(manual_pdfs, desc="Processing Manual PDFs"):
            # Skip if it matches a downloaded crawler PDF (they might be in the same dir)
            if any(doc.get("filepath") == str(pdf_path) for doc in documents):
                continue
                
            pages_text = pdf_processor.extract_text_from_pdf(pdf_path)
            
            # Simple metadata for manual PDFs
            pdf_metadata = {
                "source_url": f"file://{pdf_path.name}",
                "title": pdf_path.stem,
                "category": "Manual PDFs",
                "department": "General",
                "version": 1,
                "is_current": 1,
            }
            pdf_chunks = chunker.chunk_pdf(pdf_metadata, pages_text)
            all_chunks.extend(pdf_chunks)
            
    if not all_chunks:
        print("No chunks to process. Exiting.")
        return

    print(f"\nTotal chunks generated: {len(all_chunks)}")
    
    # Process in batches to avoid memory issues with Embedder
    batch_size = 32
    print(f"Embedding and storing chunks in FAISS (Batch Size: {batch_size})...")
    
    for i in tqdm(range(0, len(all_chunks), batch_size), desc="Embedding"):
        batch_chunks = all_chunks[i:i+batch_size]
        batch_texts = [c["content"] for c in batch_chunks]
        
        embeddings = embedder.embed_batch(batch_texts)
        vstore.add_chunks(batch_chunks, embeddings)
        
    print(f"\nIngestion Complete. FAISS index saved with {vstore.index.ntotal} total vectors.")
    print(f"Test retrieval using: python -c \"from src.vectorstore import VectorStore; from src.embeddings import Embedder; e=Embedder(); v=VectorStore(e.dimension); print(v.search(e.embed_text('departments')))\"")

if __name__ == "__main__":
    run_ingestion()
