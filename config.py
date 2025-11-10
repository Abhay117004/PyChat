import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional, Dict

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    crawled_file: Path = DATA_DIR / "crawled.jsonl"
    vector_database_path: Path = DATA_DIR / "vectordb"
    sources_file: Path = BASE_DIR / "sources.yaml"
    quality_report_file: Path = DATA_DIR / "quality_report.json"
    checkpoint_dir: Path = DATA_DIR / "checkpoints"
    
    dedup_db_path: Path = DATA_DIR / "deduplication.db"
    meta_db_path: Path = DATA_DIR / "crawl_metadata.db"
    metrics_file_path: Path = DATA_DIR / "metrics.json"

    collection_name: str = "rag_collection"

    max_concurrent_crawls: int = 100
    max_global_requests_per_sec: int = 100

    base_delay_min: float = 0.5
    base_delay_max: float = 1.0
    latency_adjustment_factor: float = 0.5

    enable_sitemap_discovery: bool = True

    crawl4ai_headless: bool = True
    crawl4ai_verbose: bool = True
    crawl4ai_browser_type: str = "chromium"
    crawl4ai_page_timeout: int = 10000
    crawl4ai_word_count_threshold: int = 10
    crawl4ai_exclude_external_links: bool = True
    crawl4ai_remove_forms: bool = True

    min_words_for_trafilatura: int = 100
    max_url_depth: int = 4
    quality_threshold: int = 45
    min_word_count: int = 50
    min_char_count: int = 150

    max_boilerplate_ratio: float = 0.25
    duplicate_title_threshold: int = 5
    simhash_hamming_distance: int = 3
    enable_content_deduplication: bool = True

    chunk_size: int = 1500
    chunk_overlap: int = 500
    enable_smart_chunking: bool = True
    min_chunk_size: int = 100

    embedding_provider: str = "huggingface"
    embedding_model_name: str = "BAAI/bge-base-en-v1.5"
    embedding_device: str = "cuda"
    embedding_batch_size: int = 64

    top_k_results: int = 7
    retrieval_candidate_multiplier: int = 3
    enable_reranking: bool = True
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    enable_quality_weighted_search: bool = True
    show_quality_scores_in_response: bool = True
    enable_query_rewriting: bool = True
    enable_answer_verification: bool = True
    content_type_weights: Dict[str, float] = {
        "tutorial": 1.4,
        "example": 1.3,
        "reference": 1.1,
        "guide": 1.2,
        "howto": 1.3,
        "general": 1.0
    }

    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"
    default_temperature: float = 0.5
    temperature_precise: float = 0.2
    temperature_balanced: float = 0.5
    temperature_creative: float = 0.8
    max_output_tokens: int = 1500

    checkpoint_interval: int = 60
    auto_resume: bool = True

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()