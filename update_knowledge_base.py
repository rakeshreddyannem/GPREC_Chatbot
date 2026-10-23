import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from src.crawler import GPRECCrawler
from src.notice_ingest import ingest_notices_from_documents
from ingest import run_ingestion
from src.rag_pipeline import clear_answer_cache

def generate_markdown_report(report_data: dict) -> str:
    timestamp = report_data.get("timestamp", datetime.now().isoformat())
    new_items = report_data.get("new", [])
    mod_items = report_data.get("modified", [])
    rem_items = report_data.get("removed", [])
    unchanged_count = report_data.get("unchanged_count", 0)
    total_chunks = report_data.get("total_chunks", 0)

    lines = [
        "# Knowledge Base Update Report",
        f"**Generated:** {timestamp}\n",
        "## Summary",
        "| Category | Count |",
        "|---|---|",
        f"| NEW Items | {len(new_items)} |",
        f"| MODIFIED Items | {len(mod_items)} |",
        f"| REMOVED Items | {len(rem_items)} |",
        f"| UNCHANGED Items | {unchanged_count} |",
        f"| Total Vectors in Index | {total_chunks} |\n",
    ]

    lines.append(f"## NEW Items ({len(new_items)})")
    if new_items:
        for item in new_items:
            lines.append(f"- [{item.get('title') or item.get('url')}]({item.get('url')}) `({item.get('type', 'item')})`")
    else:
        lines.append("- *None*")
    lines.append("")

    lines.append(f"## MODIFIED Items ({len(mod_items)})")
    if mod_items:
        for item in mod_items:
            lines.append(f"- [{item.get('title') or item.get('url')}]({item.get('url')}) `({item.get('type', 'item')})`")
    else:
        lines.append("- *None*")
    lines.append("")

    lines.append(f"## REMOVED Items ({len(rem_items)})")
    if rem_items:
        for item in rem_items:
            lines.append(f"- [{item.get('title') or item.get('url')}]({item.get('url')}) `({item.get('type', 'item')})`")
    else:
        lines.append("- *None*")
    lines.append("")

    return "\n".join(lines)

def run_update():
    print("==================================================")
    print("GPREC AI Assistant - Knowledge Base Update Pipeline")
    print("==================================================")
    start_time = time.time()

    # Step 1: Run Crawler
    print("\n[Step 1/5] Running Web Crawler for Change Detection...")
    crawler = GPRECCrawler()
    crawler.run()

    # Step 2: Run Notice Ingest
    print("\n[Step 2/5] Running Notice & Deadline Ingestion...")
    ingest_notices_from_documents(crawler.db)

    # Step 3: Run Faculty Directory Ingestion & Updates
    print("\n[Step 3/5] Running Faculty Directory Ingestion & Updates...")
    from src.faculty_parser import ingest_all_departments
    ingest_all_departments(db=crawler.db, download_photos=True)

    # Step 4: Run Vector Embedding and Ingestion
    print("\n[Step 4/5] Running Vector Store Ingestion (Incremental Update)...")
    ingest_report = run_ingestion(db=crawler.db)

    # Step 5: Clear Answer Cache
    print("\n[Step 5/5] Clearing Answer Cache...")
    cleared = clear_answer_cache()
    print(f"Cleared {cleared} cache resource(s).")

    # Generate and save reports in data/reports/
    reports_dir = config.DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = reports_dir / "update_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ingest_report, f, indent=2)
    print(f"\nSaved update report to: {json_path}")

    md_report = generate_markdown_report(ingest_report)
    md_path = reports_dir / "update_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"Saved readable report to: {md_path}")

    elapsed = time.time() - start_time
    print(f"\nUpdate Complete in {elapsed:.2f} seconds!")
    return ingest_report

if __name__ == "__main__":
    run_update()
