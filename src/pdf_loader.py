import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import requests
import hashlib
import ssl
from typing import List, Dict, Any, Optional
from pathlib import Path

import config

class PDFProcessor:
    def __init__(self, download_dir: Path = config.PDF_DATA_DIR):
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        # Configure tesseract cmd if needed on Windows. Example:
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    def download_pdf(self, url: str) -> Optional[Path]:
        """Downloads a PDF from a URL and saves it locally."""
        try:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            filepath = self.download_dir / f"{url_hash}.pdf"
            
            if filepath.exists() and filepath.stat().st_size > 0:
                print(f"File {filepath.name} already exists. Skipping download.")
                return filepath
                
            print(f"Downloading {url}...")
            response = requests.get(
                url, 
                headers={'User-Agent': config.USER_AGENT}, 
                timeout=config.REQUEST_TIMEOUT, 
                verify=False,
                stream=True
            )
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print("Download complete.")
            return filepath
        except Exception as e:
            print(f"Failed to download PDF {url}: {e}")
            return None

    @staticmethod
    def extract_tables_from_page(page: fitz.Page) -> List[List[str]]:
        """
        Extracts structured tables from a PDF page using PyMuPDF (fitz) find_tables().
        Converts rows into pipe-separated structured format:
        e.g., "Subject | Date | Time" or "Category | Fee Amount".
        Falls back to regex-based column pattern alignment if vector lines are missing.
        """
        formatted_rows: List[str] = []
        
        # 1. Official PyMuPDF table finder
        try:
            if hasattr(page, "find_tables"):
                tabs = page.find_tables()
                if tabs and getattr(tabs, "tables", None):
                    for tab in tabs.tables:
                        extracted = tab.extract()
                        if not extracted:
                            continue
                        for row in extracted:
                            # Filter empty cells and clean whitespace inside cells
                            clean_cells = [
                                re.sub(r'\s+', ' ', str(c)).strip() 
                                for c in row if c is not None and str(c).strip()
                            ]
                            if len(clean_cells) >= 2:
                                formatted_rows.append(" | ".join(clean_cells))
        except Exception as e:
            print(f"PyMuPDF find_tables warning: {e}")

        # 2. Fallback heuristic: Detect columnar tabular patterns if find_tables found nothing
        if not formatted_rows:
            raw_text = page.get_text("text") or ""
            lines = raw_text.splitlines()
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                # Tab separated or 3+ spaces separated
                cells = [c.strip() for c in re.split(r'\t+|\s{3,}', line_str) if c.strip()]
                if len(cells) >= 2:
                    # Check for exam timetable, fee table, or syllabus patterns
                    is_table_like = (
                        re.search(r'\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}', line_str) # Date
                        or re.search(r'\b(?:AM|PM|FN|AN|Hours?)\b', line_str, re.I) # Time/Session
                        or re.search(r'(?:₹|Rs\.?|INR|\bFee\b|\bAmount\b)', line_str, re.I) # Fee
                        or re.search(r'\b(?:Code|Credits?|L-T-P|Course|Subject)\b', line_str, re.I) # Syllabus
                    )
                    if is_table_like or len(cells) >= 3:
                        formatted_rows.append(" | ".join(cells))

        return formatted_rows

    def extract_document_data(
        self, 
        filepath: Path, 
        parent_url: str = "", 
        link_text: str = "", 
        nearby_heading: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Extracts structured document data page by page.
        Connects document to parent page metadata (parent_url, link_text, nearby_heading).
        Extracts structured tables instead of mushing columns together.
        Detects scanned pages with no text layer and sets needs_manual_review = True.
        """
        pages_data = []
        try:
            doc = fitz.open(filepath)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                raw_text = page.get_text("text").strip()
                
                needs_manual_review = False
                is_scanned = False
                
                # Check for scanned page: very little or no native text
                if len(raw_text) < 50:
                    is_scanned = True
                    try:
                        # Render page to image and attempt OCR
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        
                        ocr_text = pytesseract.image_to_string(img).strip()
                        if len(ocr_text) < 50:
                            needs_manual_review = True
                        else:
                            raw_text = ocr_text
                    except Exception as e:
                        print(f"OCR failed for {filepath.name} page {page_num + 1}: {e}")
                        needs_manual_review = True

                # Extract structured tables
                table_rows = self.extract_tables_from_page(page)
                
                # Clean regular text
                clean_text = re.sub(r'[ \t]+', ' ', raw_text).strip()
                
                # If structured tables exist, format them clearly so columns are not mushed
                table_section = ""
                if table_rows:
                    table_section = "\n\n--- STRUCTURED TABLES / TIMETABLE ROWS ---\n" + "\n".join(table_rows) + "\n-----------------------------------------\n"

                full_content = clean_text + table_section

                pages_data.append({
                    "page_num": page_num + 1,
                    "content": full_content.strip(),
                    "tables": table_rows,
                    "has_tables": len(table_rows) > 0,
                    "is_scanned": is_scanned,
                    "needs_manual_review": needs_manual_review,
                    "needs_review": needs_manual_review,  # Backwards compatibility
                    "parent_url": parent_url,
                    "link_text": link_text,
                    "nearby_heading": nearby_heading,
                    "source_file": filepath.name
                })
            doc.close()
            return pages_data
        except Exception as e:
            print(f"Error processing PDF {filepath}: {e}")
            return [{
                "page_num": 1,
                "content": "",
                "tables": [],
                "has_tables": False,
                "is_scanned": True,
                "needs_manual_review": True,
                "needs_review": True,
                "parent_url": parent_url,
                "link_text": link_text,
                "nearby_heading": nearby_heading,
                "source_file": filepath.name if hasattr(filepath, 'name') else str(filepath)
            }]

    def extract_text_from_pdf(self, filepath: Path) -> List[Dict[str, Any]]:
        """Backwards-compatible wrapper around extract_document_data."""
        return self.extract_document_data(filepath)
