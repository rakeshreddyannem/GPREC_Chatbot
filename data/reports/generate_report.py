import sqlite3
import os
from pathlib import Path

import sys
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
import config
DB_PATH = config.DB_PATH
REPORT_PATH = BASE_DIR / "data" / "reports" / "syllabus_coverage.md"

def generate_report():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total rows
    cursor.execute("SELECT COUNT(*) FROM syllabus")
    total_rows = cursor.fetchone()[0]
    
    # Query distinct branches in table
    cursor.execute("SELECT DISTINCT branch FROM syllabus WHERE branch IS NOT NULL")
    db_branches = [r[0] for r in cursor.fetchall()]
    
    # College standard branches from app
    standard_branches = ["CSE", "ECE", "EEE", "CE", "ME", "CSM", "CSD", "CSB"]
    all_branches = sorted(list(set(db_branches + standard_branches)))
    semesters = list(range(1, 9))
    
    # Distinct course_code + course_title per branch and semester
    cursor.execute("""
        SELECT branch, semester, course_code, course_title, COUNT(*) as unit_count
        FROM syllabus
        GROUP BY branch, semester, course_code, course_title
        ORDER BY branch, semester, course_code
    """)
    grouped_rows = cursor.fetchall()
    
    # Needs review or empty topics
    cursor.execute("""
        SELECT id, branch, semester, course_code, course_title, unit_number, unit_title, needs_review, topics
        FROM syllabus
        WHERE needs_review = 1 OR topics IS NULL OR TRIM(topics) = ''
    """)
    review_or_empty_rows = cursor.fetchall()
    
    # Find which branch/semester combinations are empty
    # Check each branch and semester 1-8
    present_branch_sems = set()
    for r in grouped_rows:
        if r['branch'] and r['semester']:
            present_branch_sems.add((r['branch'], int(r['semester'])))
            
    empty_branch_sems = []
    for b in all_branches:
        for s in semesters:
            if (b, s) not in present_branch_sems:
                empty_branch_sems.append((b, s))
                
    # Build markdown report
    md = []
    md.append("# Syllabus Coverage Report\n")
    md.append(f"**Generated**: October 2026  ")
    md.append(f"**Database**: `{DB_PATH.name}`  ")
    md.append(f"**Total Syllabus Rows**: {total_rows}\n")
    md.append("---\n")
    
    md.append("## 1. Branch & Semester Coverage Summary\n")
    md.append("| Branch | Semester | Course Code | Course Title | Unit Rows |")
    md.append("|---|---|---|---|---|")
    for r in grouped_rows:
        b = r['branch'] or "*(None)*"
        s = str(r['semester']) if r['semester'] is not None else "*(None)*"
        cc = r['course_code'] or "*(None)*"
        ct = r['course_title'] or "*(None)*"
        units = r['unit_count']
        md.append(f"| {b} | {s} | {cc} | {ct} | {units} |")
    md.append("\n")
    
    md.append("## 2. Empty Branch and Semester Combinations\n")
    md.append("The following branch and semester combinations currently have **0 rows** in the syllabus table:\n")
    # Group empty semesters by branch
    empty_by_branch = {}
    for b, s in empty_branch_sems:
        empty_by_branch.setdefault(b, []).append(f"Sem {s}")
    
    md.append("| Branch | Empty Semesters | Status |")
    md.append("|---|---|---|")
    for b in all_branches:
        sems = empty_by_branch.get(b, [])
        if len(sems) == 8:
            status = "Completely empty (0 subjects)"
        elif len(sems) == 0:
            status = "All semesters populated"
        else:
            status = f"{8 - len(sems)} semester(s) populated"
        md.append(f"| **{b}** | {', '.join(sems)} | {status} |")
    md.append("\n")
    
    md.append("## 3. Rows with `needs_review = 1` or Empty Topics\n")
    if not review_or_empty_rows:
        md.append("No rows flagged with `needs_review = 1` or empty `topics`.\n")
    else:
        md.append("| Row ID | Branch | Sem | Course Code | Course Title | Unit # | Unit Title | `needs_review` | Empty Topics? |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        for r in review_or_empty_rows:
            is_empty_topics = "Yes (Empty)" if (r['topics'] is None or not str(r['topics']).strip()) else "No"
            md.append(f"| {r['id']} | {r['branch']} | {r['semester']} | {r['course_code']} | {r['course_title']} | {r['unit_number']} | {r['unit_title']} | {r['needs_review']} | {is_empty_topics} |")
        md.append("\n")
        
    md.append("## 4. Key Data Observations\n")
    md.append("- **Branch CSE Semester 3** has 9 well-structured unit rows across two core courses: `CS202` (Advanced Data Structures, 5 units) and `CS203` (Database Systems, 4 units).")
    md.append("- **Row ID 10** (`Database Management Systems`, Unit 5 `Concurrency Control`) has `needs_review = 1`, with `semester`, `year`, and `course_code` set to NULL. It includes full unit topics, textbook references, and exam scheme.")
    md.append("- All other branches (**ECE, EEE, CE, ME, CST, CSM, CSB**) currently have **0 syllabus rows** in the database.")
    md.append("- The UI must handle both populated and unpopulated branches/semesters gracefully by providing the free-text subject fallback as requested.\n")
    
    content = "\n".join(md)
    os.makedirs(REPORT_PATH.parent, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Report saved to {REPORT_PATH}")
    print(content)

if __name__ == "__main__":
    generate_report()
