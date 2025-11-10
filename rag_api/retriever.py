from typing import List, Dict, Optional
import asyncio, json, hashlib
from sentence_transformers import CrossEncoder, SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from rank_bm25 import BM25Okapi
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION

from config import settings, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
from .utils.logging import log_success, log_warning, log_step, timeit
from .utils.cache import embedding_cache


class Retriever:
    def __init__(self):
        self.embedding_model = SentenceTransformer(settings.embedding_model_name)
        self.bm25_index = None
        self.document_cache = {}
        self.retrieval_cache = {}
        self.reranker = self._load_reranker()

        log_step("Database", f"Connecting to Qdrant Cloud collection '{QDRANT_COLLECTION}'")
        self.qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.collection_name = QDRANT_COLLECTION
        self._build_bm25_index()

    def _load_reranker(self) -> Optional[CrossEncoder]:
        if not settings.enable_reranking:
            return None
        try:
            log_step("Reranker", f"Loading {settings.reranker_model_name}")
            reranker = CrossEncoder(settings.reranker_model_name)
            log_success("Reranker loaded successfully")
            return reranker
        except Exception as e:
            log_warning(f"Could not load reranker: {e}")
            return None

    def _build_bm25_index(self):
        try:
            log_step("BM25", "Building keyword index from Qdrant payloads...")
            docs = self.qdrant.scroll(collection_name=self.collection_name, limit=50000)[0]
            texts = [p.payload.get("text", "") for p in docs if p.payload.get("text")]
            metas = [p.payload for p in docs]
            tokenized_docs = [t.lower().split() for t in texts]
            self.bm25_index = BM25Okapi(tokenized_docs)
            self.document_cache = {i: {"text": t, "metadata": m} for i, (t, m) in enumerate(zip(texts, metas))}
            log_success(f"BM25 index built with {len(self.document_cache):,} docs")
        except Exception as e:
            log_warning(f"Could not build BM25 index: {e}")

    @timeit
    async def embed_query(self, query: str) -> List[float]:
        cached = embedding_cache.get(query)
        if cached is not None:
            log_step("Cache", "Embedding cache hit")
            return cached
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(None, lambda: self.embedding_model.encode([query]).tolist()[0])
        embedding_cache.set(query, embedding)
        return embedding

    @timeit
    async def retrieve(self, query_embedding: List[float], n_results: int = None) -> List[Dict]:
        n_results = n_results or settings.top_k_results * settings.retrieval_candidate_multiplier
        n_results = min(n_results, 50)
        hits = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=n_results,
            with_payload=True,
        )
        candidates = [{"text": h.payload.get("text", ""), "metadata": h.payload, "score": float(h.score)} for h in hits]
        log_step("Retrieval", f"Retrieved {len(candidates)} results from Qdrant Cloud")
        return candidates

    @timeit
    async def hybrid_retrieve(self, query: str, n_results: int = None) -> List[Dict]:
        query_emb = await self.embed_query(query)
        semantic = await self.retrieve(query_emb, n_results)
        if not self.bm25_index:
            return semantic
        loop = asyncio.get_running_loop()
        bm25_scores = await loop.run_in_executor(None, self.bm25_index.get_scores, query.lower().split())
        bm25_results = []
        for idx in sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:n_results]:
            if idx in self.document_cache:
                bm25_results.append({
                    "text": self.document_cache[idx]["text"],
                    "metadata": self.document_cache[idx]["metadata"],
                    "score": float(bm25_scores[idx])
                })
        merged = self._merge_results(semantic, bm25_results)
        log_step("Hybrid", f"Merged {len(merged)} hybrid results")
        return merged

    def _merge_results(self, semantic: List[Dict], bm25: List[Dict]) -> List[Dict]:
        seen = {}
        for d in semantic:
            sig = d["text"][:100]
            seen[sig] = {"doc": d, "semantic_score": d["score"], "bm25_score": 0.0}
        for d in bm25:
            sig = d["text"][:100]
            if sig in seen:
                seen[sig]["bm25_score"] = d["score"]
            else:
                seen[sig] = {"doc": d, "semantic_score": 0.0, "bm25_score": d["score"]}
        merged = []
        for entry in seen.values():
            sem = entry["semantic_score"]
            bm25n = entry["bm25_score"] / 10.0 if entry["bm25_score"] > 0 else 0.0
            entry["doc"]["score"] = (sem * 0.7) + (bm25n * 0.3)
            merged.append(entry["doc"])
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged

    async def get_top_documents(self, query: str, intent: str, k: int = None) -> List[Dict]:
        k = k or settings.top_k_results
        cache_key = hashlib.md5(f"{query}_{intent}".encode()).hexdigest()
        if cache_key in self.retrieval_cache:
            log_step("Cache", "Retrieval cache hit")
            return self.retrieval_cache[cache_key]
        candidates = await self.hybrid_retrieve(query, k * 3)
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
        top_docs = candidates[:k]
        self.retrieval_cache[cache_key] = top_docs
        return top_docs

    def get_stats(self) -> Dict:
        try:
            count = self.qdrant.count(self.collection_name).count
            return {"total_chunks": count, "unique_pages": 0, "average_quality": 0.0, "content_types": {}}
        except Exception:
            return {"total_chunks": 0, "unique_pages": 0, "average_quality": 0.0, "content_types": {}}
