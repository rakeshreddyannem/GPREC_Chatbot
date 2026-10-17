import hashlib
from typing import Dict, Any, Tuple
from .database import DatabaseManager

class ChangeDetector:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def generate_hash(self, content: str) -> str:
        """Generates SHA-256 hash of the content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def check_page_status(self, url: str, content: str) -> Tuple[str, str, int]:
        """
        Returns (status, content_hash, version)
        status can be: 'NEW', 'UNCHANGED', 'MODIFIED'
        """
        content_hash = self.generate_hash(content)
        existing_page = self.db.get_page_by_url(url)

        if not existing_page:
            return "NEW", content_hash, 1

        if existing_page["content_hash"] == content_hash:
            return "UNCHANGED", content_hash, existing_page["version"]

        # If hashes differ, it's a modification. We increment the version.
        return "MODIFIED", content_hash, existing_page["version"] + 1
