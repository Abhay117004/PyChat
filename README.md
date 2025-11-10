# PyChat RAG System

A Retrieval-Augmented Generation (RAG) system for Python programming assistance, built with FastAPI, ChromaDB, and Groq LLM.

## Features

- **Intelligent Query Classification**: Automatically detects user intent (code, examples, debugging, etc.)
- **Advanced Retrieval**: Hybrid search with BM25 + semantic embeddings + reranking
- **Quality-Aware Indexing**: Content quality scoring and deduplication
- **Web Crawling**: Automated crawling of Python documentation and tutorials
- **RESTful API**: FastAPI-based API with automatic documentation
- **Monitoring**: Prometheus metrics and health checks
- **CLI Tools**: Command-line interface for all operations

## Quick Start

### Prerequisites

- Python 3.8+
- pip
- Git


# PyChat: AI-Powered Python Knowledge Assistant

## Overview
PyChat is a Retrieval-Augmented Generation (RAG) system designed to answer Python, data science, machine learning, and web development questions using advanced document retrieval and large language models. It features a modular backend, a modern frontend, and robust crawling, indexing, and serving capabilities.

## File Structure
```
PyChat/
├── analytics.py           # Data analytics utilities
├── api.py                 # FastAPI server entrypoint
├── ask.py                 # Query routing and orchestration
├── config.py              # Configuration management
├── crawler.py             # Main crawler orchestrator
├── db_utils.py            # Database utilities
├── embeddings.py          # Embedding generation and management
├── indexer.py             # Document indexing and vector storage
├── quality_analyzer.py    # Content quality analysis
├── run.py                 # CLI entrypoint for crawling, serving, and more
├── sources.yaml           # Crawl source configuration
├── rag_api/               # RAG API logic and utilities
│   ├── main.py            # FastAPI app and endpoints
│   ├── retriever.py       # Hybrid retriever (semantic + keyword)
│   ├── prompt_builder.py  # Prompt construction for LLMs
│   ├── llm_client.py      # LLM API integration (Groq, etc.)
│   ├── classifier.py      # Intent classification
│   ├── schemas.py         # API schemas and models
│   └── utils/             # Logging, caching, helpers
├── crawler/               # Crawler modules
│   ├── config_loader.py   # Source config loader
│   ├── content_extractors.py # HTML/Markdown extraction
│   ├── content_processor.py  # Content cleaning and normalization
│   ├── domain_worker.py   # Per-domain crawl logic
│   ├── fetchers.py        # Web fetcher and browser automation
│   ├── monitoring.py      # Crawl monitoring and metrics
│   ├── orchestrator.py    # Crawl orchestration and scheduling
│   ├── robots_handler.py  # Robots.txt and crawl rules
│   ├── state_manager.py   # Checkpointing and resume logic
│   ├── url_utils.py       # URL normalization and filtering
│   └── models.py          # Data models for crawl results
├── frontend/              # Web frontend (HTML, JS, CSS)
│   ├── index.html         # Main UI
│   ├── script.js          # UI logic and API calls
│   └── style.css          # Modern glassmorphism styling
# PyChat — RAG system for Python assistance

PyChat is a Retrieval-Augmented Generation (RAG) system that helps answer Python, data science, and web-development questions by combining web crawling, semantic indexing, and LLM-backed generation.

Key components:
- Crawler: collects and normalizes HTML/Markdown content from configured sources
- Indexer: builds embeddings and stores vectors for fast retrieval
- API server: a FastAPI app that performs hybrid retrieval and LLM prompting
- Frontend: a small web UI for chat and diagnostics

## Features

- Hybrid retrieval (BM25 + semantic embeddings + reranking)
- Quality-aware indexing and deduplication
- Pluggable embedding and LLM providers
- Checkpointed crawling with resume capability
- Simple CLI for crawl/index/serve workflows

## Minimal file overview

`PyChat/` (top-level project)

- `api.py` — FastAPI server entrypoint
- `run.py` — CLI runner (crawl / index / serve / analyze)
- `crawler/` — crawler modules and helpers
- `rag_api/` — RAG API code (retriever, prompt builder, llm client)
- `data/` — local storage for crawled data, vectordb, checkpoints
- `frontend/` — `index.html`, `script.js`, `style.css`
- `requirements.txt` — Python dependencies
- `.gitignore`, `README.md`, `LICENSE`

## Quick start

1. Create and activate a virtual environment (outside the repo directory if possible):

```bat
python -m venv C:\path\to\venv
C:\path\to\venv\Scripts\activate.bat
```

2. Install dependencies:

```bat
pip install -r requirements.txt
```

3. Create a `.env` (not checked into git) with provider API keys, or export env vars.

4. Run the CLI:

```bat
python run.py crawl   :: to crawl sources
python run.py index   :: to build/update the vector index
python run.py serve   :: to start the API server (or use uvicorn)
```

5. Open `frontend/index.html` to view the simple local UI (or hit the FastAPI endpoints).

## Docker (example)

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "run.py", "serve"]
```

## Notes and safety

- Never commit `.env` or API keys to the repository. Use `.env.example` for names only.
- Keep the virtualenv out of the repository. Add it to `.gitignore` (e.g., `PyChat/`).
- If an API key was pushed previously, rotate/revoke it immediately at the provider (deleting from git history is not enough).


