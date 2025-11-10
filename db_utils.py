import sqlite3
import time
import re
from typing import Optional, Set
from collections import Counter
from simhash import Simhash
from config import settings

class DedupDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_tables()
        self.seen_titles = self._load_seen_titles()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _create_tables(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    fingerprint TEXT PRIMARY KEY
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS simhashes (
                    simhash TEXT PRIMARY KEY
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS titles (
                    title_hash TEXT PRIMARY KEY,
                    count INTEGER NOT NULL
                )
            """)
    
    def _load_seen_titles(self) -> Counter:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT title_hash, count FROM titles")
            return Counter(dict(cursor.fetchall()))

    def check_duplicate(self, text: str, title: str) -> bool:
        fingerprint = self._calculate_fingerprint(text)
        simhash_val = self._calculate_simhash(text)
        title_hash = str(hash(title))

        if self.seen_titles.get(title_hash, 0) >= settings.duplicate_title_threshold:
            return True

        with self._get_conn() as conn:
            cursor = conn.execute("SELECT 1 FROM fingerprints WHERE fingerprint = ?", (fingerprint,))
            if cursor.fetchone():
                return True
            
            cursor = conn.execute("SELECT simhash FROM simhashes")
            for (existing_hash_str,) in cursor:
                existing_hash = int(existing_hash_str)
                dist = self._hamming_distance(simhash_val, existing_hash)
                if dist <= settings.simhash_hamming_distance:
                    return True

            try:
                conn.execute("INSERT INTO fingerprints (fingerprint) VALUES (?)", (fingerprint,))
                conn.execute("INSERT INTO simhashes (simhash) VALUES (?)", (str(simhash_val),))
                self.seen_titles[title_hash] += 1
                conn.execute(
                    "INSERT OR REPLACE INTO titles (title_hash, count) VALUES (?, ?)",
                    (title_hash, self.seen_titles[title_hash])
                )
            except sqlite3.IntegrityError:
                return True
        
        return False

    def _calculate_fingerprint(self, text: str) -> str:
        normalized = re.sub(r'\s+', '', text.lower())
        shingles = set(normalized[i:i+5] for i in range(len(normalized) - 4))
        return ''.join(sorted(list(shingles)[:100]))

    def _calculate_simhash(self, text: str) -> int:
        return Simhash(text.split()).value
    
    def _hamming_distance(self, a: int, b: int) -> int:
        x = (a ^ b) & ((1 << 64) - 1)
        dist = 0
        while x:
            dist += 1
            x &= x - 1
        return dist

    def close(self):
        pass

class MetadataDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_table()
        self.headers_cache = self._load_headers()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _create_table(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    url TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    status TEXT NOT NULL,
                    quality REAL,
                    word_count INTEGER,
                    timestamp INTEGER NOT NULL,
                    etag TEXT,
                    last_modified TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON metadata (domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON metadata (status)")
    
    def _load_headers(self) -> dict:
        headers = {}
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT url, etag, last_modified FROM metadata WHERE etag IS NOT NULL OR last_modified IS NOT NULL")
            for url, etag, last_mod in cursor:
                headers[url] = (etag, last_mod)
        return headers

    def get_headers(self, url: str) -> tuple:
        return self.headers_cache.get(url, (None, None))

    def update_metadata(self, url: str, domain: str, status: str, 
                        quality: Optional[float] = None, 
                        word_count: Optional[int] = None,
                        etag: Optional[str] = None,
                        last_modified: Optional[str] = None):
        timestamp = int(time.time())
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO metadata 
                (url, domain, status, quality, word_count, timestamp, etag, last_modified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, domain, status, quality, word_count, timestamp, etag, last_modified))
        
        if etag or last_modified:
            self.headers_cache[url] = (etag, last_modified)