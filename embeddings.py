from typing import List, Optional
from loguru import logger
from sentence_transformers import SentenceTransformer
import torch
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from config import settings

class EmbeddingEngine(EmbeddingFunction):
    def __init__(self, model_name: str, device: str = 'auto', batch_size: int = 32):
        logger.info(f"Loading HuggingFace model: {model_name}")
        
        if device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
            
        self.model = SentenceTransformer(model_name, device=self.device)
        self.batch_size = batch_size
        logger.success(f"Model loaded on {self.device}")

    def name(self) -> str:
        return settings.embedding_model_name

    def __call__(self, texts: Documents) -> Embeddings:
        cleaned_texts = ["" if doc is None else doc for doc in texts]
        
        try:
            embeddings = self.model.encode(
                cleaned_texts,
                batch_size=self.batch_size,
                convert_to_tensor=False,
                show_progress_bar=False
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error encoding batch: {e}")
            return [[] for _ in cleaned_texts]

    def encode_queries(self, queries: List[str]) -> List[List[float]]:
        try:
            embeddings = self.model.encode(
                queries,
                batch_size=self.batch_size,
                convert_to_tensor=False,
                show_progress_bar=False
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error encoding queries: {e}")
            return [[] for _ in queries]

    def encode_documents(self, documents: List[str]) -> List[List[float]]:
        return self(documents)


_embedding_engine: Optional[EmbeddingEngine] = None

def get_embedding_engine() -> EmbeddingEngine:
    global _embedding_engine
    if _embedding_engine is None:
        _embedding_engine = EmbeddingEngine(
            model_name=settings.embedding_model_name,
            device=settings.embedding_device,
            batch_size=settings.embedding_batch_size
        )
    return _embedding_engine