import sys
import os
import json
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from src.embeddings import Embedder
from src.vectorstore import VectorStore
from src.rag_pipeline import RAGPipeline
from tests.regression.check_rules import evaluate_result

def run_regression_suite(save_as="before_results.json"):
    print("=" * 60)
    print("GPREC AI Student Assistant - Baseline Regression Suite")
    print("=" * 60)
    
    questions_file = Path(__file__).resolve().parent / "questions.json"
    with open(questions_file, "r") as f:
        questions = json.load(f)
        
    print(f"Loaded {len(questions)} baseline questions.")
    print("Initializing Embedder, VectorStore, and RAG Pipeline...")
    sys.stdout.flush()
    
    embedder = Embedder()
    vstore = VectorStore(embedder.dimension)
    pipeline = RAGPipeline(embedder, vstore)
    
    print("\nStarting execution of 13 baseline questions...\n")
    sys.stdout.flush()
    
    results = []
    
    for q in questions:
        q_id = q["id"]
        query = q["query"]
        print(f"[{q_id:02d}/13] Running: \"{query}\"")
        sys.stdout.flush()
        
        start_time = time.time()
        try:
            res = pipeline.answer_question(query)
            elapsed = time.time() - start_time
            
            # Run automated check
            eval_res = evaluate_result(q_id, res)
            
            record = {
                "id": q_id,
                "query": query,
                "category": q.get("category"),
                "expected_behavior": q.get("expected_behavior"),
                "answer": res.get("answer", ""),
                "sources": [
                    {
                        "title": s.get("title", ""),
                        "source_url": s.get("source_url", ""),
                        "page": s.get("page"),
                        "published_date": s.get("published_date")
                    } for s in res.get("sources", [])[:5]
                ],
                "confidence": res.get("confidence", "Unknown"),
                "latency_sec": round(elapsed, 2),
                "check_passed": eval_res["passed"],
                "check_reason": eval_res["reason"]
            }
            results.append(record)
            status_str = "PASS" if eval_res["passed"] else "FAIL"
            print(f"       -> Status: {status_str} | Confidence: {res.get('confidence')} | Latency: {elapsed:.2f}s")
            print(f"       -> Check Reason: {eval_res['reason']}")
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"       -> ERROR: {e}")
            results.append({
                "id": q_id,
                "query": query,
                "category": q.get("category"),
                "expected_behavior": q.get("expected_behavior"),
                "answer": f"ERROR: {str(e)}",
                "sources": [],
                "confidence": "Low",
                "latency_sec": round(elapsed, 2),
                "check_passed": False,
                "check_reason": f"Execution exception: {str(e)}"
            })
        sys.stdout.flush()
        # Brief pause between queries to avoid harsh OpenRouter free rate limits
        time.sleep(1.5)

    # Save to JSON
    output_json_path = Path(__file__).resolve().parent / save_as
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved raw outputs to: {output_json_path}")

    # Generate Markdown Summary
    md_path = output_json_path.with_suffix(".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Regression Results ({output_json_path.stem.upper()})\n\n")
        f.write(f"**Execution Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| # | Query | Check Status | Confidence | Latency | Automated Check Reason |\n")
        f.write("|---|-------|--------------|------------|---------|-------------------------|\n")
        for r in results:
            status_icon = "✅ PASS" if r["check_passed"] else "❌ FAIL"
            f.write(f"| {r['id']} | {r['query']} | {status_icon} | {r['confidence']} | {r['latency_sec']}s | {r['check_reason']} |\n")
        
        f.write("\n\n## Detailed Responses per Question\n\n")
        for r in results:
            f.write(f"### Question {r['id']}: {r['query']}\n\n")
            f.write(f"- **Category:** `{r['category']}`\n")
            f.write(f"- **Expected Behavior:** {r['expected_behavior']}\n")
            f.write(f"- **Automated Check:** {'✅ PASS' if r['check_passed'] else '❌ FAIL'} - {r['check_reason']}\n")
            f.write(f"- **Confidence:** {r['confidence']} | **Latency:** {r['latency_sec']}s\n\n")
            f.write(f"**Output ({output_json_path.stem}):**\n```text\n")
            f.write(r['answer'].strip() + "\n```\n\n")
            f.write("**Retrieved Sources (Top 3):**\n")
            if r['sources']:
                for s in r['sources'][:3]:
                    f.write(f"- [{s['title']}]({s['source_url']})\n")
            else:
                f.write("- *None*\n")
            f.write("\n---\n\n")
            
    print(f"Generated markdown report at: {md_path}")
    print("\nSummary Table:")
    passed_count = sum(1 for r in results if r["check_passed"])
    print(f"Total: {len(results)} | Passed: {passed_count} | Failed: {len(results) - passed_count}")
    return results

if __name__ == "__main__":
    out_name = sys.argv[1] if len(sys.argv) > 1 else "before_results.json"
    run_regression_suite(out_name)

