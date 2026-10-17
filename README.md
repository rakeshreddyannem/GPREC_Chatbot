# GPREC AI Student Assistant

A specialized Retrieval-Augmented Generation (RAG) chatbot for **G. Pulla Reddy Engineering College (GPREC)**, answering student queries strictly grounded in official college sources, notifications, circulars, and departmental academic curricula.

---

## Key Features

- **Strict Source Grounding:** Prevents hallucinations by bounding responses strictly to verified college documents and web pages.
- **Hybrid Retrieval:** Integrates dense vector search (FAISS + sentence-transformers) with lexical search (BM25) for high-precision retrieval.
- **Notice & Circular Tracking:** Automated extraction and parsing of urgent examination schedules, results, and administrative circulars.
- **Interactive UI:** Modern Streamlit interface with categorized navigation (Ask AI, Urgent Notices, Deadlines, Academics, and Admin Dashboard).
- **Multiple LLM Backends:** Flexible support for OpenRouter (e.g., Gemma 2, Llama 3) and Google Gemini.

---

## Project Structure

```
├── app.py                      # Main Streamlit web application
├── config.py                   # Central configuration & crawl settings
├── ingest.py                   # Knowledge base chunking & vector indexing pipeline
├── update_knowledge_base.py    # Periodic updater script
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment configuration
├── .gitignore                  # Git ignore rules
├── gprec_logo1.png             # UI branding asset
├── src/                        # Core system modules
│   ├── crawler.py              # Web crawler with rate limiting & deduplication
│   ├── change_detector.py      # Content change detection (NEW/MODIFIED/UNCHANGED)
│   ├── chunker.py              # Semantic & token-aware text chunking
│   ├── database.py             # SQLite database manager & schema
│   ├── embeddings.py           # Text embedding generator (Sentence-Transformers/Gemini)
│   ├── extractor.py            # HTML content extraction and sanitization
│   ├── notice_parser.py        # Circular & notice structural parser
│   ├── pdf_loader.py           # PDF text & table extractor
│   ├── rag_pipeline.py         # Prompt engineering, retrieval & LLM generation
│   ├── reliability.py          # Hallucination checking & fallback guards
│   ├── syllabus_parser.py      # Course syllabus & curriculum parser
│   └── vectorstore.py          # FAISS index and BM25 hybrid vector store
├── ui/                         # Frontend presentation
│   ├── components.py           # Streamlit UI cards, headers & layouts
│   └── style.css               # Custom theme styling
├── tests/                      # Automated unit, integration & regression test suite
└── data/                       # Directory structure for crawled pages & documents
```

---

## Getting Started

### 1. Prerequisites
- **Python 3.10+**
- Git installed

### 2. Clone Repository & Setup Environment
```bash
git clone https://github.com/rakeshreddyannem/GPREC_Chatbot.git
cd GPREC_Chatbot

# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your API credentials:
- If using **OpenRouter** (Default):
  ```env
  LLM_PROVIDER=openrouter
  OPENROUTER_API_KEY=your_openrouter_api_key
  OPENROUTER_MODEL=google/gemma-2-9b-it:free
  ```
- If using **Gemini**:
  ```env
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=your_gemini_api_key
  GEMINI_MODEL=gemini-2.5-flash
  ```

### 4. Build Knowledge Base (Ingestion)
Initialize the database and run data ingestion to create the vector indices:
```bash
# Initialize SQLite database schema
python src/database.py

# Run ingestion pipeline (chunks crawled data and creates FAISS index)
python ingest.py
```

### 5. Launch the Chatbot
Start the Streamlit application:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## Running Tests

Run the test suite using `pytest`:
```bash
pytest tests/
```

