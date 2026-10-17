from bs4 import BeautifulSoup
import re
from typing import Dict, Any, Optional
from dateutil import parser as date_parser
from datetime import datetime

def clean_html(html_content: str) -> str:
    """Removes scripts, styles, header, footer, nav to extract core text."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Remove unwanted tags
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "form"]):
        element.decompose()
        
    # Remove common repetitive elements by class or id (e.g. menus, cookie banners)
    for element in soup.find_all(class_=re.compile(r'(menu|footer|header|sidebar|cookie|widget)', re.I)):
        element.decompose()
    for element in soup.find_all(id=re.compile(r'(menu|footer|header|sidebar|cookie|widget)', re.I)):
        element.decompose()
    
    # Extract text with line breaks preserved initially to detect duplicate lines
    lines = soup.get_text(separator="\n", strip=True).splitlines()
    seen = set()
    unique_lines = []
    for line in lines:
        line_clean = line.strip()
        if not line_clean: continue
        if line_clean not in seen:
            seen.add(line_clean)
            unique_lines.append(line_clean)
            
    text = " ".join(unique_lines)
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """Extracts title, dates, etc. from the page soup."""
    # Title Generation: Prioritize H1, then breadcrumb, then URL parsing. Never generic <title>.
    title = ""
    if soup.h1:
        title = soup.h1.get_text(strip=True)
    
    # If no h1, try to find a breadcrumb or section heading
    if not title:
        breadcrumbs = soup.find(class_=re.compile(r'breadcrumb', re.I))
        if breadcrumbs:
            title = breadcrumbs.get_text(separator=" > ", strip=True)
            
    # If still no title, derive from URL
    if not title:
        try:
            from urllib.parse import urlparse
            path = urlparse(url).path.strip('/')
            if path:
                parts = [p.replace('-', ' ').title() for p in path.split('/')]
                title = " > ".join(parts)
            else:
                title = "Home"
        except:
            title = "Document"
    # Department / Category inference from URL or Breadcrumbs
    department = "General"
    category = "General"
    url_lower = url.lower()
    
    # Very basic inference (to be improved later)
    if "/departments/" in url_lower:
        category = "Departments"
        parts = url_lower.split("/departments/")
        if len(parts) > 1:
            dept = parts[1].split("/")[0]
            if dept:
                department = dept.upper()
    elif "/admissions/" in url_lower:
        category = "Admissions"
    elif "/examinations/" in url_lower:
        category = "Examinations"
    elif "/placements/" in url_lower:
        category = "Placements"
    elif "notice" in url_lower or "circular" in url_lower:
        category = "Notices"
        
    # Try to find a date (e.g. published date) - heuristics
    published_date = None
    
    # Simple regex to find date-like patterns in text or title
    def find_date(text):
        if not text: return None
        # Look for dd-mm-yyyy or dd/mm/yyyy
        match = re.search(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b', text)
        if match: return match.group(0)
        # Look for Month YYYY or DD Month YYYY
        match = re.search(r'\b(?:\d{1,2}[\s,-]+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,-]+\d{4}\b', text, re.I)
        if match: return match.group(0)
        return None
        
    date_str = find_date(title)
    if not date_str:
        # Check nearby text or h3/h4 tags
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'span', 'p']):
            found = find_date(heading.get_text())
            if found:
                date_str = found
                break
                
    if date_str:
        try:
            dt = date_parser.parse(date_str, fuzzy=True, dayfirst=True)
            published_date = dt.isoformat()
        except:
            published_date = None
            
    return {
        "title": title,
        "category": category,
        "department": department,
        "source_type": "page",
        "published_date": published_date
    }
