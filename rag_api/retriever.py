import asyncio
import json
import hashlib
from typing import List, Dict, Optional
import chromadb
from sentence_transformers import CrossEncoder
from rank_bm25 import BM25Okapi

from config import settings
from embeddings import get_embedding_engine
from .utils.logging import log_success, log_warning, log_step, timeit
from .utils.cache import embedding_cache


class Retriever:
    def __init__(self):
        self.embedding_model = get_embedding_engine()
        self.bm25_index = None
        self.document_cache = {}
        self.retrieval_cache = {}
        self.reranker = self._load_reranker()
        self.collection = self._load_collection()

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

    def _load_collection(self) -> Optional[chromadb.Collection]:
        try:
            log_step("Database", f"Loading from {settings.vector_database_path}")
            db = chromadb.PersistentClient(path=str(settings.vector_database_path))
            collection = db.get_collection(settings.collection_name)
            count = collection.count()
            log_success(f"Loaded {count:,} chunks from database")
            if count > 0:
                self._build_bm25_index(collection)
            return collection
        except Exception as e:
            log_warning(f"No collection found: {e}")
            return None

    def _build_bm25_index(self, collection: chromadb.Collection):
        try:
            log_step("BM25", "Building keyword index...")
            count = collection.count()
            if count == 0:
                return
            results = collection.get(include=["documents", "metadatas"])
            if not results["documents"]:
                return
            tokenized_docs = [doc.lower().split() for doc in results["documents"]]
            self.bm25_index = BM25Okapi(tokenized_docs)
            for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
                self.document_cache[i] = {"text": doc, "metadata": meta}
            log_success(f"BM25 index built with {len(self.document_cache):,} documents")
        except Exception as e:
            log_warning(f"Could not build BM25 index: {e}")
            self.bm25_index = None
            self.document_cache = {}

    @timeit
    async def embed_query(self, query: str) -> List[float]:
        cached = embedding_cache.get(query)
        if cached is not None:
            log_step("Cache", "Embedding cache hit")
            return cached
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None, lambda: self.embedding_model.model.encode([query]).tolist()[0]
        )
        embedding_cache.set(query, embedding)
        return embedding

    @timeit
    async def retrieve(self, query_embedding: List[float], n_results: int = None) -> List[Dict]:
        if self.collection is None:
            return []
        if n_results is None:
            n_results = settings.top_k_results * settings.retrieval_candidate_multiplier
        n_results = min(n_results, 100)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        if not results["ids"][0]:
            return []
        candidates = [
            {"text": doc, "metadata": meta, "score": 1.0 - dist}
            for doc, meta, dist in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            )
        ]
        log_step("Retrieval", f"Retrieved {len(candidates)} candidates")
        return candidates

    @timeit
    async def boost_and_deduplicate(self, candidates: List[Dict], query: str, intent: str) -> List[Dict]:
        for c in candidates:
            try:
                quality = c["metadata"].get("quality", "{}")
                if isinstance(quality, str):
                    quality = json.loads(quality)
                q_score = quality.get("score", 0)
                ctype = quality.get("content_type", "general")
                boost = 1.0
                if settings.enable_quality_weighted_search:
                    boost *= 1.0 + (q_score / 100) * 0.5
                boost *= settings.content_type_weights.get(ctype, 1.0)
                text = c["text"].lower()
                if intent in ["code", "howto"]:
                    if "```" in text or "def " in text:
                        boost *= 1.5
                    if "example" in text:
                        boost *= 1.3
                elif intent == "example" and "```" in text:
                    boost *= 1.6
                elif intent == "comparison" and any(w in text for w in ["vs", "compare", "difference"]):
                    boost *= 1.4
                elif intent == "debug" and any(w in text for w in ["error", "exception", "fix"]):
                    boost *= 1.3
                c["score"] *= boost
            except Exception:
                continue
        candidates.sort(key=lambda x: x["score"], reverse=True)
        seen, unique = set(), []
        for c in candidates:
            sig = c["text"][:100].lower()
            if sig not in seen:
                seen.add(sig)
                unique.append(c)
        log_step("Boost", f"Boosted and deduplicated to {len(unique)} unique docs")
        return unique

    @timeit
    async def hybrid_retrieve(self, query: str, n_results: int = None) -> List[Dict]:
        if n_results is None:
            n_results = settings.top_k_results * settings.retrieval_candidate_multiplier
        query_emb = await self.embed_query(query)
        semantic = await self.retrieve(query_emb, n_results)
        if not self.bm25_index:
            return semantic
        loop = asyncio.get_running_loop()
        bm25_scores = await loop.run_in_executor(None, self.bm25_index.get_scores, query.lower().split())
        bm25_results = []
        for idx in sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:n_results]:
            if idx in self.document_cache:
                bm25_results.append(
                    {"text": self.document_cache[idx]["text"], "metadata": self.document_cache[idx]["metadata"], "score": float(bm25_scores[idx])}
                )
        merged = self._merge_results(semantic, bm25_results)
        log_step("Hybrid", f"Merged {len(merged)} candidates from semantic + BM25")
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
    
    async def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        if not self.reranker or not candidates:
            return candidates

        pairs = [(query, c["text"][:512]) for c in candidates[:20]]

        loop = asyncio.get_running_loop()
        try:
            scores = await loop.run_in_executor(
                None,
                lambda: self.reranker.predict(
                    pairs,
                    batch_size=32,
                    show_progress_bar=False
                ),
            )
        except Exception as e:
            log_warning(f"Reranker failed: {e}")
            return candidates

        for i, score in enumerate(scores):
            candidates[i]["score"] = float(score) * 0.7 + candidates[i]["score"] * 0.3

        candidates.sort(key=lambda x: x["score"], reverse=True)
        log_step("Rerank", f"Reranked {len(pairs)} candidates")
        return candidates


    async def get_top_documents(self, query: str, intent: str, k: int = None) -> List[Dict]:
        k = k or settings.top_k_results
        cache_key = hashlib.md5(f"{query}_{intent}".encode()).hexdigest()
        if cache_key in self.retrieval_cache:
            log_step("Cache", "Retrieval cache hit")
            return self.retrieval_cache[cache_key]
        candidates = await self.hybrid_retrieve(query)
        if not candidates:
            return []
        candidates = await self.boost_and_deduplicate(candidates, query, intent)
        if self.reranker:
            candidates = await self.rerank(query, candidates)
        top_docs = candidates[:k]
        self.retrieval_cache[cache_key] = top_docs
        if len(self.retrieval_cache) > 500:
            self.retrieval_cache.pop(next(iter(self.retrieval_cache)))
        return top_docs

    def get_stats(self) -> Dict:
        if self.collection is None:
            return {"total_chunks": 0, "unique_pages": 0, "average_quality": 0.0, "content_types": {}}
        try:
            count = self.collection.count()
            results = self.collection.get(include=["metadatas"], limit=count)
        except Exception:
            return {"total_chunks": 0, "unique_pages": 0, "average_quality": 0.0, "content_types": {}}

        metadatas = results.get("metadatas", [])
        unique_urls = len({m.get("url") for m in metadatas if m.get("url")})
        total_quality, q_count, content_types = 0, 0, {}

        for meta in metadatas:
            try:
                quality = meta.get("quality", "{}")
                if isinstance(quality, str):
                    quality = json.loads(quality)
                score = float(quality.get("score", 0))
                if score > 0:
                    total_quality += score
                    q_count += 1
                ctype = quality.get("content_type", "general")
                content_types[ctype] = content_types.get(ctype, 0) + 1
            except Exception:
                continue

        avg_quality = round(total_quality / q_count, 1) if q_count else 0.0
        return {
            "total_chunks": count,
            "unique_pages": unique_urls,
            "average_quality": avg_quality,
            "content_types": content_types,
        }
