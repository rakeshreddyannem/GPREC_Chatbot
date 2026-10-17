import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.vectorstore import VectorStore
from src.embeddings import Embedder

def run_test():
    print("Loading embedder and vector store...")
    embedder = Embedder()
    vstore = VectorStore(embedder.dimension)
    
    query = "What departments are available?"
    print(f"\nQuery: {query}")
    query_emb = embedder.embed_text(query)
    
    results = vstore.search(query_emb, query_text=query, top_k=5)
    
    print(f"\nTop {len(results)} Results:")
    for i, res in enumerate(results, 1):
        score = res.get("score", 0.0)
        title = res.get("title", "No Title")
        url = res.get("source_url", "")
        preview = res.get("content", "")[:200].replace('\n', ' ')
        print(f"\n[{i}] Score: {score:.4f} | {title} | {url}")
        print(f"Content Preview: {preview}...")

if __name__ == "__main__":
    run_test()
