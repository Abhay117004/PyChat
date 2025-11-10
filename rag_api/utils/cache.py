from functools import lru_cache
from typing import List, Tuple
import hashlib


class EmbeddingCache:

    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def _hash_query(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str) -> List[float]:
        key = self._hash_query(query)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    def set(self, query: str, embedding: List[float]) -> None:
        if len(self.cache) >= self.max_size:
            self.cache.pop(next(iter(self.cache)))

        key = self._hash_query(query)
        self.cache[key] = embedding

    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }

    def clear(self) -> None:
        self.cache.clear()
        self.hits = 0
        self.misses = 0


class RewriteCache:

    def __init__(self, max_size: int = 500):
        self.cache = {}
        self.max_size = max_size

    def _hash_query(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str) -> str:
        key = self._hash_query(query)
        return self.cache.get(key)

    def set(self, query: str, rewritten: str) -> None:
        if len(self.cache) >= self.max_size:
            self.cache.pop(next(iter(self.cache)))

        key = self._hash_query(query)
        self.cache[key] = rewritten

    def clear(self) -> None:
        self.cache.clear()


embedding_cache = EmbeddingCache()
rewrite_cache = RewriteCache()
