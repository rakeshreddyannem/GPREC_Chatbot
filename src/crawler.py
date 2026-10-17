import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import requests
import re
from urllib.parse import urljoin, urldefrag, urlparse, unquote
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Set, Dict, Any
import json

import config
from src.database import DatabaseManager
from src.extractor import clean_html, extract_metadata
from src.change_detector import ChangeDetector

class GPRECCrawler:
    def __init__(self):
        self.db = DatabaseManager()
        self.change_detector = ChangeDetector(self.db)
        self.visited_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.stats = {
            "total_discovered": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_skipped": 0,
            "total_pdfs": 0,
            "new_count": 0,
            "modified_count": 0,
            "unchanged_count": 0,
            "removed_count": 0
        }
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})

    def normalize_url(self, url: str) -> str:
        url, _ = urldefrag(url)
        return url

    def is_valid_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in config.ALLOWED_DOMAINS)

    def is_pdf(self, url: str) -> bool:
        exts = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt", ".zip"]
        return any(url.lower().endswith(ext) for ext in exts)

    def get_robots_txt(self):
        # We manually respect the delay here if we want, but simple 1.5s delay is implemented
        pass

    def crawl_page(self, url: str) -> List[str]:
        """Crawls a single page, processes it, and returns a list of discovered links."""
        url = self.normalize_url(url)
        if url in self.visited_urls:
            return []
            
        self.visited_urls.add(url)
        self.stats["total_discovered"] += 1
        
        if self.stats["total_processed"] >= getattr(config, "MAX_PAGES", 1000):
            self.stats["total_skipped"] += 1
            return []
            
        print(f"Crawling: {url}")
        try:
            time.sleep(config.CRAWL_DELAY)
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            
            # Handling PDFs (basic reporting for Phase 2)
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/pdf" in content_type or self.is_pdf(url):
                self.stats["total_pdfs"] += 1
                self.stats["total_processed"] += 1
                print(f"  -> Discovered PDF: {url}")
                # We skip full PDF processing in Phase 2
                return []
                
            if response.status_code != 200:
                self.failed_urls.add(url)
                self.stats["total_failed"] += 1
                return []
                
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Extraction
            clean_text = clean_html(html_content)
            metadata = extract_metadata(soup, url)
            
            # Change Detection
            status, content_hash, version = self.change_detector.check_page_status(url, clean_text)
            
            if status == "NEW":
                self.stats["new_count"] += 1
            elif status == "MODIFIED":
                self.stats["modified_count"] += 1
            elif status == "UNCHANGED":
                self.stats["unchanged_count"] += 1
                
            print(f"  -> Status: {status}")
            
            page_data = {
                "source_url": url,
                "title": metadata.get("title", ""),
                "category": metadata.get("category", ""),
                "department": metadata.get("department", ""),
                "source_type": metadata.get("source_type", "page"),
                "published_date": metadata.get("published_date"),
                "last_modified": response.headers.get("Last-Modified"),
                "last_checked": datetime.now().isoformat(),
                "content_hash": content_hash,
                "version": version,
                "is_current": 1,
                "status": status,
                "clean_text": clean_text
            }
            
            # Save to DB
            self.db.upsert_page(page_data)
            self.stats["total_processed"] += 1
            
            # Extract links and documents
            discovered_links = []
            
            # Helper to add links
            def add_link(href, text, nearby, is_onclick=False):
                if href.startswith('javascript:') or href.startswith('mailto:') or href.startswith('tel:'):
                    return
                href = unquote(href)
                full_url = urljoin(url, href).split('#')[0]
                
                is_ext = not self.is_valid_url(full_url)
                if self.is_pdf(full_url):
                    status = "external - needs manual review" if is_ext else "discovered"
                    
                    # Extract date from text or nearby
                    import re
                    from dateutil import parser as date_parser
                    def find_date(t):
                        if not t: return None
                        match = re.search(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b', t)
                        if match: return match.group(0)
                        match = re.search(r'\b(?:\d{1,2}[\s,-]+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,-]+\d{4}\b', t, re.I)
                        if match: return match.group(0)
                        return None
                        
                    date_str = find_date(text) or find_date(nearby)
                    published_date = None
                    date_source = None
                    if date_str:
                        try:
                            dt = date_parser.parse(date_str, fuzzy=True, dayfirst=True)
                            published_date = dt.isoformat()
                            date_source = "link_text" if find_date(text) else "nearby_text"
                        except:
                            pass
                            
                    self.db.upsert_document({
                        "document_url": full_url,
                        "link_text": text[:200] if text else "",
                        "parent_page_url": url,
                        "nearby_text": nearby[:500] if nearby else "",
                        "category": metadata.get("category", "Notices" if "notice" in url.lower() or "circular" in url.lower() else ""),
                        "department": metadata.get("department", ""),
                        "published_date": published_date,
                        "date_source": date_source,
                        "status": status,
                        "last_checked": datetime.now().isoformat()
                    })
                    self.stats["total_pdfs"] += 1
                elif not is_ext and full_url not in self.visited_urls:
                    discovered_links.append(full_url)

            # Helper for nearby text
            def get_nearby_text(tag):
                parent = tag.find_parent(['td', 'li', 'p', 'h3', 'h4', 'h5'])
                if parent:
                    return parent.get_text(separator=' ', strip=True)
                # Fallback to direct parent if it's small
                direct = tag.parent
                if direct and len(direct.get_text(strip=True)) < 200:
                    return direct.get_text(separator=' ', strip=True)
                return ""

            # 1. Standard anchor tags
            for a_tag in soup.find_all('a', href=True):
                nearby = get_nearby_text(a_tag)
                add_link(a_tag['href'], a_tag.get_text(strip=True), nearby)
                
            # 2. Buttons/divs with onclick
            for tag in soup.find_all(['button', 'div', 'span'], onclick=True):
                match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", tag['onclick'])
                if match:
                    nearby = get_nearby_text(tag)
                    add_link(match.group(1), tag.get_text(strip=True), nearby, is_onclick=True)

            # 3. data-href
            for tag in soup.find_all(attrs={"data-href": True}):
                nearby = get_nearby_text(tag)
                add_link(tag['data-href'], tag.get_text(strip=True), nearby)

            # 4. Iframes/Embeds
            for tag in soup.find_all(['iframe', 'embed', 'object']):
                src = tag.get('src') or tag.get('data')
                if src:
                    nearby = get_nearby_text(tag)
                    add_link(src, "Embedded Document", nearby)
                    
            # Deduplicate links
            discovered_links = list(set(discovered_links))
                    
            return discovered_links
            
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            self.failed_urls.add(url)
            self.stats["total_failed"] += 1
            return []

    def run(self, seed_urls: List[str] = None):
        seeds = seed_urls or config.SEED_URLS
        queue = []
        for s in seeds:
            s = self.normalize_url(s)
            if s not in queue:
                queue.append(s)
                
        while queue and self.stats["total_processed"] < getattr(config, "MAX_PAGES", 1000):
            url = queue.pop(0)
            if url not in self.visited_urls:
                new_links = self.crawl_page(url)
                for nl in new_links:
                    if nl not in queue and nl not in self.visited_urls:
                        queue.append(nl)
                        
        print("\nCrawl Complete.")
        self.generate_report()

    def generate_report(self):
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_discovered": self.stats["total_discovered"],
            "total_processed": self.stats["total_processed"],
            "total_failed": self.stats["total_failed"],
            "total_skipped": self.stats["total_skipped"],
            "total_pdfs": self.stats["total_pdfs"],
            "new_count": self.stats["new_count"],
            "modified_count": self.stats["modified_count"],
            "unchanged_count": self.stats["unchanged_count"],
            "removed_count": self.stats["removed_count"],
            "details": {
                "failed_urls": list(self.failed_urls)
            }
        }
        self.db.save_crawl_report(report_data)
        
        report_path = config.REPORTS_DIR / f"crawl_report_{int(time.time())}.json"
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=4)
        print(f"Report saved to {report_path}")
        print(json.dumps(report_data, indent=2))

if __name__ == "__main__":
    crawler = GPRECCrawler()
    crawler.run()
