import os
import re
import sys
import time
import logging
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, quote, unquote, urljoin
from typing import Dict, Any, List, Optional, Tuple

import hashlib
import requests
from bs4 import BeautifulSoup
import fitz # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.database import DatabaseManager

logger = logging.getLogger(__name__)

ROMAN_MAP = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
    'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10
}


class SyllabusParser:
    """Compatibility wrapper around syllabus parsing functionality for ingest pipeline."""
    def __init__(self):
        api_key = getattr(config, "OPENROUTER_API_KEY", "")
        if api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                )
            except Exception:
                self.client = None
        else:
            self.client = None

    def extract_metadata_from_text(self, text: str, url: str, link_text: str) -> Dict[str, Any]:
        """Extract Regulation and Branch from text/url/link_text."""
        reg_match = re.search(r'\b(R[1-2][0-9])\b', text + url + link_text, re.IGNORECASE)
        regulation = reg_match.group(1).upper() if reg_match else "UNKNOWN"
        branch = "UNKNOWN"
        for b in ["CSE", "ECE", "EEE", "ME", "CE", "CSM", "CSD", "CSB"]:
            if re.search(r'\b' + b + r'\b', text + url + link_text, re.IGNORECASE):
                branch = b
                break
        return {"regulation": regulation, "branch": branch}

    def parse_page(self, page_text: str, page_num: int, doc_url: str, doc_metadata: Dict[str, str]) -> List[Dict[str, Any]]:
        """Parse page text using LLM if available, returning extracted syllabus entries."""
        if not self.client or len(page_text.strip()) < 100:
            return []
        import json
        prompt = f"""
You are an expert at extracting engineering college syllabus data.
Extract the syllabus units and subjects from the following text (Page {page_num} of a document).
Context: URL={doc_url}, LinkText={doc_metadata.get('link_text', '')}

Return the data as a JSON list of objects ONLY. Do not include markdown formatting or backticks. Each object should have:
- regulation (string, e.g. R20, R23)
- branch (string, e.g. CSE, ECE)
- year (integer, e.g. 1, 2, 3, 4, or null)
- semester (integer, e.g. 1, 2, or null)
- academic_year (string or null)
- course_code (string or null)
- course_title (string)
- category (string, e.g. Core, Elective, Lab, or null)
- credits (string or null)
- ltp (string, e.g. 3-0-0, or null)
- unit_number (integer or null)
- unit_title (string or null)
- topics (string, detailed topics in the unit)
- textbooks (string or null)
- outcomes (string or null)
- exam_scheme (string or null)
- needs_review (integer: 1 if you are guessing or uncertain, 0 if it is clearly stated)

If this page does not contain a syllabus (e.g. it is just a cover page, index, or general rules), return an empty list [].
Do not invent information.

TEXT:
{page_text}
"""
        try:
            response = self.client.chat.completions.create(
                model=getattr(config, "OPENROUTER_MODEL", "openrouter/free"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2000
            )
            text_resp = response.choices[0].message.content.strip()
            if text_resp.startswith("```json"):
                text_resp = text_resp[7:]
            if text_resp.startswith("```"):
                text_resp = text_resp[3:]
            if text_resp.endswith("```"):
                text_resp = text_resp[:-3]
            text_resp = text_resp.strip()
            result = json.loads(text_resp)
            if isinstance(result, list):
                for item in result:
                    item['page_num'] = page_num
                    item['document_url'] = doc_url
                return result
            return []
        except Exception as e:
            logger.debug(f"Error in LLM syllabus parsing for page {page_num}: {e}")
            return []


# --- 1. Safe URL Encoding & Normalization ---

def safe_url_encode(url: str) -> str:
    """Percent-encodes the path (urllib.parse.quote with safe='/:%') before downloading.
    Guarantees that pre-encoded paths are never double-encoded.
    """
    if not url:
        return ""
    parts = urlsplit(url)
    raw_path = unquote(parts.path)
    encoded_path = quote(raw_path, safe='/:%')
    raw_query = unquote(parts.query) if parts.query else ""
    encoded_query = quote(raw_query, safe='=&?/%') if raw_query else ""
    return urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, parts.fragment))

def clean_text(t: Optional[str]) -> Optional[str]:
    """Normalizes whitespace and dashes in extracted text."""
    if not t:
        return None
    t = re.sub(r'[ \t]+', ' ', t)
    t = t.replace('–', '-').replace('—', '-').replace('\u2015', '-').replace('\u2013', '-').replace('\u2014', '-')
    t = t.strip()
    return t if t else None

# --- 2. Link Classification ---

def classify_syllabus_link(link_text: str, href: str, context_text: str, branch: str) -> Dict[str, Any]:
    """Classifies a hyperlink into program, scheme, kind, status, and reason."""
    href_lower = href.lower()
    link_lower = link_text.lower()
    combo = f"{link_text} {context_text} {href}".lower()
    
    # 1. Program: B.Tech vs M.Tech
    if any(k in href_lower or k in link_lower for k in ["m.tech", "mtech", "pg_", "m. tech"]):
        program = "M.Tech"
    elif any(k in combo for k in ["post graduate", "power electronics", "structural engineering", "automation and robotics", "advanced manufacturing"]):
        program = "M.Tech"
    elif any(k in link_lower or k in href_lower for k in ["b.tech", "btech", "ug"]):
        program = "B.Tech"
    elif "m.tech" in context_text.lower() and "b.tech" not in context_text.lower():
        program = "M.Tech"
    else:
        program = "B.Tech"

    # 2. Scheme (2010, 2013, 2017, 2020, 2022, 2023, 2025, 2026)
    scheme = "UNKNOWN"
    direct_text = f"{link_text} {href}".lower()
    scheme_match = re.search(r'\b(2010|2013|2017|2020|2022|2023|2025|2026)\b', direct_text)
    if scheme_match:
        scheme = scheme_match.group(1)
    else:
        short_match = re.search(r'\bs[-_ ]?(10|13|17|20|22|23|25|26)\b', direct_text)
        if short_match:
            scheme = "20" + short_match.group(1)
        else:
            ctx_match = re.search(r'\b(2010|2013|2017|2020|2022|2023|2025|2026)\b', context_text)
            if ctx_match:
                scheme = ctx_match.group(1)
            else:
                ctx_short = re.search(r'\bs[-_ ]?(10|13|17|20|22|23|25|26)\b', context_text.lower())
                scheme = "20" + ctx_short.group(1) if ctx_short else "UNKNOWN"

    # 3. Kind: regulations, first_year, upper_years, minor, honors, mooc, other
    if any(k in href_lower or k in link_lower for k in ["regulation", "regu", "regulations"]):
        kind = "regulations"
    elif "regulation" in context_text.lower() and "syllabus" not in href_lower and "syllabus" not in link_lower:
        kind = "regulations"
    elif any(k in href_lower or k in link_lower for k in ["mooc", "moocs", "massive open online"]):
        kind = "mooc"
    elif any(k in href_lower or k in link_lower for k in ["minor", "minors"]):
        kind = "minor"
    elif any(k in href_lower or k in link_lower for k in ["honor", "honors"]):
        kind = "honors"
    elif re.search(r'(?<![a-z])(?:i\s*b\.?tech|i-b\.?tech|1st\s*year|first\s*year|first-sem)(?![a-z])', direct_text, re.I):
        kind = "first_year"
    elif any(k in direct_text for k in ["ii year", "iii year", "iv year", "ii-year", "iii-year", "iv-year", "v semester", "iii,iv", "iii-iv", "ii, iii, iv", "iv- b.tech"]):
        kind = "upper_years"
    elif re.search(r'(?<![a-z])(?:i\s*b\.?tech|i-b\.?tech|1st\s*year|first\s*year)(?![a-z])', context_text, re.I) and not any(k in direct_text for k in ["ii", "iii", "iv", "v semester"]):
        kind = "first_year"
    elif any(k in direct_text for k in ["syllabus", "curriculam", "structure"]):
        kind = "upper_years"
    elif any(k in combo for k in ["ii", "iii", "iv", "v semester", "upper", "syllabus", "curriculam", "structure"]):
        kind = "upper_years"
    elif any(k in context_text.lower() for k in ["mooc", "moocs", "massive open online"]):
        kind = "mooc"
    elif "minor" in context_text.lower():
        kind = "minor"
    elif any(k in context_text.lower() for k in ["honor", "honors"]):
        kind = "honors"
    else:
        kind = "other"

    # 4. Status & Reason
    href_lower = href.lower()
    if href_lower.endswith((".doc", ".docx")):
        status = "skipped"
        reason = "Word document (.doc/.docx)"
    elif program != "B.Tech":
        status = "skipped"
        reason = f"M.Tech program ({program})"
    elif scheme not in ("2020", "2023", "2026"):
        status = "skipped"
        reason = f"Older scheme (< 2020): Scheme-{scheme}"
    elif kind in ("minor", "honors", "mooc", "other"):
        status = "skipped"
        reason = f"{kind.capitalize()} program (not parsed into core subjects)"
    elif kind == "regulations":
        status = "found"
        reason = "Regulations document (eligible for QA download)"
    elif kind in ("first_year", "upper_years"):
        status = "found"
        reason = "Eligible for subject syllabus parsing"
    else:
        status = "skipped"
        reason = f"Unhandled kind: {kind}"

    return {
        "branch": branch,
        "program": program,
        "scheme": scheme,
        "kind": kind,
        "link_text": link_text.strip(),
        "url": href.strip(),
        "status": status,
        "reason": reason
    }

# --- 3. Scrape Department Syllabus Links ---

def scrape_department_syllabus_links(dept_url: str, branch: str, db: DatabaseManager) -> List[Dict[str, Any]]:
    """Finds the Syllabus section (#syllabus) on a department page, extracts all hyperlinks,
    classifies them, and stores all rows in syllabus_sources table.
    """
    logger.info(f"Scraping syllabus links for {branch} from {dept_url}")
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        resp = session.get(dept_url, headers=headers, timeout=25)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.error(f"Failed to fetch department page {dept_url}: {e}")
        return []

    syllabus_container = soup.find(id="syllabus")
    if not syllabus_container:
        # Fallback to anchor name="syllabus"
        a_tag = soup.find("a", attrs={"name": "syllabus"})
        if a_tag:
            syllabus_container = a_tag.find_parent(["div", "section"])
    if not syllabus_container:
        # Fallback: look for vc_tta-panel with text containing Syllabus
        for panel in soup.find_all("div", class_="vc_tta-panel"):
            if "syllabus" in panel.get_text().lower():
                syllabus_container = panel
                break

    if not syllabus_container:
        logger.warning(f"Could not find #syllabus section on {dept_url}")
        return []

    body = syllabus_container.find("div", class_="vc_tta-panel-body") or syllabus_container
    all_a_tags = body.find_all("a")
    
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    results = []

    for a in all_a_tags:
        raw_href = a.get("href", "").strip()
        link_text = a.get_text(strip=True)
        if not raw_href or raw_href.startswith("#"):
            continue
            
        full_url = urljoin(dept_url, raw_href)
        
        # Context extraction: check parent paragraph, heading, or block
        parent_p = a.find_parent(["p", "div", "li", "td", "h1", "h2", "h3", "h4", "h5", "h6"])
        context_text = parent_p.get_text(separator=' ', strip=True) if parent_p else ""
        
        # Find preceding heading
        heading_text = ""
        for prev in a.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6"]):
            txt = prev.get_text(strip=True)
            if txt and len(txt) < 80:
                heading_text = txt
                break
        combined_context = f"{heading_text} - {context_text}"

        classification = classify_syllabus_link(link_text, full_url, combined_context, branch)
        classification["last_checked"] = now_str
        classification["local_path"] = None

        db.upsert_syllabus_source(classification)
        results.append(classification)

    # Fetch latest stored state from database to preserve content_hash, status, and local_path
    db_sources = {s["url"]: s for s in db.get_syllabus_sources(branch=branch)}
    merged_results = [db_sources.get(r["url"], r) for r in results]
    logger.info(f"Recorded {len(merged_results)} syllabus sources for {branch}")
    return merged_results

# --- 4. Layout Parsers & Registry ---

def parse_scheme_2023_layout(pdf_path: Path, doc_url: str, default_branch: str, scheme: str = "2023") -> List[Dict[str, Any]]:
    """Standard layout parser for Scheme-2023 PDFs (PyMuPDF)."""
    doc = fitz.open(str(pdf_path))
    page_course_starts = []
    
    for pno in range(len(doc)):
        page = doc[pno]
        txt = page.get_text()
        lines = [l.strip() for l in txt.split('\n') if l.strip()]
        if not lines:
            continue
            
        # Skip purely scheme of instruction pages without course outcomes or units
        if any("scheme of instruction and examination" in l.lower() for l in lines[:10]) and not any("course outcomes" in l.lower() for l in lines):
            continue
            
        sem_idx = None
        sem_num = None
        for i in range(min(15, len(lines))):
            m = re.search(r'\b(VIII|VII|VI|IV|V|III|II|I)\s+Semester\b', lines[i], re.I)
            if m:
                l_lower = lines[i].lower()
                if any(k in l_lower for k in [default_branch.lower(), "eee", "cse", "ece", "me", "ce", "scheme", "common", "branch", "category", ":"]):
                    sem_idx = i
                    sem_num = ROMAN_MAP.get(m.group(1).upper(), 1)
                    break
                    
        if sem_idx is not None:
            title = None
            if sem_idx > 0:
                for k in range(sem_idx - 1, -1, -1):
                    cand = lines[k]
                    if any(ig in cand.lower() for ig in ["g. pulla", "autonomous", "accredited", "department of", "degree course"]):
                        continue
                    if cand.strip().startswith("[") and cand.strip().endswith("]"):
                        continue
                    if cand.strip() == "[":
                        continue
                    title = cand
                    break
            if not title and len(lines) > 0:
                title = lines[0]
                
            if sem_idx > 1 and lines[sem_idx - 1].startswith("(") and lines[sem_idx - 1].endswith(")"):
                if title and lines[sem_idx - 1] not in title:
                    title = title + " " + lines[sem_idx - 1]
                    
            code = None
            for j in range(sem_idx, min(len(lines), sem_idx + 25)):
                m = re.search(r'\b([A-Z]{2,6}[- ]?\d{2,4}[A-Z]?)\b', lines[j])
                if m:
                    cand_code = re.sub(r'[\s\-]', '', m.group(1))
                    if cand_code not in ["AICTE", "NAAC", "NBA", "JNTUA", "KURNOOL", "TOTAL", "GPREC", "IEEE", "UGC", "CIA"]:
                        code = cand_code
                        break
                        
            page_course_starts.append({
                "page_num": pno + 1,
                "title": clean_text(title),
                "code": code,
                "sem": sem_num
            })
            
    entries = []
    
    for idx, cinfo in enumerate(page_course_starts):
        start_p = cinfo["page_num"] - 1
        end_p = page_course_starts[idx + 1]["page_num"] - 1 if idx + 1 < len(page_course_starts) else len(doc)
        
        course_text = ""
        for p in range(start_p, end_p):
            course_text += doc[p].get_text() + "\n"
            
        title = cinfo["title"]
        code = cinfo["code"]
        sem = cinfo["sem"]
        year = (sem + 1) // 2 if sem else 1
        
        # Check if Year 1 or common
        branch = "COMMON" if ("common" in course_text[:400].lower() or year == 1) else default_branch
        
        # Category
        cat_match = re.search(r'Category\s*\n+([A-Za-z0-9\s&]+?)\n+(?:Hours|Credits|L|Course)', course_text, re.I)
        category = None
        if cat_match:
            category = clean_text(cat_match.group(1))
            if category and "course" in category.lower():
                category = re.sub(r'course.*', '', category, flags=re.I).strip()
        if not category:
            m = re.search(r'\b(BS|ES|PC|HSMC|SC|OE|PE|AC|PCC|BSC|ESC|MC)\b', course_text[:1000])
            if m:
                category = m.group(1).strip()
                
        # LTP & Credits
        ltp = None
        credits = None
        ltp_match = re.search(r'\bL\s*\n\s*T\s*\n\s*P\s*\n\s*C\s*\n(?:[^\n]*\n){0,10}?(\d+)\s*\n\s*(\d+)\s*\n\s*(\d+)\s*\n\s*(\d+(?:\.\d+)?)', course_text)
        if ltp_match:
            l, t, p, c = ltp_match.groups()
            ltp = f"{l}-{t}-{p}"
            credits = c
        else:
            alt_ltp = re.search(r'\n([0-9\-]+)\s+([0-9\-]+)\s+([0-9\-]+)\s+([0-9]+(?:\.[0-9]+)?)\s*\n', course_text[:1200])
            if alt_ltp:
                l, t, p, c = alt_ltp.groups()
                l = '0' if l == '-' else l
                t = '0' if t == '-' else t
                p = '0' if p == '-' else p
                ltp = f"{l}-{t}-{p}"
                credits = c
                
        # Outcomes
        outcomes = None
        co_match = re.search(r'Course Outcomes\s*:?\s*(.*?)(?=\bUNIT\s*[-–—]\s*[I|V|1]|List of Experiments|\bText Books\b)', course_text, re.S | re.I)
        if co_match:
            outcomes = clean_text(co_match.group(1))
            
        # Textbooks
        tb_txt = None
        ref_txt = None
        tb_match = re.search(r'Text Books?\s*:?\s*(.*?)(?=\bReference Books?\b|\bWeb References\b|\bQuestion Paper Pattern\b|$)', course_text, re.S | re.I)
        if tb_match:
            tb_txt = clean_text(tb_match.group(1))
        ref_match = re.search(r'Reference Books?\s*:?\s*(.*?)(?=\bWeb References\b|\bQuestion Paper Pattern\b|$)', course_text, re.S | re.I)
        if ref_match:
            ref_txt = clean_text(ref_match.group(1))
            
        tb_parts = []
        if tb_txt:
            tb_parts.append(tb_txt)
        if ref_txt:
            tb_parts.append(f"Reference Books:\n{ref_txt}")
        textbooks = "\n\n".join(tb_parts) if tb_parts else None

        # Exam Scheme
        exam_scheme = None
        ex_m = re.search(r'Continuous\s*Internal\s*Assessment\s*End\s*Exam\s*Total\s*\n*(?:[^\n]*\n){0,3}?(\d+)\s+(\d+)\s+(\d+)', course_text)
        if ex_m:
            cia, end, tot = ex_m.groups()
            exam_scheme = f"Continuous Internal Assessment: {cia}, End Exam: {end}, TOTAL: {tot}"
            
        # Units
        units = []
        unit_splits = list(re.finditer(r'\bUNIT\s*[-–—]\s*([I|V|X]+|\d+)\b', course_text, re.I))
        if unit_splits:
            for u_idx, u_match in enumerate(unit_splits):
                u_num_raw = u_match.group(1).upper()
                u_num = ROMAN_MAP.get(u_num_raw, int(u_num_raw) if u_num_raw.isdigit() else u_idx + 1)
                start_pos = u_match.end()
                end_pos = unit_splits[u_idx + 1].start() if u_idx + 1 < len(unit_splits) else len(course_text)
                
                u_block = course_text[start_pos:end_pos]
                u_block = re.split(r'\b(?:Text Books?|Reference Books?|Question Paper Pattern|Web References)\b', u_block, flags=re.I)[0]
                u_lines = [l.strip() for l in u_block.split('\n') if l.strip()]
                
                u_title = None
                u_topics = ""
                if u_lines:
                    u_title = u_lines[0]
                    u_topics = " ".join(u_lines[1:])
                units.append({
                    "unit_number": u_num,
                    "unit_title": clean_text(u_title),
                    "topics": clean_text(u_topics)
                })

        base_needs_review = 1 if (not code or not title or not credits or not ltp or not outcomes or not textbooks) else 0

        if units:
            for u in units:
                entries.append({
                    "branch": branch,
                    "regulation": scheme,
                    "year": year,
                    "semester": sem,
                    "course_code": code,
                    "course_title": title,
                    "category": category,
                    "credits": credits,
                    "ltp": ltp,
                    "unit_number": u["unit_number"],
                    "unit_title": u["unit_title"],
                    "topics": u["topics"],
                    "textbooks": textbooks,
                    "outcomes": outcomes,
                    "exam_scheme": exam_scheme,
                    "document_url": doc_url,
                    "page_num": cinfo["page_num"],
                    "needs_review": base_needs_review if (u["unit_title"] and u["topics"]) else 1
                })
        else:
            exp_text = None
            exp_match = re.search(r'List of Experiments\s*(.*?)(?=\bText Books?\b|\bReference Books?\b|\bQuestion Paper Pattern\b|$)', course_text, re.S | re.I)
            if exp_match:
                exp_text = clean_text(exp_match.group(1))
            entries.append({
                "branch": branch,
                "regulation": scheme,
                "year": year,
                "semester": sem,
                "course_code": code,
                "course_title": title,
                "category": category,
                "credits": credits,
                "ltp": ltp,
                "unit_number": None,
                "unit_title": None,
                "topics": exp_text or clean_text(course_text[:500]),
                "textbooks": textbooks,
                "outcomes": outcomes,
                "exam_scheme": exam_scheme,
                "document_url": doc_url,
                "page_num": cinfo["page_num"],
                "needs_review": 1
            })
            
    return entries

# Registry keyed by (branch, scheme)
LAYOUT_REGISTRY: Dict[Tuple[str, str], Any] = {
    # Default fallbacks
    ("*", "2023"): parse_scheme_2023_layout,
    ("*", "2020"): parse_scheme_2023_layout, # S-20 uses identical structure
    ("*", "2026"): parse_scheme_2023_layout,
}

def get_parser(branch: str, scheme: str):
    """Retrieves layout parser from registry, falling back to scheme-level default."""
    if (branch, scheme) in LAYOUT_REGISTRY:
        return LAYOUT_REGISTRY[(branch, scheme)]
    if ("*", scheme) in LAYOUT_REGISTRY:
        return LAYOUT_REGISTRY[("*", scheme)]
    return parse_scheme_2023_layout

def parse_pdf_syllabus(pdf_path: Path, doc_url: str, branch: str, scheme: str) -> List[Dict[str, Any]]:
    """Dispatches to the registered layout parser for the given (branch, scheme)."""
    parser_func = get_parser(branch, scheme)
    return parser_func(pdf_path, doc_url, branch, scheme)

# --- 5. Download and Ingest ---

def download_syllabus_file(url: str, target_dir: Path) -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """Downloads a syllabus file with safe URL encoding. Returns (local_path, content_hash, error_str)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    enc_url = safe_url_encode(url)
    filename = Path(unquote(urlsplit(url).path)).name
    local_file = target_dir / filename
    
    # If already downloaded, check hash
    if local_file.exists():
        try:
            with open(local_file, "rb") as f:
                content = f.read()
            content_hash = hashlib.sha256(content).hexdigest()
            return local_file, content_hash, None
        except Exception:
            pass

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(enc_url, headers=headers, timeout=35)
        if resp.status_code == 200:
            content_hash = hashlib.sha256(resp.content).hexdigest()
            with open(local_file, "wb") as f:
                f.write(resp.content)
            return local_file, content_hash, None
        else:
            return None, None, f"HTTP status {resp.status_code}"
    except Exception as e:
        return None, None, str(e)

def ingest_syllabus_source(db: DatabaseManager, source: Dict[str, Any], embed: bool = True) -> Dict[str, Any]:
    """Processes a single syllabus source row:
    - If skipped: leaves as skipped.
    - If regulations: downloads PDF, sets status 'downloaded' (not parsed into subjects).
    - If first_year / upper_years: downloads PDF, parses into syllabus table, and embeds chunks.
    - Uses content_hash to avoid re-parsing unchanged PDFs.
    """
    url = source["url"]
    branch = source["branch"]
    scheme = source["scheme"]
    kind = source["kind"]
    status = source["status"]

    if status == "skipped":
        return {"status": "skipped", "reason": source.get("reason", "Skipped")}

    target_dir = config.DATA_DIR / "syllabus"
    local_path, content_hash, err = download_syllabus_file(url, target_dir)
    
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    if err or not local_path:
        db.upsert_syllabus_source({
            "branch": branch,
            "url": url,
            "program": source.get("program", "B.Tech"),
            "scheme": scheme,
            "kind": kind,
            "link_text": source.get("link_text", ""),
            "local_path": None,
            "content_hash": None,
            "status": "failed",
            "reason": f"Download failed: {err}",
            "last_checked": now_str
        })
        return {"status": "failed", "reason": err}

    # Content hash check: if already parsed with identical hash, skip re-parsing
    if source.get("content_hash") == content_hash and source.get("status") in ("parsed", "downloaded"):
        logger.info(f"Syllabus file {local_path.name} unchanged (hash {content_hash[:8]}), skipping re-parse")
        return {"status": "unchanged", "local_path": str(local_path), "content_hash": content_hash}

    # Regulations: keep as document for question answering, do not parse into subjects
    if kind == "regulations":
        db.upsert_syllabus_source({
            "branch": branch,
            "url": url,
            "program": source.get("program", "B.Tech"),
            "scheme": scheme,
            "kind": kind,
            "link_text": source.get("link_text", ""),
            "local_path": str(local_path),
            "content_hash": content_hash,
            "status": "downloaded",
            "reason": "Regulations document (kept for QA, not parsed into subjects)",
            "last_checked": now_str
        })
        return {"status": "downloaded", "local_path": str(local_path), "content_hash": content_hash}

    # Parse syllabus PDF into subjects
    try:
        entries = parse_pdf_syllabus(local_path, url, branch, scheme)
        inserted_count = 0
        for entry in entries:
            db.upsert_syllabus_entry(entry)
            inserted_count += 1
            
        db.upsert_syllabus_source({
            "branch": branch,
            "url": url,
            "program": source.get("program", "B.Tech"),
            "scheme": scheme,
            "kind": kind,
            "link_text": source.get("link_text", ""),
            "local_path": str(local_path),
            "content_hash": content_hash,
            "status": "parsed",
            "reason": f"Parsed {inserted_count} unit rows",
            "last_checked": now_str
        })

        # Chunk and embed into VectorStore
        if embed and entries:
            embed_syllabus_entries(entries)

        return {
            "status": "parsed",
            "entries_count": inserted_count,
            "local_path": str(local_path),
            "content_hash": content_hash
        }
    except Exception as e:
        logger.error(f"Error parsing PDF {local_path}: {e}", exc_info=True)
        db.upsert_syllabus_source({
            "branch": branch,
            "url": url,
            "program": source.get("program", "B.Tech"),
            "scheme": scheme,
            "kind": kind,
            "link_text": source.get("link_text", ""),
            "local_path": str(local_path),
            "content_hash": content_hash,
            "status": "failed",
            "reason": f"Parsing failed: {e}",
            "last_checked": now_str
        })
        return {"status": "failed", "reason": str(e)}

_EMBEDDER_INSTANCE = None
_VECTORSTORE_INSTANCE = None

def get_embedder_and_store():
    global _EMBEDDER_INSTANCE, _VECTORSTORE_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        from src.embeddings import Embedder
        from src.vectorstore import VectorStore
        _EMBEDDER_INSTANCE = Embedder()
        _VECTORSTORE_INSTANCE = VectorStore(dimension=_EMBEDDER_INSTANCE.dimension)
    return _EMBEDDER_INSTANCE, _VECTORSTORE_INSTANCE

def embed_syllabus_entries(entries: List[Dict[str, Any]]):
    """Chunks and embeds syllabus text into FAISS VectorStore with rich metadata."""
    if not entries:
        return
        
    try:
        embedder, store = get_embedder_and_store()
        
        # Build chunks
        chunks = []
        texts = []
        for e in entries:
            branch = e.get("branch")
            scheme = e.get("regulation")
            year = e.get("year")
            sem = e.get("semester")
            code = e.get("course_code") or "COURSE"
            title = e.get("course_title") or ""
            unit_no = e.get("unit_number")
            unit_title = e.get("unit_title") or ""
            topics = e.get("topics") or ""
            textbooks = e.get("textbooks") or ""
            outcomes = e.get("outcomes") or ""
            url = e.get("document_url") or ""
            
            unit_str = f"Unit {unit_no}: {unit_title}" if unit_no else "Course Syllabus & Lab Experiments"
            content = f"Department of {branch} Engineering - Scheme-{scheme} Year {year} Semester {sem}\n" \
                      f"Subject: {code} - {title}\n" \
                      f"{unit_str}\n" \
                      f"Topics: {topics}\n"
            if outcomes:
                content += f"Course Outcomes:\n{outcomes}\n"
            if textbooks:
                content += f"Textbooks & References:\n{textbooks}\n"
                
            chunk_meta = {
                "content": content,
                "source_url": url,
                "branch": branch,
                "scheme": scheme,
                "year": year,
                "semester": sem,
                "course_code": code,
                "course_title": title,
                "category": "syllabus"
            }
            chunks.append(chunk_meta)
            texts.append(content)
            
        # Batch embed and save
        batch_size = 64
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            emb = embedder.embed_batch(batch_texts)
            all_embeddings.append(emb)
            
        import numpy as np
        final_embeddings = np.vstack(all_embeddings)
        
        # Remove any existing syllabus chunks for this document URL to avoid duplicate embeddings
        urls_in_batch = set(e.get("document_url") for e in entries if e.get("document_url"))
        store.remove_by_urls(urls_in_batch, save=False)
        
        store.add_chunks(chunks, final_embeddings, save=True)
        logger.info(f"Embedded {len(chunks)} syllabus chunks into VectorStore")
    except Exception as e:
        logger.error(f"Error embedding syllabus entries: {e}", exc_info=True)

# --- 7. Report Generation ---

def generate_coverage_data(db: DatabaseManager, branch_filter: Optional[str] = None) -> Dict[str, Any]:
    """Computes syllabus coverage statistics:
    for each branch, scheme, year, semester: number of courses, number with units, number needing review.
    Also collects failed and skipped links.
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        branch_clause = "WHERE branch = ?" if branch_filter else ""
        params = [branch_filter] if branch_filter else []
        
        cursor.execute(f"""
            SELECT branch, regulation as scheme, year, semester,
                   COUNT(DISTINCT course_code) as num_courses,
                   COUNT(DISTINCT CASE WHEN unit_number IS NOT NULL THEN course_code END) as num_with_units,
                   COUNT(DISTINCT CASE WHEN needs_review = 1 THEN course_code END) as num_needing_review
            FROM syllabus
            {branch_clause}
            GROUP BY branch, regulation, year, semester
            ORDER BY branch, regulation, year, semester
        """, params)
        coverage_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute(f"""
            SELECT branch, program, scheme, kind, link_text, url, status, reason
            FROM syllabus_sources
            {branch_clause}
            ORDER BY branch, id
        """, params)
        all_sources = [dict(row) for row in cursor.fetchall()]

    skipped_sources = [s for s in all_sources if s["status"] == "skipped"]
    failed_sources = [s for s in all_sources if s["status"] == "failed"]
    downloaded_sources = [s for s in all_sources if s["status"] in ("downloaded", "parsed")]

    return {
        "coverage": coverage_rows,
        "skipped": skipped_sources,
        "failed": failed_sources,
        "downloaded": downloaded_sources
    }

def write_coverage_report(db: Optional[DatabaseManager] = None, report_path: Optional[Path] = None) -> Path:
    """Generates data/reports/syllabus_coverage.md documenting coverage, skipped links, and manual verification items."""
    if db is None:
        db = DatabaseManager()
    if report_path is None:
        report_path = config.DATA_DIR / "reports" / "syllabus_coverage.md"
        
    report_path.parent.mkdir(parents=True, exist_ok=True)
    cov_data = generate_coverage_data(db)
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# B.Tech Syllabus Ingestion & Coverage Report",
        f"**Generated:** {timestamp}\n",
        "## Summary",
        f"- **Parsed / Downloaded Sources:** {len(cov_data['downloaded'])}",
        f"- **Skipped Links:** {len(cov_data['skipped'])}",
        f"- **Failed Links:** {len(cov_data['failed'])}\n",
        "## Syllabus Coverage by Branch, Scheme, Year & Semester",
        "| Branch | Scheme | Year | Semester | Distinct Courses | Courses with Units | Needing Review |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for row in cov_data["coverage"]:
        lines.append(
            f"| {row['branch']} | {row['scheme']} | {row['year']} | {row['semester']} | "
            f"{row['num_courses']} | {row['num_with_units']} | {row['num_needing_review']} |"
        )
    if not cov_data["coverage"]:
        lines.append("| *None* | - | - | - | 0 | 0 | 0 |")

    lines.append("\n## Skipped Links (With Reason)")
    lines.append("| Branch | Scheme | Program | Kind | Link Text | URL | Reason |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for s in cov_data["skipped"]:
        lines.append(
            f"| {s['branch']} | {s['scheme']} | {s['program']} | {s['kind']} | "
            f"{s['link_text']} | [{s['url']}]({s['url']}) | {s['reason']} |"
        )
    if not cov_data["skipped"]:
        lines.append("| *None* | - | - | - | - | - | - |")

    lines.append("\n## Failed Links (If Any)")
    if cov_data["failed"]:
        lines.append("| Branch | Program | Scheme | Kind | URL | Error / Reason |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for f in cov_data["failed"]:
            lines.append(f"| {f['branch']} | {f['program']} | {f['scheme']} | {f['kind']} | [{f['url']}]({f['url']}) | {f['reason']} |")
    else:
        lines.append("- *No failed links.* All eligible syllabus downloads and parsings succeeded.")

    lines.append("\n## Manual Verification Checklist (What to Check by Hand Against PDFs)")
    lines.append("1. **Courses with `needs_review = 1`**: These are primarily Laboratory courses, IT Workshops, and Mini-Projects which follow a 'List of Experiments' structure rather than 5 units. Check that lab experiment titles are present in `topics`.")
    lines.append("2. **Category Code Parsing**: For lab courses where the category column is omitted in PDF tables, category remains NULL. Confirm if default PC/ES is desired.")
    lines.append("3. **Common First Year Coverage**: Verify that `BS101`, `BS102`, `CS101`, etc., stored under branch `COMMON`, are visible when selecting any branch for Semesters 1 and 2 in Subject Assistance.")
    lines.append("4. **Word Documents (.doc/.docx)**: The college website hosts several older M.Tech syllabi in `.doc` format which were skipped per requirements.")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return report_path

def ingest_all_departments_syllabus(db: Optional[DatabaseManager] = None, embed: bool = True) -> Dict[str, Any]:
    """Ingests syllabus across all 10 departments with timeboxing per department."""
    if db is None:
        db = DatabaseManager()
        
    from src.faculty_parser import DEPARTMENT_CONFIGS
    start_time = time.time()
    dept_reports = []

    for dept in DEPARTMENT_CONFIGS:
        branch = dept["short_code"]
        dept_url = dept["url"]
        dept_start = time.time()
        logger.info(f"=== Starting syllabus ingestion for {branch} ===")
        print(f"\n--- Processing Department: {branch} ({dept['name']}) ---")
        
        sources = scrape_department_syllabus_links(dept_url, branch, db)
        eligible = [s for s in sources if s.get("status") in ("found", "parsed", "downloaded")]
        print(f"  Found {len(sources)} total links ({len(eligible)} eligible for schemes 2020/2023/2026)")
        
        parsed_count = 0
        downloaded_count = 0
        unchanged_count = 0
        failed_count = 0
        
        for s in eligible:
            # Timebox per department (max 120s)
            if time.time() - dept_start > 120:
                logger.warning(f"Time-box reached for {branch}, proceeding to next department")
                break
                
            res = ingest_syllabus_source(db, s, embed=embed)
            res_status = res.get("status")
            if res_status == "parsed":
                parsed_count += 1
            elif res_status == "downloaded":
                downloaded_count += 1
            elif res_status == "unchanged":
                unchanged_count += 1
            elif res_status == "failed":
                failed_count += 1
                
        elapsed = time.time() - dept_start
        dept_reports.append({
            "branch": branch,
            "name": dept["name"],
            "eligible": len(eligible),
            "parsed": parsed_count,
            "downloaded": downloaded_count,
            "unchanged": unchanged_count,
            "failed": failed_count,
            "elapsed_seconds": round(elapsed, 2)
        })
        print(f"  Completed {branch} in {elapsed:.2f}s (Parsed: {parsed_count}, Regs Downloaded: {downloaded_count}, Unchanged: {unchanged_count}, Failed: {failed_count})")

    report_path = config.DATA_DIR / "reports" / "syllabus_coverage.md"
    write_coverage_report(db, report_path)
    print(f"\nSaved syllabus coverage report to {report_path}")

    total_time = time.time() - start_time
    return {
        "departments": dept_reports,
        "total_elapsed_seconds": round(total_time, 2)
    }
