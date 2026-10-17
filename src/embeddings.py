from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

import config

class Embedder:
    def __init__(self, model_name: str = config.EMBEDDING_MODEL_NAME):
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        
    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode(text, convert_to_numpy=True)
        
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True)
