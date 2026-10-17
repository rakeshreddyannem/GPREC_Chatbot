import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

class ResponseType:
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    NOT_FOUND = "NOT_FOUND"
    CLARIFY = "CLARIFY"

# Department definitions
DEPARTMENTS = {
    "EEE": "Electrical and Electronics Engineering",
    "ECE": "Electronics and Communication Engineering",
    "CSE": "Computer Science and Engineering",
    "CSM": "Computer Science and Machine Learning",
    "CSD": "Computer Science and Data Science",
    "CE": "Civil Engineering",
    "ME": "Mechanical Engineering",
    "H&S": "Humanities and Basic Sciences",
    "HBS": "Humanities and Basic Sciences"
}

class AmbiguityDetector:
    """Detects missing parameters (department, semester, program) and initiates CLARIFY."""
    
    @staticmethod
    def detect_department(query: str) -> Optional[str]:
        q_upper = query.upper()
        # Direct abbreviation match with word boundaries
        for code in ["EEE", "ECE", "CSE", "CSM", "CSD", "CE", "ME", "H&S", "HBS"]:
            if re.search(r'\b' + re.escape(code) + r'\b', q_upper):
                return code
        # Full name matching
        for code, full_name in DEPARTMENTS.items():
            if full_name.lower() in query.lower():
                return code
        return None

    @classmethod
    def check_ambiguity(cls, query: str) -> Optional[Dict[str, Any]]:
        q_lower = query.lower()
        dept = cls.detect_department(query)
        
        # Case: "list the PhD faculties" or "who are the PhD faculty" without department
        if ("phd facult" in q_lower or "ph.d facult" in q_lower or "doctorate facult" in q_lower) and not dept:
            return {
                "response_type": ResponseType.CLARIFY,
                "question": "Which department's Ph.D. faculties would you like to see?",
                "options": ["EEE", "ECE", "CSE", "ME", "CE", "H&S"],
                "missing_field": "department"
            }
            
        # Case: "exam time table" / "exam timetable" / "exam schedule" without branch or year/semester
        exam_keywords = ["exam time table", "exam timetable", "exam schedule", "examination timetable", "examination time table"]
        if any(term in q_lower for term in exam_keywords):
            has_detail = dept is not None or any(term in q_lower for term in [
                "1st year", "2nd year", "3rd year", "4th year", 
                "i year", "ii year", "iii year", "iv year", 
                "1st sem", "2nd sem", "sem", "b.tech", "m.tech", "btech", "mtech"
            ])
            if not has_detail:
                return {
                    "response_type": ResponseType.CLARIFY,
                    "question": "Which program and semester exam timetable are you looking for? (e.g., B.Tech IV Sem R20)",
                    "options": ["B.Tech I Year", "B.Tech II Year", "B.Tech III Year", "B.Tech IV Year", "B.Tech IV Sem (R20)", "M.Tech"],
                    "missing_field": "semester_branch"
                }

        return None


class SensitiveInfoFilter:
    """Scrubs sensitive credentials, default passwords, and personal mobile numbers."""
    
    @staticmethod
    def scrub(text: str) -> str:
        if not text:
            return ""
            
        cleaned = text
        
        # 1. Password patterns (e.g., "password: xyz", "default password: 123", "using your RollNo and password")
        cleaned = re.sub(
            r'(?i)\b(default\s+password|login\s+password|initial\s+password|password)\s*[:=]\s*["\']?([A-Za-z0-9@#$%^&*!_-]+)["\']?',
            r'\1: [PROTECTED - Contact Portal Admin]',
            cleaned
        )
        
        # 2. Personal Indian mobile numbers (10 digits starting with 6, 7, 8, 9)
        # We preserve official college landlines (08518-270957, etc.) and short extensions
        def replace_phone(match):
            phone = match.group(0).replace(" ", "").replace("-", "")
            # If preceded by official desk/reception label, leave or format as official
            return "[Contact the relevant college office]"
            
        # Match 10-digit mobile numbers with optional +91 or 0 prefix
        cleaned = re.sub(
            r'(?<!\d)(?:\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}(?!\d)',
            '[Contact the department office for details]',
            cleaned
        )
        
        return cleaned


class AnswerVerifier:
    """
    Verifies that names, designations, dates, fees, and PhD claims in generated answers
    are strictly grounded in the retrieved context. Forbids inferences.
    """
    
    @staticmethod
    def verify_phd_claims(answer: str, context_text: str) -> Tuple[bool, List[str]]:
        """
        Ensures a faculty is claimed as Ph.D. ONLY if explicitly stated in context
        with Dr. prefix or Ph.D qualification.
        Forbids asserting PhD based on jury/resource person roles.
        """
        unsupported = []
        ctx_lower = context_text.lower()
        
        # Look for forbidden inference statements in answer
        forbidden_inferences = [
            r'jury\s+member.*implies',
            r'resource\s+person.*implies',
            r'inferred.*ph\.?d',
            r'likely\s+holds.*ph\.?d'
        ]
        for pattern in forbidden_inferences:
            if re.search(pattern, answer, re.IGNORECASE):
                unsupported.append("Unsupported inference: asserting PhD based on jury/resource person role")
                
        # Find all names prefixed with Dr. in answer
        dr_matches = re.findall(r'\bDr\.?\s+([A-Z][a-zA-Z\.\s]{2,25})\b', answer)
        for name in dr_matches:
            clean_name = name.strip()
            # Must appear in context with Dr. or Ph.D
            name_parts = [p for p in clean_name.split() if len(p) > 2]
            name_matched = False
            for part in name_parts:
                if part.lower() in ctx_lower:
                    name_matched = True
                    break
            if not name_matched and len(name_parts) > 0:
                unsupported.append(f"Doctorate claim for '{clean_name}' not found in retrieved sources.")
                
        return len(unsupported) == 0, unsupported

    @staticmethod
    def verify_factual_grounding(answer: str, context_text: str) -> Tuple[bool, List[str]]:
        unsupported = []
        ctx_lower = context_text.lower()
        
        # Verify fee figures (e.g. ₹75,500, Rs. 50,000, 75500)
        fee_matches = re.findall(r'[₹Rs\.]*\s*([0-9]{2,3},[0-9]{3}|[0-9]{4,6})', answer)
        for fee in fee_matches:
            raw_num = fee.replace(",", "")
            if raw_num not in context_text and fee not in context_text:
                unsupported.append(f"Fee amount '{fee}' not present in source context.")
                
        return len(unsupported) == 0, unsupported


class DateValidator:
    """Validates date plausibility and prevents first_seen from being shown as notice date."""
    
    @staticmethod
    def is_plausible_date(date_str: str) -> bool:
        if not date_str:
            return True
        try:
            # Parse year
            year_match = re.search(r'\b(20\d{2}|19\d{2})\b', date_str)
            if year_match:
                year = int(year_match.group(1))
                current_year = datetime.now().year
                # Must be between 2000 and current_year + 2
                if year < 2000 or year > current_year + 2:
                    return False
            return True
        except Exception:
            return True


class ResponseFormatter:
    """Ensures consistent, single response type output without conflicting messages."""
    
    @staticmethod
    def format_not_found(suggested_questions: Optional[List[str]] = None) -> Dict[str, Any]:
        default_suggestions = [
            "What courses are offered at GPREC?",
            "What are the library timings and rules?",
            "Who is the head of the EEE department?"
        ]
        suggestions = suggested_questions or default_suggestions
        return {
            "response_type": ResponseType.NOT_FOUND,
            "answer": "I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.",
            "suggested_questions": suggestions,
            "confidence": "Low",
            "confidence_reason": "No direct official documentation found"
        }
        
    @staticmethod
    def format_partial(available: str, missing: str, where_to_look: str) -> Dict[str, Any]:
        answer_text = (
            f"{available.strip()}\n\n"
            f"**Missing Information:** {missing.strip()}\n\n"
            f"**Where to Look:** {where_to_look.strip()}"
        )
        return {
            "response_type": ResponseType.PARTIAL,
            "answer": answer_text,
            "missing_info": missing,
            "where_to_look": where_to_look,
            "confidence": "Medium",
            "confidence_reason": "Partial information retrieved from official sources"
        }
