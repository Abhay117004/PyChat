import asyncio
import requests
from typing import List, Dict, Any
from loguru import logger
from qdrant_client import QdrantClient
from config import settings
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
from .utils.cache import embedding_cache
import os

IS_RENDER = os.environ.get("RENDER", "false").lower() == "true"

class Retriever:
    def __init__(self):
        self.collection_name = QDRANT_COLLECTION
        self.qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        self.embedding_model = None
        self.reranker = None
        self.bm25_index = None
        self.document_cache = {}
        self.retrieval_cache = {}

        # Try local models only if not on Render
        if not IS_RENDER:
            try:
                from sentence_transformers import SentenceTransformer, CrossEncoder
                self.embedding_model = SentenceTransformer(settings.embedding_model_name)
                self.reranker = CrossEncoder(settings.reranker_model_name)
                logger.success(f"Loaded local embedding model: {settings.embedding_model_name}")
                logger.success(f"Loaded local reranker model: {settings.reranker_model_name}")
            except Exception as e:
                logger.warning(f"Local model load failed. Falling back to Jina API: {e}")
        else:
            logger.info("Render environment detected. Skipping local model loading, using Jina APIs instead.")

        # API endpoints for Jina fallback
        self.jina_key = settings.JINA_API_KEY
        self.jina_embed_url = "https://api.jina.ai/v1/embeddings"
        self.jina_rerank_url = "https://api.jina.ai/v1/rerank"

        try:
            self._build_bm25_index()
        except Exception as e:
            logger.warning(f"BM25 index build skipped: {e}")

    async def embed_query(self, query: str) -> List[float]:
        if not query:
            logger.warning("Empty query received for embedding.")
            return []

        cached = embedding_cache.get(query)
        if cached is not None:
            logger.debug("Using cached embedding.")
            return cached

        # Use local SentenceTransformer if available
        if self.embedding_model:
            try:
                emb = self.embedding_model.encode([query])[0]
                embedding_cache.set(query, emb)
                return emb
            except Exception as e:
                logger.error(f"Local embedding failed: {e}")

        # Fallback to Jina Cloud embeddings
        if not self.jina_key:
            logger.error("No JINA_API_KEY provided for fallback embedding.")
            return []

        headers = {"Authorization": f"Bearer {self.jina_key}", "Content-Type": "application/json"}
        payload = {"model": "jina-embeddings-v2-base-en", "input": [query]}

        try:
            res = requests.post(self.jina_embed_url, headers=headers, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json().get("data", [])
            if not data:
                logger.error("Jina returned empty embedding response.")
                return []
            emb = data[0]["embedding"]
            embedding_cache.set(query, emb)
            return emb
        except Exception as e:
            logger.error(f"Jina embedding API failed: {e}")
            return []

    async def retrieve(self, query_embedding: List[float], n_results: int = None) -> List[Dict]:
        n_results = n_results or settings.top_k_results * settings.retrieval_candidate_multiplier
        try:
            hits = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=n_results,
                with_payload=True,
            )
            docs = [{"text": h.payload.get("text", ""), "metadata": h.payload, "score": float(h.score)} for h in hits]
            logger.info(f"Retrieved {len(docs)} semantic results from Qdrant.")
            return docs
        except Exception as e:
            logger.error(f"Qdrant retrieval failed: {e}")
            return []

    async def hybrid_retrieve(self, query: str, n_results: int = None) -> List[Dict]:
        query_emb = await self.embed_query(query)
        semantic = await self.retrieve(query_emb, n_results)

        # BM25 optional local text match
        if not self.bm25_index:
            return semantic

        try:
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
            logger.info(f"Merged {len(merged)} hybrid results.")
            return merged
        except Exception as e:
            logger.warning(f"BM25 merge failed: {e}")
            return semantic

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
        cache_key = f"{query}__{intent}"
        if cache_key in self.retrieval_cache:
            logger.debug("Using cached retrieval results.")
            return self.retrieval_cache[cache_key]

        candidates = await self.hybrid_retrieve(query, k * 3)
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
        top_docs = candidates[:k]
        reranked = await self._rerank(query, top_docs, k)
        self.retrieval_cache[cache_key] = reranked
        return reranked

    async def _rerank(self, query: str, docs: List[Dict], k: int = None) -> List[Dict]:
        if not docs:
            return []
        # Local reranker if available
        if self.reranker:
            try:
                pairs = [(query, d["text"]) for d in docs]
                scores = self.reranker.predict(pairs)
                for d, s in zip(docs, scores):
                    d["score"] = float(s)
                docs.sort(key=lambda x: x["score"], reverse=True)
                logger.info("Used local reranker for reranking.")
                return docs[:k] if k else docs
            except Exception as e:
                logger.warning(f"Local reranking failed: {e}")

        # Fallback to Jina Cloud reranker
        if not self.jina_key:
            logger.error("No JINA_API_KEY provided for fallback reranking.")
            return docs[:k] if k else docs

        headers = {"Authorization": f"Bearer {self.jina_key}", "Content-Type": "application/json"}
        payload = {"model": "jina-reranker-v1-base-en", "query": query, "documents": [d["text"] for d in docs]}
        try:
            res = requests.post(self.jina_rerank_url, headers=headers, json=payload, timeout=30)
            res.raise_for_status()
            results = res.json().get("results", [])
            for d, r in zip(docs, results):
                d["score"] = r.get("relevance_score", d.get("score", 0.0))
            docs.sort(key=lambda x: x["score"], reverse=True)
            logger.info("Used Jina Cloud reranker.")
            return docs[:k] if k else docs
        except Exception as e:
            logger.error(f"Jina reranker API failed: {e}")
            return docs[:k] if k else docs

    def _build_bm25_index(self):
        try:
            from rank_bm25 import BM25Okapi
            from qdrant_client.http import models as rest
            hits = self.qdrant.scroll(
                collection_name=self.collection_name,
                scroll_filter=None,
                limit=10000,
                with_payload=True
            )[0]
            docs = [h.payload.get("text", "") for h in hits]
            tokenized = [d.lower().split() for d in docs if isinstance(d, str)]
            self.bm25_index = BM25Okapi(tokenized)
            self.document_cache = {i: {"text": docs[i], "metadata": hits[i].payload} for i in range(len(docs))}
            logger.success(f"BM25 index built with {len(docs)} documents.")
        except Exception as e:
            logger.warning(f"Failed to build BM25 index: {e}")
            self.bm25_index = None

    def get_stats(self) -> Dict:
        try:
            count = self.qdrant.count(self.collection_name).count
            return {"total_chunks": count, "bm25_enabled": bool(self.bm25_index)}
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total_chunks": 0, "bm25_enabled": False}
