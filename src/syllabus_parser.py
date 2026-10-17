import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import json
import re
from typing import Dict, Any, List
from openai import OpenAI

class SyllabusParser:
    def __init__(self):
        api_key = getattr(config, "OPENROUTER_API_KEY", "")
        if api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
        else:
            self.client = None

    def extract_metadata_from_text(self, text: str, url: str, link_text: str) -> Dict[str, Any]:
        """Extract Regulation, Branch, Year, Sem from text/url/link_text"""
        # Very simple regex fallback if LLM is not used
        reg_match = re.search(r'\b(R[1-2][0-9])\b', text + url + link_text, re.IGNORECASE)
        regulation = reg_match.group(1).upper() if reg_match else "UNKNOWN"
        
        branch = "UNKNOWN"
        for b in ["CSE", "ECE", "EEE", "ME", "CE", "CST", "CSBS"]:
            if re.search(r'\b' + b + r'\b', text + url + link_text, re.IGNORECASE):
                branch = b
                break
                
        # For a full extraction, we use LLM 
        return {"regulation": regulation, "branch": branch}

    def parse_page(self, page_text: str, page_num: int, doc_url: str, doc_metadata: Dict[str, str]) -> List[Dict[str, Any]]:
        if not self.client or len(page_text.strip()) < 100:
            return []

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
            # Remove possible markdown backticks
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
            print(f"Error parsing syllabus page {page_num}: {e}")
            return []

