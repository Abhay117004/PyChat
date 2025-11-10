# 🧠 PyChat — AI-Powered Python Programming Assistant

PyChat is a **production-grade Retrieval-Augmented Generation (RAG)** system designed to deliver expert-level answers for **Python programming queries**.  
It intelligently crawls documentation, indexes high-quality content, and serves responses powered by **Groq LLM** and **Qdrant Cloud** for vector retrieval.

---

## 🚀 Key Features

### 🕷️ Smart Web Crawler
- **Asynchronous multi-domain crawling** with Crawl4AI.
- **Quality-based filtering** using text structure, code presence, and uniqueness.
- **Language detection**, deduplication (SimHash + SQLite), and adaptive throttling.
- Resumable checkpoints and robot.txt compliance.

### 🧩 Intelligent Indexing
- Automatic **text chunking** with LangChain’s `RecursiveCharacterTextSplitter`.
- High-performance **embeddings** via `BAAI/bge-base-en-v1.5`.
- Vector storage using **ChromaDB** or **Qdrant Cloud**.
- Metadata tracking for each page (domain, quality, word count, etc.).

### 🔍 RAG Query System
- Hybrid retrieval (**semantic + BM25 keyword**).
- Optional **reranking** with `BAAI/bge-reranker-v2-m3`.
- Multi-stage LLM pipeline:
  - **Query rewriting** (Groq).
  - **Context synthesis** via prompt building.
  - **Answer verification** for factual correctness.
- Built-in **performance metrics**, Prometheus monitoring, and health checks.

### 💬 Web UI (Frontend)
- Fast, accessible **single-page interface** built with vanilla JS.
- Real-time chat, source panel, theme toggle, and local conversation history.
- System status (connected / offline) and live metrics display.
- Works directly with FastAPI backend — no external dependencies.

---

## 🏗️ Project Structure

```
PyChat/
│
├── crawler/                    # Asynchronous crawler system
│   ├── config_loader.py        # Loads sources.yaml
│   ├── content_processor.py    # Cleans & validates content
│   ├── domain_worker.py        # Worker for domain-level tasks
│   ├── orchestrator.py         # Crawler manager & event loop
│   ├── robots_handler.py       # Handles robots.txt & sitemaps
│   ├── state_manager.py        # Checkpoints & crawl state
│   ├── models.py               # Core data models
│   └── url_utils.py            # Normalization & filtering
│
├── embeddings.py               # HuggingFace SentenceTransformer wrapper
├── indexer.py                  # Chunking, embedding & indexing into Chroma
├── analytics.py                # Post-crawl analytics & quality reports
├── db_utils.py                 # SQLite databases for dedup & metadata
├── quality_analyzer.py         # Content scoring logic
├── migrate_to_qdrant.py        # Migrates embeddings from Chroma → Qdrant
│
├── rag_api/
│   ├── main.py                 # FastAPI app entry point
│   ├── llm_client.py           # Groq client wrapper with caching
│   ├── retriever.py            # Qdrant + BM25 hybrid retriever
│   ├── prompt_builder.py       # Context + query prompt templates
│   ├── classifier.py           # Query intent & complexity detection
│   ├── schemas.py              # Pydantic models for API I/O
│   └── utils/
│       ├── logging.py          # Rich console & performance tracking
│       └── cache.py            # Embedding & rewrite caches
│
├── frontend/                   # Web UI
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── config.py                   # Global settings & environment loader
├── run.py                      # CLI for crawl, index, serve, analyze
├── ask.py                      # Direct Groq CLI query tool
├── sources.yaml                # Crawl seed configuration
├── .env.example                # Environment template
└── requirements.txt
```

---

## ⚙️ Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/pychat.git
cd pychat
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Copy `.env.example` to `.env` and fill in:
```env
QDRANT_URL=https://your-qdrant-instance.qdrant.tech
QDRANT_API_KEY=your_api_key_here
GROQ_API_KEY=your_groq_key_here
```

### 4. Prepare Data Directories
```bash
mkdir -p data/checkpoints data/vectordb data/logs
```

---

## 🕸️ Crawling Knowledge Sources

Edit `sources.yaml` to define your seed domains, e.g.:
```yaml
sources:
  python:
    - url: "https://docs.python.org/3/"
      max_pages: 2000
      quality_threshold: 45
```

Run the crawler:
```bash
python run.py crawl --quality-threshold 50 --max-pages 5000
```

This will:
- Crawl all Python-related docs.
- Filter and clean content.
- Save results to `data/crawled.jsonl`.

---

## 🧠 Indexing the Data

Convert crawled data into embeddings and store in Chroma:
```bash
python run.py index
```

Then migrate to Qdrant for production:
```bash
python migrate_to_qdrant.py
```

---

## 🧩 Starting the API Server

```bash
python run.py serve
```

Access the API at:
```
http://127.0.0.1:8000
```

- Swagger Docs: `/docs`
- Metrics: `/metrics`
- Prometheus endpoint: `/prometheus`
- Health check: `/health`

---

## 💬 Using the Web UI

Once the API is running, open:
```
http://127.0.0.1:8000/
```

You’ll see the PyChat frontend — ask any Python question:
> _“How to read a CSV file with pandas?”_  
> _“Explain decorators in Python.”_

The system retrieves, synthesizes, and verifies an answer with linked sources.

---

## 📈 Analytics & Reports

After crawling:
```bash
python run.py analyze
```

Generates `data/quality_report.json` and prints insights:
- Content quality distribution
- Domain breakdown
- Boilerplate ratios
- Duplicate detection
- Top-quality pages

---

## 🧪 CLI Utilities

| Command | Description |
|----------|--------------|
| `python run.py crawl` | Start web crawler |
| `python run.py index` | Index crawled data |
| `python run.py serve` | Run FastAPI backend |
| `python run.py query "your question"` | Query via CLI |
| `python run.py analyze` | Generate analytics |
| `python run.py clean` | Reset all data (clears DB, checkpoints, etc.) |

Direct Groq test:
```bash
python ask.py "Explain Python context managers"
```

---

## 🧰 Tech Stack

| Layer | Technology |
|--------|-------------|
| **LLM** | Groq (Llama-3.1-8B-Instant) |
| **Vector DB** | Qdrant Cloud |
| **Crawler** | Crawl4AI + aiohttp + BeautifulSoup |
| **Embeddings** | SentenceTransformers (`BAAI/bge-base-en-v1.5`) |
| **Backend** | FastAPI |
| **Frontend** | HTML + CSS + Vanilla JS |
| **Storage** | SQLite (dedup, metadata) |
| **Monitoring** | Prometheus metrics |

---

## 🧭 Design Highlights

- Fully **modular pipeline**: crawl → index → query.
- Smart queueing with **priority-based URL selection**.
- Quality-driven acceptance with structured scoring.
- Cache layers for **embeddings**, **rewrites**, and **retrievals**.
- Fault-tolerant orchestration with async tasks.
- Clean API architecture with validation & schemas.

---

## 🧑‍💻 Development Notes

- Python ≥ 3.10 required.
- GPU optional (auto-detects for embeddings).
- Frontend served automatically from `/frontend`.
- Crawls resume from checkpoints unless `--clean` is run.

---

## 🛡️ License

This project is licensed under the **MIT License** — see `LICENSE` for details.

---

## 🌟 Acknowledgements

- [Crawl4AI](https://github.com/nidhaloff/crawl4ai)
- [Qdrant](https://qdrant.tech)
- [SentenceTransformers](https://www.sbert.net)
- [LangChain](https://www.langchain.com)
- [Groq Cloud](https://groq.com)
