import re
import hashlib
from typing import List, Dict, Any, Set, Tuple, Optional

class BoilerplateCleaner:
    """Removes standard website headers, footers, navigation noise, and boilerplate."""

    BOILERPLATE_PATTERNS = [
        r"(?i)skip to (?:main\s+)?content",
        r"(?i)copyright.*all rights reserved[^\n]*",
        r"(?i)all rights reserved[^\n]*",
        r"(?i)copyright\s*(?:©|\(c\))?[^\n]*",
        r"(?i)designed and maintained by[^.\n]*",
        r"(?i)follow us on (?:facebook|twitter|instagram|linkedin|youtube)[^\n]*",
        r"(?i)g\.?\s*pulla\s*reddy\s*engineering\s*college\s*\(autonomous\)\s*kurnool[,\s]*andhra pradesh",
        r"(?i)phone:\s*\+?91[\d\s\-]+|fax:\s*[\d\s\-]+",
        r"(?i)home\s*\|\s*about\s*us\s*\|\s*admissions\s*\|\s*academics\s*\|\s*departments",
        r"(?i)this website uses cookies[^.\n]*",
        r"(?i)an autonomous institution affiliated to jntua[^.\n]*",
        r"(?i)approved by aicte[^.\n]*accredited by naac[^.\n]*",
    ]

    @classmethod
    def clean_text(cls, text: str) -> str:
        if not text:
            return ""

        cleaned = text
        for pat in cls.BOILERPLATE_PATTERNS:
            cleaned = re.sub(pat, " ", cleaned)

        # Normalize redundant spaces and blank lines
        lines = [line.strip() for line in cleaned.splitlines()]
        filtered_lines = []
        for line in lines:
            # Skip lines that are just nav links or solitary separators
            if not line or line in ["|", "•", "-", "*", "--", "---"]:
                continue
            if len(line) < 3 and not line.isalnum():
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines).strip()


class SectionTitleExtractor:
    """Derives specific section-level titles from content structure."""

    DEPARTMENT_MAP = {
        "electrical": "EEE",
        "electronics": "ECE",
        "computer science": "CSE",
        "civil": "CE",
        "mechanical": "ME",
        "humanities": "H&S",
        "training & placement": "T&P",
        "library": "Central Library",
        "hostel": "Hostel",
        "examination": "Examinations"
    }

    SUBSECTION_KEYWORDS = [
        ("assistant professor", "Assistant Professors"),
        ("associate professor", "Associate Professors"),
        ("professor & head", "HOD & Professors"),
        ("professors", "Professors"),
        ("non-teaching", "Non-Teaching Staff"),
        ("technical staff", "Technical Staff"),
        ("laboratories", "Laboratories & Infrastructure"),
        ("placement statistics", "Placement Statistics"),
        ("placement training", "Placement Training"),
        ("recruiting companies", "Recruiters & Companies"),
        ("timings", "Timings & Working Hours"),
        ("rules and regulations", "Rules & Regulations"),
        ("fee structure", "Fee Structure & Payment"),
        ("admission procedure", "Admission Procedure"),
        ("facilities", "Facilities & Amenities"),
        ("mess", "Mess & Dining"),
        ("time table", "Time Table & Schedule"),
    ]

    @classmethod
    def derive_title(cls, base_title: str, content: str, source_url: str = "") -> str:
        clean_base = re.sub(r"(?i)–\s*GPREC\s*>.*$", "", base_title).strip()
        clean_base = re.sub(r"(?i)G\.?\s*Pulla\s*Reddy.*$", "", clean_base).strip(" –->|:")

        # Detect department/topic prefix
        dept_prefix = ""
        url_lower = source_url.lower()
        title_lower = clean_base.lower()

        for key, code in cls.DEPARTMENT_MAP.items():
            if key in title_lower or key in url_lower:
                dept_prefix = code
                break

        # Detect specific subsection
        content_lower = content.lower()
        sub_title = ""
        for kw, label in cls.SUBSECTION_KEYWORDS:
            if kw in content_lower[:400]:
                sub_title = label
                break

        if dept_prefix and sub_title:
            return f"{dept_prefix} — {sub_title}"
        elif dept_prefix and clean_base:
            return f"{dept_prefix} — {clean_base}"
        elif sub_title and clean_base:
            return f"{clean_base} — {sub_title}"
        elif clean_base:
            return clean_base
        return "GPREC Official Information"


class ChunkDeduplicator:
    """Deduplicates chunks using SHA-256 hash and Jaccard token set similarity (> 0.85)."""

    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "with", "by", "is", "are", "was", "were", "be", "been", "this", "that", "it"
    }

    @classmethod
    def get_token_set(cls, text: str) -> Set[str]:
        words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', text.lower())
        return {w for w in words if w not in cls.STOPWORDS}

    @classmethod
    def jaccard_similarity(cls, tokens_a: Set[str], tokens_b: Set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0

    @classmethod
    def deduplicate_chunks(cls, chunks: List[Dict[str, Any]], similarity_threshold: float = 0.85) -> List[Dict[str, Any]]:
        seen_hashes = set()
        kept_chunks = []
        token_sets = []

        for chunk in chunks:
            raw_content = chunk.get("content", "").strip()
            if len(raw_content) < 30:
                continue

            # 1. Exact hash deduplication
            content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
            if content_hash in seen_hashes:
                continue

            # 2. Near-duplicate similarity check
            current_tokens = cls.get_token_set(raw_content)
            is_near_duplicate = False

            for existing_tokens in token_sets:
                sim = cls.jaccard_similarity(current_tokens, existing_tokens)
                if sim >= similarity_threshold:
                    is_near_duplicate = True
                    break

            if not is_near_duplicate:
                seen_hashes.add(content_hash)
                token_sets.append(current_tokens)
                chunk["chunk_hash"] = content_hash
                if not chunk.get("content_hash"):
                    chunk["content_hash"] = content_hash
                if "version" not in chunk:
                    chunk["version"] = 1
                kept_chunks.append(chunk)

        return kept_chunks


class CoverageAuditor:
    """Audits essential college domains for presence, completeness, and freshness."""

    ESSENTIAL_TARGETS = [
        ("Placement statistics / recruiters", ["placement", "recruit", "training-placements"]),
        ("Fee structure", ["fee", "payment", "tuition"]),
        ("Hostel details & rules", ["hostel", "boys hostel", "girls hostel", "mess"]),
        ("Library resources & timings", ["library", "digital library"]),
        ("Exam cell / timetable portal", ["exam", "timetable", "examinations"]),
        ("EEE department faculty", ["electrical", "eee"]),
        ("ECE department faculty", ["electronics", "ece"]),
        ("CSE department faculty", ["computer", "cse"]),
        ("ME department faculty", ["mechanical"]),
        ("CE department faculty", ["civil"]),
        ("H&S department faculty", ["humanities", "basic sciences", "h&s", "hbs"]),
        ("College leadership / administration", ["principal", "administration", "leadership", "about-us"])
    ]

    @classmethod
    def audit_coverage(cls, db) -> Dict[str, Any]:
        results = {}
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for label, keywords in cls.ESSENTIAL_TARGETS:
                matches = []
                for kw in keywords:
                    cursor.execute("""
                        SELECT source_url, title, COALESCE(LENGTH(clean_text), 0) as content_len 
                        FROM pages 
                        WHERE LOWER(source_url) LIKE ? OR LOWER(title) LIKE ? OR LOWER(department) LIKE ?
                    """, (f"%{kw}%", f"%{kw}%", f"%{kw}%"))
                    matches.extend([dict(row) for row in cursor.fetchall()])

                # Deduplicate by url
                unique_urls = {m["source_url"]: m for m in matches}
                total_content = sum(m.get("content_len", 0) for m in unique_urls.values())

                if len(unique_urls) == 0:
                    status = "MISSING"
                elif total_content < 200:
                    status = "INCOMPLETE"
                else:
                    status = "PRESENT"

                results[label] = {
                    "status": status,
                    "pages_count": len(unique_urls),
                    "total_content_bytes": total_content,
                    "sample_urls": list(unique_urls.keys())[:2]
                }
        return results
