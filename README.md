---
title: GPREC AI Student Assistant
emoji: 🎓
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# GPREC AI Student Assistant

A specialized Retrieval-Augmented Generation (RAG) assistant for **G. Pulla Reddy Engineering College (GPREC)**, answering student queries strictly grounded in official college sources, notifications, circulars, and departmental academic curricula.

---

## Key Features

- **Strict Source Grounding:** Prevents hallucinations by bounding responses strictly to verified college documents and web pages.
- **Hybrid Retrieval:** Integrates dense vector search (FAISS + sentence-transformers) with lexical search (BM25) for high-precision retrieval.
- **Notice & Circular Tracking:** Automated extraction and parsing of urgent examination schedules, results, and administrative circulars.
- **Subject & Syllabus Tutor:** Course syllabus explorer, doubt solver, and practice problem generator mapped to R20/R23 academic regulations.
- **Interactive UI:** Modern Streamlit interface with categorized navigation (Ask AI, Subject Assistance, Academics, Latest Notices, Deadlines, and Admin Dashboard).
- **Multiple LLM Backends:** Flexible support for OpenRouter (e.g., Gemma 2, Llama 3) and Google Gemini.
- **Production Hardened:** Per-session rate limiting, non-root Docker container, read-mostly resilient database handling, and container health checks.

---

## Deployment

### Option 1: Streamlit Community Cloud (Recommended)

1. Push this repository to GitHub (`main` branch).
2. Visit [share.streamlit.io](https://share.streamlit.io/) and click **New app**.
3. Select this repository (`rakeshreddyannem/GPREC_Chatbot`), branch `main`, and main file path `app.py`.
4. In **Advanced settings -> Secrets**, paste your configuration (refer to [.streamlit/secrets.toml.example](file:///.streamlit/secrets.toml.example)):
   ```toml
   LLM_PROVIDER = "openrouter"
   OPENROUTER_API_KEY = "your_openrouter_api_key_here"
   # Or for Gemini:
   # LLM_PROVIDER = "gemini"
   # GEMINI_API_KEY = "your_gemini_api_key_here"
   ADMIN_PASSWORD = "your_admin_password_here"
   ```
5. Click **Deploy!** OS-level dependencies (`libgomp1`) are automatically resolved via `packages.txt`, and Python packages via `requirements.txt`.

### Option 2: Hugging Face Spaces (Docker)

This Space is configured as a standalone Docker container running on port `7860`.

#### Required Environment Secrets
Configure these in your Hugging Face Space **Settings -> Variables and secrets**:

| Variable / Secret Name | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Optional | `openrouter` (default) or `gemini` |
| `OPENROUTER_API_KEY` | Optional* | API key from OpenRouter (*required if `LLM_PROVIDER=openrouter`) |
| `GEMINI_API_KEY` | Optional* | API key from Google AI Studio (*required if `LLM_PROVIDER=gemini`) |
| `LLM_MODEL` | Optional | Model identifier (defaults to `google/gemma-2-9b-it:free` or `gemini-2.5-flash`) |
| `ADMIN_PASSWORD` | Optional | Password protecting the `/admin` dashboard. If omitted, admin panel is disabled. |

---

## Project Structure

```
├── app.py                      # Main Streamlit web application
├── config.py                   # Central configuration & runtime settings
├── Dockerfile                  # Container definition for Hugging Face Spaces
├── .dockerignore               # Container build exclusions
├── .gitattributes              # Git LFS tracking rules for DB and vectorstore
├── requirements.txt            # Pinned runtime dependencies
├── requirements-dev.txt        # Development and testing dependencies
├── gprec_knowledge.db          # Knowledge base SQLite database (tracked with Git LFS)
├── vectorstore/                # FAISS index and metadata (tracked with Git LFS)
│   ├── faiss_index.bin
│   └── metadata.pkl
├── data/faculty_photos/        # Directory of departmental faculty photographs
├── gprec_logo1.png             # College branding asset
├── deploy/                     # Packaging scripts for deployment
│   └── scripts/
│       ├── make_deploy_bundle.sh
│       └── make_deploy_bundle.ps1
├── src/                        # Core system modules
│   ├── crawler.py              # Web crawler with rate limiting & deduplication
│   ├── database.py             # SQLite database manager & schema
│   ├── embeddings.py           # Text embedding generator (sentence-transformers)
│   ├── rag_pipeline.py         # Prompt engineering, retrieval & LLM generation
│   ├── reliability.py          # Hallucination checking & fallback guards
│   ├── subject_assistant.py    # Academic doubt tutor & syllabus assistant
│   └── vectorstore.py          # FAISS index and BM25 hybrid vector store
├── ui/                         # Frontend presentation
│   ├── components.py           # Streamlit UI cards, headers & layouts
│   └── style.css               # Custom theme styling
└── tests/                      # Automated unit, integration & regression test suite
```

---

## Local Development & Testing

### 1. Setup Virtual Environment
```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and provide your API keys:
```bash
cp .env.example .env
```

### 3. Launch Local Streamlit Server
```bash
streamlit run app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true
```
Open your browser at `http://localhost:7860`.

### 4. Run Docker Locally
```bash
docker build -t gprec-chatbot:latest .
docker run -p 7860:7860 -e OPENROUTER_API_KEY="your_key" gprec-chatbot:latest
```

---

## Disclaimer
Student project for academic reference. Always verify critical examination notices, fee dates, and results on the [official GPREC website](https://gprec.ac.in).
