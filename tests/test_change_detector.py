import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import DatabaseManager
from src.change_detector import ChangeDetector

def test_simulate_changes():
    db = DatabaseManager()
    cd = ChangeDetector(db)
    
    test_url = "https://gprec.ac.in/test-simulation"
    
    # 1. Simulate NEW
    content_v1 = "This is the original content."
    status, chash, version = cd.check_page_status(test_url, content_v1)
    print(f"Test 1 - NEW page: Status={status}, Version={version}")
    
    # Insert it to DB manually
    db.upsert_page({
        "source_url": test_url,
        "content_hash": chash,
        "version": version,
        "status": status,
        "is_current": 1,
        "clean_text": content_v1
    })
    
    # 2. Simulate UNCHANGED
    status, chash2, version2 = cd.check_page_status(test_url, content_v1)
    print(f"Test 2 - UNCHANGED page: Status={status}, Version={version2}")
    
    # 3. Simulate MODIFIED
    content_v2 = "This is the modified content with new information."
    status, chash3, version3 = cd.check_page_status(test_url, content_v2)
    print(f"Test 3 - MODIFIED page: Status={status}, Version={version3}")
    
    # 4. Simulate REMOVED (This happens if the crawler hits 404 and we cross-reference DB)
    # The crawler logic for REMOVED would normally mark a DB entry as is_current=0
    # Let's verify the DB updating works for MODIFIED
    db.upsert_page({
        "source_url": test_url,
        "content_hash": chash3,
        "version": version3,
        "status": status,
        "is_current": 1,
        "clean_text": content_v2
    })
    
    row = db.get_page_by_url(test_url)
    print(f"Verification - Final DB row: Version={row['version']}, Status={row['status']}")
    
if __name__ == "__main__":
    test_simulate_changes()
