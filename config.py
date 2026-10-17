import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv(override=True)

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WEBSITE_DATA_DIR = DATA_DIR / "website"
PDF_DATA_DIR = DATA_DIR / "pdf"
NOTICES_DATA_DIR = DATA_DIR / "notices"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

VECTORSTORE_DIR = BASE_DIR / "vectorstore"
REPORTS_DIR = BASE_DIR / "reports"
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "gprec_knowledge.db")

# Crawler settings
TARGET_URL = "https://gprec.ac.in"
ALLOWED_DOMAINS = ["gprec.ac.in", "www.gprec.ac.in"]
MAX_PAGES = 300
CRAWL_DELAY = 0.1  # Rate limiting delay in seconds
REQUEST_TIMEOUT = 15
USER_AGENT = "GPREC-AI-Student-Assistant/1.0 (+https://gprec.ac.in)"

# Target sections to prioritize during crawling
SEED_URLS = [
    "https://gprec.ac.in",
    "https://gprec.ac.in/admissions/",
    "https://gprec.ac.in/academics/",
    "https://gprec.ac.in/departments/",
    "https://gprec.ac.in/examinations/",
    "https://gprec.ac.in/placements/",
    "https://gprec.ac.in/notices/",
    "https://gprec.ac.in/hostel/",
    "https://gprec.ac.in/library/",
    "https://gprec.ac.in/contact-us/",
    "https://www.gprec.ac.in/#news",
    "https://www.gprec.ac.in/#1599562280620-025adbdd-4e2c",
    "https://www.gprec.ac.in/#placements",
    "https://www.gprec.ac.in/#1602596887768-c0c86bce-8597",
    "https://www.gprec.ac.in/#1635491099493-cbefa893-94bd",
    
]

# Chunker settings
DEFAULT_CHUNK_SIZE = 600  # Tokens / words approx
DEFAULT_CHUNK_OVERLAP = 100

# Embedding settings
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# Vector Store settings
FAISS_INDEX_PATH = VECTORSTORE_DIR / "faiss_index.bin"
FAISS_METADATA_PATH = VECTORSTORE_DIR / "metadata.pkl"

# Retrieval settings
TOP_K = 15
HYBRID_SEMANTIC_WEIGHT = 0.7
HYBRID_BM25_WEIGHT = 0.3

# Category-specific update intervals (in hours)
UPDATE_INTERVALS = {
    "notices": 6,
    "examination": 6,
    "admissions": 6,
    "placements": 24,
    "academics": 48,
    "general": 168,  # Weekly
}

# LLM Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-2-9b-it:free")

# Important pages coverage configuration (Pages that must be indexed)
IMPORTANT_PAGES = [
    {"category": "leadership", "name": "Principal / Management", "url_patterns": ["principal", "management", "administration", "about-us"]},
    {"category": "about", "name": "About College", "url_patterns": ["about", "mandatory-disclosure"]},
    {"category": "departments", "name": "EEE Department", "url_patterns": ["electrical-and-electronics-engineering", "eee"]},
    {"category": "departments", "name": "ECE Department", "url_patterns": ["electronics-and-communication-engineering", "ece"]},
    {"category": "departments", "name": "CSE Department", "url_patterns": ["computer-science-and-engineering", "cse"]},
    {"category": "departments", "name": "ME Department", "url_patterns": ["mechanical-engineering", "mechanical"]},
    {"category": "departments", "name": "CE Department", "url_patterns": ["civil-engineering", "civil"]},
    {"category": "departments", "name": "H&S Department", "url_patterns": ["humanities-and-basic-sciences", "humanities", "h&s", "hbs"]},
    {"category": "hostel", "name": "Hostel (Boys/Girls)", "url_patterns": ["hostel"]},
    {"category": "library", "name": "Central Library", "url_patterns": ["library"]},
    {"category": "fees", "name": "Fee Structure", "url_patterns": ["fee", "admissions", "tuition"]},
    {"category": "examinations", "name": "Examinations / Timetable", "url_patterns": ["examination", "examcell", "exam"]},
    {"category": "placements", "name": "Training & Placements", "url_patterns": ["placement", "training-placement"]},
    {"category": "contact", "name": "Contact Us", "url_patterns": ["contact"]}
]
