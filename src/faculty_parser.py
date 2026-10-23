import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.database import DatabaseManager

logger = logging.getLogger(__name__)

# Canonical department definitions
DEPARTMENT_CONFIGS = [
    {
        "name": "Civil Engineering",
        "short_code": "CE",
        "slug": "civil_engineering",
        "url": "https://www.gprec.ac.in/programs-offered/civil-engineering/",
        "aliases": ["civil", "civil engineering", "ce"]
    },
    {
        "name": "Computer Science and Engineering",
        "short_code": "CSE",
        "slug": "computer_science_and_engineering",
        "url": "https://www.gprec.ac.in/programs-offered/computer-science-and-engineering/",
        "aliases": ["cse", "computer science", "computer science and engineering", "cs"]
    },
    {
        "name": "Electrical and Electronics Engineering",
        "short_code": "EEE",
        "slug": "electrical_and_electronics_engineering",
        "url": "https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/",
        "aliases": ["eee", "electrical", "electrical and electronics engineering", "electrical engineering"]
    },
    {
        "name": "Electronics and Communication Engineering",
        "short_code": "ECE",
        "slug": "electronics_and_communication_engineering",
        "url": "https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/",
        "aliases": ["ece", "electronics", "electronics and communication engineering", "electronics and communication"]
    },
    {
        "name": "Mechanical Engineering",
        "short_code": "ME",
        "slug": "mechanical_engineering",
        "url": "https://www.gprec.ac.in/programs-offered/mechanical-engineering/",
        "aliases": ["me", "mech", "mechanical", "mechanical engineering"]
    },
    {
        "name": "Humanities and Basic Sciences",
        "short_code": "H&S",
        "slug": "humanities_and_basic_sciences",
        "url": "https://www.gprec.ac.in/programs-offered/humanities-and-basic-sciences/",
        "aliases": ["h&s", "hs", "humanities", "basic sciences", "humanities and basic sciences", "humanities and sciences", "bs"]
    },
    {
        "name": "CSE - Artificial Intelligence & Machine Learning",
        "short_code": "CSM",
        "slug": "cse_ai_ml",
        "url": "https://www.gprec.ac.in/cse-artificial-intelligence-machine-learning-csm/",
        "aliases": ["csm", "ai ml", "aiml", "cse ai", "cse aiml", "cse artificial intelligence and machine learning"]
    },
    {
        "name": "CSE - Data Science",
        "short_code": "CSD",
        "slug": "cse_data_science",
        "url": "https://www.gprec.ac.in/cse-data-science/",
        "aliases": ["csd", "data science", "cse ds", "cse data science"]
    },
    {
        "name": "Computer Science and Business Systems",
        "short_code": "CSB",
        "slug": "computer_science_and_business_systems",
        "url": "https://www.gprec.ac.in/computer-science-and-business-systems/",
        "aliases": ["csb", "business systems", "computer science and business systems"]
    },
    {
        "name": "Computer Science and Technology",
        "short_code": "CST",
        "slug": "computer_science_and_technology",
        "url": "https://www.gprec.ac.in/computer-science-and-technology/",
        "aliases": ["cst", "computer science and technology"]
    }
]


def clean_faculty_name(raw_name: str) -> str:
    """Normalize whitespace and strip extraneous characters from faculty names."""
    if not raw_name:
        return ""
    # Replace non-breaking spaces and repeated whitespace
    name = raw_name.replace('\xa0', ' ').replace('&nbsp;', ' ')
    name = re.sub(r'^\d+[\.\)]\s*', '', name)  # Remove leading numbering like '1. '
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_hod_designation(designation: Optional[str]) -> int:
    """Return 1 only if designation explicitly states Head of the Department/HOD, excluding Associate HOD."""
    if not designation:
        return 0
    desig_clean = designation.replace('\xa0', ' ').lower()
    # If explicitly contains Associate HoD or Assoc HoD, it's not the head of department
    if re.search(r'\b(assoc|associate)\.?\s*(hod|head)', desig_clean):
        return 0
    if re.search(r'\b(hod|head of the department|head of department)\b', desig_clean):
        return 1
    return 0


def is_guest_designation(designation: Optional[str]) -> int:
    """Return 1 if designation specifies guest, visiting, or adjunct faculty."""
    if not designation:
        return 0
    desig_clean = designation.replace('\xa0', ' ').lower()
    if re.search(r'\b(guest|visiting|adjunct)\b', desig_clean):
        return 1
    return 0


def parse_faculty_page(html_content: str, dept_name: str, source_url: str) -> List[Dict[str, Any]]:
    """
    Parse faculty member cards from WPBakery 2-column card tables.
    Extracts name, designation, qualification, email, photo_url, profile_url, is_hod, is_guest.
    Missing fields remain None / NULL.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    faculty_list = []
    seen_names = set()

    # Find all tables that contain faculty details
    for table in soup.find_all("table"):
        table_text = table.get_text().lower()
        if "name of the faculty" not in table_text:
            continue

        # Avoid double-processing inner tables if outer table already processed
        # A faculty block table typically either wraps an inner table or is standalone
        if not table.find("table") and table.find_parent("table"):
            # This is an inner table, parent will be or was processed
            continue

        # 1. Photo URL from img tag
        photo_url = None
        img = table.find("img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src and not src.startswith("data:"):
                photo_url = urljoin(source_url, src.strip())

        # 2. Extract key-value rows from the table
        fields: Dict[str, str] = {}
        profile_url = None

        # Look for PDF profile links anywhere within this table
        for a in table.find_all("a", href=True):
            href = a["href"].strip()
            if ".pdf" in href.lower() or "faculty" in href.lower():
                profile_url = urljoin(source_url, href)
                break

        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) == 2:
                k = cells[0].get_text(strip=True).lower().replace('\xa0', ' ')
                v = cells[1].get_text(strip=True).replace('\xa0', ' ')
                
                # Check for profile link directly inside cell 1 or 2
                if not profile_url:
                    for a in cells[1].find_all("a", href=True):
                        h = a["href"].strip()
                        if ".pdf" in h.lower() or "profile" in h.lower():
                            profile_url = urljoin(source_url, h)
                            break
                            
                fields[k] = v

        # Extract name
        raw_name = fields.get("name of the faculty") or fields.get("name")
        if not raw_name:
            continue

        name = clean_faculty_name(raw_name)
        if not name or len(name) < 2:
            continue

        if name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        # Extract designation (None if missing or placeholder)
        designation = fields.get("designation")
        if designation:
            designation = re.sub(r'\s+', ' ', designation).strip()
            if designation.lower() in ("-", "--", "nil", "na", "n/a"):
                designation = None

        # Extract qualification (None if missing or placeholder - DO NOT GUESS)
        qualification = fields.get("qualifications") or fields.get("qualification")
        if qualification:
            qualification = re.sub(r'\s+', ' ', qualification).strip()
            if qualification.lower() in ("-", "--", "nil", "na", "n/a"):
                qualification = None

        # Extract email (None if missing or placeholder - DO NOT INVENT)
        email = fields.get("emailid") or fields.get("email") or fields.get("mail id")
        if email:
            email = email.strip()
            # Verify if it looks like an email address
            m = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', email)
            email = m.group(0) if m else None

        is_hod = is_hod_designation(designation)
        is_guest = is_guest_designation(designation)

        record = {
            "name": name,
            "designation": designation,
            "qualification": qualification,
            "department": dept_name,
            "email": email,
            "photo_url": photo_url,
            "photo_path": None,  # Populated during photo download
            "profile_url": profile_url,
            "is_guest": is_guest,
            "is_hod": is_hod,
            "source_url": source_url,
            "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_active": 1
        }
        faculty_list.append(record)

    return faculty_list


def download_and_resize_photo(
    photo_url: Optional[str],
    dept_slug: str,
    person_name: str,
    output_base_dir: Optional[Path] = None,
    session: Optional[requests.Session] = None
) -> Optional[str]:
    """
    Download a faculty photo and resize it to at most 400px width preserving aspect ratio.
    Saves to data/faculty_photos/<dept_slug>/<clean_slug>.jpg.
    Returns the relative path string 'data/faculty_photos/...', or None if download fails.
    Skips if file already exists on disk.
    """
    if not photo_url:
        return None

    base_dir = output_base_dir or (config.DATA_DIR / "faculty_photos")
    target_dir = base_dir / dept_slug
    target_dir.mkdir(parents=True, exist_ok=True)

    name_slug = re.sub(r'[^a-zA-Z0-9]+', '_', person_name.lower()).strip('_')
    filename = f"{name_slug}.jpg"
    target_path = target_dir / filename
    rel_path = f"data/faculty_photos/{dept_slug}/{filename}"

    # If already downloaded and valid, reuse
    if target_path.exists() and target_path.stat().st_size > 0:
        return rel_path

    # Download with retry
    http = session or requests.Session()
    headers = {"User-Agent": getattr(config, "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")}

    try:
        resp = http.get(photo_url, headers=headers, timeout=(2.0, 3.5), stream=True)
        if resp.status_code != 200:
            return None

        # Check content-length: skip files larger than 5MB (e.g. uncompressed raw PNGs)
        cl = resp.headers.get("content-length")
        if cl and int(cl) > 5_000_000:
            return None

        content = resp.raw.read(5_000_000)
        if not content:
            return None

        # Load and resize with PIL
        img = Image.open(io.BytesIO(content))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize to max 400px width preserving aspect ratio
        if img.width > 400:
            ratio = 400.0 / img.width
            new_height = int(img.height * ratio)
            img = img.resize((400, new_height), Image.Resampling.LANCZOS)

        img.save(target_path, "JPEG", quality=85)
        return rel_path

    except Exception as e:
        logger.warning(f"Failed to download/process photo for {person_name} from {photo_url}: {e}")
        return None


def ingest_department_faculty(
    dept_config: Dict[str, Any],
    db: DatabaseManager,
    session: Optional[requests.Session] = None,
    download_photos: bool = True
) -> Dict[str, Any]:
    """
    Fetch a department's page, extract faculty members, download & resize photos,
    and upsert them to the database. Marks absent faculty as inactive.
    """
    dept_name = dept_config["name"]
    url = dept_config["url"]
    slug = dept_config["slug"]

    http = session or requests.Session()
    headers = {"User-Agent": getattr(config, "USER_AGENT", "Mozilla/5.0")}

    logger.info(f"Fetching faculty for {dept_name} from {url}")
    resp = http.get(url, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch {url}: HTTP {resp.status_code}")

    faculty_records = parse_faculty_page(resp.text, dept_name, url)
    active_names = []
    photos_downloaded = 0
    missing_qualification = 0

    crawl_delay = min(getattr(config, "CRAWL_DELAY", 0.1), 0.1)

    for rec in faculty_records:
        active_names.append(rec["name"])
        if not rec["qualification"]:
            missing_qualification += 1

        if download_photos and rec["photo_url"]:
            path = download_and_resize_photo(
                rec["photo_url"],
                dept_slug=slug,
                person_name=rec["name"],
                session=http
            )
            rec["photo_path"] = path
            if path:
                photos_downloaded += 1
            if crawl_delay > 0:
                time.sleep(crawl_delay)

    # Upsert all to database
    db.upsert_faculty_batch(faculty_records)

    # Mark absent members as inactive
    db.mark_missing_faculty_inactive(dept_name, active_names)

    regular_count = sum(1 for r in faculty_records if not r["is_guest"])
    guest_count = sum(1 for r in faculty_records if r["is_guest"])
    hod_list = [r["name"] for r in faculty_records if r["is_hod"]]

    return {
        "department": dept_name,
        "short_code": dept_config["short_code"],
        "total": len(faculty_records),
        "regular": regular_count,
        "guest": guest_count,
        "photos_downloaded": photos_downloaded,
        "missing_qualification": missing_qualification,
        "hods": hod_list,
        "first_3_names": [r["name"] for r in faculty_records[:3]]
    }


def generate_faculty_report(stats_list: List[Dict[str, Any]], output_path: Path):
    """Generate Markdown report data/reports/faculty_report.md."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    total_all = sum(s["total"] for s in stats_list)
    regular_all = sum(s["regular"] for s in stats_list)
    guest_all = sum(s["guest"] for s in stats_list)
    photos_all = sum(s["photos_downloaded"] for s in stats_list)
    missing_qual_all = sum(s["missing_qualification"] for s in stats_list)

    lines = [
        "# GPREC Faculty Directory Ingestion Report",
        "",
        f"**Date Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Total Departments Scanned:** {len(stats_list)}  ",
        f"**Total Faculty Records:** {total_all} (Regular: {regular_all}, Guest/Adjunct: {guest_all})  ",
        f"**Photos Successfully Downloaded & Resized (≤400px):** {photos_all}  ",
        "",
        "## 1. Department Breakdown",
        "",
        "| Department | Total | Regular | Guest | Photos Downloaded | Missing Qualification |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |"
    ]

    for s in stats_list:
        lines.append(
            f"| {s['department']} ({s['short_code']}) | {s['total']} | {s['regular']} | {s['guest']} | {s['photos_downloaded']} | {s['missing_qualification']} |"
        )

    lines.extend([
        f"| **TOTAL** | **{total_all}** | **{regular_all}** | **{guest_all}** | **{photos_all}** | **{missing_qual_all}** |",
        "",
        "## 2. Heads of Department (HODs) Identified",
        ""
    ])

    for s in stats_list:
        hod_str = ", ".join(s["hods"]) if s["hods"] else "None explicitly designated on page"
        lines.append(f"- **{s['department']}:** {hod_str}")

    lines.extend([
        "",
        "## 3. Sample Verification (First 3 Faculty per Department)",
        ""
    ])

    for s in stats_list:
        names_str = ", ".join(s["first_3_names"]) if s["first_3_names"] else "None"
        lines.append(f"- **{s['department']}:** {names_str}")

    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Faculty report written to {output_path}")


def ingest_all_departments(db: Optional[DatabaseManager] = None, download_photos: bool = True) -> List[Dict[str, Any]]:
    """Ingest faculty for all 10 departments and write report."""
    database = db or DatabaseManager()
    session = requests.Session()
    stats_list = []

    for dept in DEPARTMENT_CONFIGS:
        print(f"Ingesting faculty for {dept['name']}...", flush=True)
        stats = ingest_department_faculty(dept, database, session=session, download_photos=download_photos)
        stats_list.append(stats)
        print(f" -> Found {stats['total']} faculty, HOD: {stats['hods']}, Photos: {stats['photos_downloaded']}", flush=True)

    report_path = config.DATA_DIR / "reports" / "faculty_report.md"
    generate_faculty_report(stats_list, report_path)
    print(f"Faculty ingestion complete. Report generated at {report_path}", flush=True)
    return stats_list


if __name__ == "__main__":
    db = DatabaseManager()
    ingest_all_departments(db, download_photos=True)
