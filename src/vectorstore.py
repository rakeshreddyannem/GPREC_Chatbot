import os
import faiss
import numpy as np
import pickle
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi

import config

class VectorStore:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index_path = config.FAISS_INDEX_PATH
        self.meta_path = config.FAISS_METADATA_PATH
        
        self.index = None
        self.metadata = []
        self.bm25 = None
        
        self.load()

    def _build_bm25(self):
        if self.metadata:
            tokenized_corpus = [doc.get("content", "").lower().split() for doc in self.metadata]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

    def load(self):
        if self.index_path.exists() and self.meta_path.exists():
            print(f"Loading FAISS index from {self.index_path}")
            self.index = faiss.read_index(str(self.index_path))
            with open(self.meta_path, 'rb') as f:
                self.metadata = pickle.load(f)
            self._build_bm25()
        else:
            print("Creating new FAISS index...")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            self.bm25 = None

    def save(self):
        config.FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        self._build_bm25()

    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray):
        if len(chunks) == 0:
            return
            
        # Add vectors to FAISS
        self.index.add(embeddings)
        
        # Add metadata
        self.metadata.extend(chunks)
        
        self.save()

    def search(self, query_embedding: np.ndarray, query_text: str = "", top_k: int = config.TOP_K) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
            
        if len(query_embedding.shape) == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0)
            
        distances, indices = self.index.search(query_embedding, top_k * 3) # fetch more for hybrid reranking
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):
                meta = self.metadata[idx].copy()
                # FAISS L2: lower is better. Normalize roughly:
                semantic_score = 1.0 / (1.0 + float(distances[0][i]))
                meta["semantic_score"] = semantic_score
                meta["idx"] = idx
                results.append(meta)
                
        # If BM25 is available and query_text is provided, combine scores
        if self.bm25 and query_text:
            tokenized_query = query_text.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            
            # Normalize BM25
            max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0
            
            for res in results:
                bm25_sc = bm25_scores[res["idx"]] / max_bm25
                res["keyword_score"] = bm25_sc
                # Hybrid Score
                res["score"] = (config.HYBRID_SEMANTIC_WEIGHT * res["semantic_score"]) + (config.HYBRID_BM25_WEIGHT * res["keyword_score"])
        else:
            for res in results:
                res["score"] = res["semantic_score"]
                
        # Sort by final score descending
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return results[:top_k]
