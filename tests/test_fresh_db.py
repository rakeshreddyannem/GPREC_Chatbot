import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database import DatabaseManager

def test_fresh_database_seeded_tables_are_empty(tmp_path):
    """Verify that a fresh temporary database has empty verified_facts, entity_directory, and notices tables."""
    test_db = tmp_path / "fresh_test.db"
    db = DatabaseManager(db_path=test_db)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verified_facts")
        facts_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM entity_directory")
        entities_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM notices")
        notices_count = cursor.fetchone()[0]

    assert facts_count == 0, f"Expected 0 verified_facts in fresh DB, got {facts_count}"
    assert entities_count == 0, f"Expected 0 entity_directory rows in fresh DB, got {entities_count}"
    assert notices_count == 0, f"Expected 0 notices in fresh DB, got {notices_count}"
