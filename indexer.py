import json
from pathlib import Path
from typing import List, Dict
from loguru import logger
import chromadb
from chromadb.utils import embedding_functions

from config import settings
from text_splitter import SmartTextSplitter
from embeddings import get_embedding_engine


def load_crawled_data(filepath: Path) -> List[dict]:
    logger.info(f"Loading crawled data from {filepath}...")
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping bad line {line_number} in JSONL: {e}")

    except FileNotFoundError:
        logger.error(f"Crawled file not found: {filepath}")
        return []
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return []

    logger.info(f"Loaded {len(data)} documents.")
    return data


def chunk_documents(documents: List[dict], splitter: SmartTextSplitter) -> List[dict]:
    logger.info(f"Chunking {len(documents)} documents...")
    all_chunks = []

    for doc in documents:
        text_to_split = doc.get('text', '')
        if not isinstance(text_to_split, str):
            logger.warning(f"Skipping document with non-string text: {doc.get('url')}")
            continue

        chunks = splitter.split_text(text_to_split)
        for i, chunk_text in enumerate(chunks):
            all_chunks.append({
                'id': f"{doc.get('url', 'unknown_url')}_chunk_{i}",
                'text': chunk_text,
                'metadata': {
                    'url': doc.get('url', 'unknown'),
                    'title': doc.get('title', 'No Title'),
                    'domain': doc.get('domain', 'unknown'),
                    'word_count': doc.get('word_count', 0),
                    'quality_score': doc.get('quality_score', 0)
                }
            })

    logger.info(f"Total chunks created: {len(all_chunks)}")
    return all_chunks


def create_vector_store(collection_name: str, embedding_function):
    logger.info(f"Initializing ChromaDB vector store at: {settings.vector_database_path}")

    db_client = chromadb.PersistentClient(path=str(settings.vector_database_path))

    collection = db_client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function
    )

    logger.success(f"Vector store ready. Collection: '{collection_name}'")
    return collection


def index_chunks(collection, chunks: List[dict]):
    logger.info(f"Indexing {len(chunks)} chunks in batches...")
    batch_size = 100

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        ids = [chunk['id'] for chunk in batch]
        documents = [chunk['text'] for chunk in batch]
        metadatas = [chunk['metadata'] for chunk in batch]

        try:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Indexed batch {i//batch_size + 1}/{(len(chunks)//batch_size) + 1}")
        except Exception as e:
            logger.error(f"Error indexing batch: {e}")
            logger.warning(f"Problematic IDs: {ids[:5]}...")

    logger.success(f"Indexing complete. Total documents in collection: {collection.count()}")


def main():
    documents = load_crawled_data(settings.crawled_file)
    if not documents:
        logger.error("No documents to index. Exiting.")
        return

    splitter = SmartTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        min_chunk_size=settings.min_chunk_size
    )

    chunks = chunk_documents(documents, splitter)
    if not chunks:
        logger.error("No chunks created. Exiting.")
        return

    embed_fn = get_embedding_engine()

    collection = create_vector_store(
        collection_name=settings.collection_name,
        embedding_function=embed_fn
    )

    index_chunks(collection, chunks)


if __name__ == "__main__":
    main()