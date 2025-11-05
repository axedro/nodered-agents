"""
Embedding generation using sentence-transformers
"""
from sentence_transformers import SentenceTransformer
from typing import List
from loguru import logger


class EmbeddingGenerator:
    """Generate embeddings for text using sentence-transformers"""

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding generator
        Args:
            model_name: HuggingFace model name for embeddings
        """
        if self._model is None:
            logger.info(f"Loading embedding model: {model_name}")
            self._model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")

    def generate(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        return self._model.encode(text).tolist()

    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = self._model.encode(texts)
        return [emb.tolist() for emb in embeddings]
