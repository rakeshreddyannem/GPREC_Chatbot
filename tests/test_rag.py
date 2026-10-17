import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.vectorstore import VectorStore
from src.embeddings import Embedder
from src.rag_pipeline import RAGPipeline

def run_test():
    print("Loading pipeline...")
    embedder = Embedder()
    vstore = VectorStore(embedder.dimension)
    pipeline = RAGPipeline(embedder, vstore)
    
    query = "What departments are available at the college?"
    print(f"\nQuery: {query}")
    
    print("\nGenerating response from Gemini...")
    result = pipeline.answer_question(query)
    
    print("\n=== ANSWER ===")
    print(result.get("answer"))
    print("\n=== SOURCES ===")
    for s in result.get("sources", []):
        print(f"- {s.get('title')} ({s.get('source_url')})")

if __name__ == "__main__":
    run_test()
