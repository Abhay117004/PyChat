from chromadb import PersistentClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, PointStruct
from tenacity import retry, stop_after_attempt, wait_fixed
import time
import math
import os

from config import settings

CHROMA_PATH = str(getattr(settings, "vector_database_path", "data/vectordb"))
CHROMA_COLLECTION = getattr(settings, "collection_name", "rag_collection")

QDRANT_URL = os.getenv("QDRANT_URL") or getattr(settings, "QDRANT_URL", None)
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or getattr(settings, "QDRANT_API_KEY", None)
QDRANT_COLLECTION = getattr(settings, "QDRANT_COLLECTION", "pychat_knowledge")

if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in the environment or in settings")

EMBEDDING_SIZE = getattr(settings, "embedding_size", 384)
BATCH_SIZE = 1024

print("Connecting to local Chroma DB...")
chroma = PersistentClient(path=CHROMA_PATH)
collection = chroma.get_collection(CHROMA_COLLECTION)

print("Connecting to Qdrant Cloud...")
qdrant = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    prefer_grpc=False,
    timeout=60,
    check_compatibility=False
)

print(f"Recreating Qdrant collection '{QDRANT_COLLECTION}' with {EMBEDDING_SIZE}-dim vectors...")
if qdrant.collection_exists(QDRANT_COLLECTION):
    qdrant.delete_collection(QDRANT_COLLECTION)

qdrant.create_collection(
    collection_name=QDRANT_COLLECTION,
    vectors_config=VectorParams(size=EMBEDDING_SIZE, distance="Cosine"),
)
print("Qdrant collection ready.\n")

print("Fetching data from Chroma (this may take a bit)...")
data = collection.get(include=["embeddings", "documents", "metadatas"])
total = len(data["ids"])
print(f"Found {total} items to migrate.\n")

@retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
def safe_upsert(points):
    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)

uploaded = 0
start_time = time.time()

for start in range(0, total, BATCH_SIZE):
    end = min(start + BATCH_SIZE, total)
    batch_embeddings = data["embeddings"][start:end]
    batch_docs = data["documents"][start:end]
    batch_meta = data["metadatas"][start:end]

    points = [
        PointStruct(
            id=i + start,
            vector=emb,
            payload={"text": txt, **(meta or {})}
        )
        for i, (emb, txt, meta)
        in enumerate(zip(batch_embeddings, batch_docs, batch_meta))
    ]

    safe_upsert(points)
    uploaded += len(points)
    pct = (uploaded / total) * 100
    print(f"Uploaded {uploaded}/{total} ({pct:.2f}%)")
    time.sleep(0.05)

elapsed = math.ceil(time.time() - start_time)
print(f"\nMigration complete! Uploaded {uploaded} items in {elapsed} seconds.")
