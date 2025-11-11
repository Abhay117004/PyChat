# 🧠 PyChat — AI-Powered Python Chatbot

PyChat is an **AI-driven Retrieval-Augmented Generation (RAG)** project that provides context-aware answers to Python programming questions.  
It combines intelligent web crawling, document indexing, and hybrid retrieval with an interactive web-based chat interface.  
The live chatbot is hosted here:  
👉 **[https://pychat-jryk.onrender.com/](https://pychat-jryk.onrender.com/)**

---

## 🚀 Features

### 🕷️ Web Crawler
- Asynchronous multi-domain crawler using **Crawl4AI**.  
- Content filtering based on structure, word count, and code snippets.  
- Automatic deduplication with **SimHash** and SQLite.  
- Resumable checkpoints and robots.txt compliance.  

### 🧩 Indexing & Embeddings
- Smart text chunking with **RecursiveCharacterTextSplitter**.  
- Embeddings via **Jina AI (768-dim)** for consistency across environments.  
- Local or remote indexing into **Qdrant Cloud**.  
- Supports metadata (URL, title, quality score, word count, etc.).  

### 🔍 Retrieval System
- **Hybrid retrieval** combining semantic search and BM25 keyword matching.  
- **Reranking** powered by **Jina AI** (cloud API fallback on Render).  
- **Groq LLM** used for final answer generation.  
- Query rewriting and factual verification pipeline.  
- Built-in metrics and Prometheus endpoint for performance tracking.  

### 💬 Chat Interface
- Responsive single-page web UI built with **HTML + CSS + Vanilla JS**.  
- Chat input, response streaming, and source display.  
- Local conversation history and theme toggle.  
- Works directly with the FastAPI backend hosted on **Render**.  

---

## 🏗️ Project Structure

```
PyChat/
│
├── crawler/
│   ├── config_loader.py
│   ├── content_processor.py
│   ├── domain_worker.py
│   ├── orchestrator.py
│   ├── robots_handler.py
│   ├── state_manager.py
│   ├── models.py
│   └── url_utils.py
│
├── embeddings.py               # Embedding engine (local/Jina hybrid)
├── indexer.py                  # Chunk → embed → index pipeline
├── analytics.py                # Crawl and quality reports
├── db_utils.py                 # SQLite for dedup & metadata
├── quality_analyzer.py         # Content scoring
├── migrate_to_qdrant.py        # Uploads Chroma vectors to Qdrant Cloud
│
├── rag_api/
│   ├── main.py                 # FastAPI app
│   ├── llm_client.py           # Groq API wrapper
│   ├── retriever.py            # Hybrid Qdrant + BM25 retriever
│   ├── prompt_builder.py       # Prompt assembly
│   ├── classifier.py           # Query intent classifier
│   ├── schemas.py              # Pydantic models
│   └── utils/
│       ├── logging.py
│       └── cache.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── config.py                   # Global settings & environment loader
├── run.py                      # CLI for crawl, index, serve, etc.
├── ask.py                      # Command-line query tool
├── sources.yaml                # Crawl seed configuration
├── .env.example                # Environment template
└── requirements.txt
```

---

## ⚙️ Setup

### 1. Clone
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
QDRANT_API_KEY=your_qdrant_api_key
GROQ_API_KEY=your_groq_api_key
JINA_API_KEY=your_jina_api_key
```

### 4. Prepare Directories
```bash
mkdir -p data/checkpoints data/vectordb data/logs
```

---

## 🕸️ Crawl Documentation

Edit `sources.yaml`:
```yaml
sources:
  python:
    - url: "https://docs.python.org/3/"
      max_pages: 2000
      quality_threshold: 45
```

Run:
```bash
python run.py crawl --max-pages 2000 --quality-threshold 45
```

Outputs cleaned content to `data/crawled.jsonl`.

---

## 🧠 Index and Upload

Create embeddings and index locally:
```bash
python run.py index
```

Migrate to Qdrant Cloud:
```bash
python migrate_to_qdrant.py
```

Qdrant will store **768-dim vectors** for Jina embeddings.

---

## 🧩 Start the API Server

```bash
python run.py serve
```

Then visit:
```
http://127.0.0.1:8000/docs
```

Endpoints:
- `/query` — RAG question answering  
- `/stats` — system info  
- `/prometheus` — metrics  
- `/health` — status  

---

## 💬 Web Chat UI

With the backend running, open:
```
http://127.0.0.1:8000/
```

Ask questions such as:
> *“Explain Python decorators.”*  
> *“How do list comprehensions work?”*  

PyChat retrieves relevant documentation, ranks it, and synthesizes an answer using Groq.

The same chatbot is live here:  
👉 **[https://pychat-jryk.onrender.com/](https://pychat-jryk.onrender.com/)**

---

## 🧪 CLI Tools

| Command | Description |
|----------|-------------|
| `python run.py crawl` | Crawl documentation |
| `python run.py index` | Create embeddings |
| `python run.py migrate` | Push to Qdrant |
| `python run.py serve` | Run FastAPI server |
| `python run.py query "..."` | CLI query mode |
| `python run.py analyze` | Generate analytics |
| `python run.py clean` | Clear data and checkpoints |
| `python ask.py "..."` | Direct Groq call |

---

## 🧰 Stack Overview

| Component | Technology |
|------------|-------------|
| **LLM** | Groq (Llama-3.1-8B-Instant) |
| **Embeddings** | Jina AI v2 Base (768-D) |
| **Vector DB** | Qdrant Cloud |
| **Crawler** | Crawl4AI + aiohttp + BeautifulSoup |
| **Backend** | FastAPI + Uvicorn |
| **Frontend** | HTML / CSS / JS |
| **Metrics** | Prometheus |
| **Orchestration** | Render (Web Service) |

---

## 🧭 Highlights

- Modular pipeline: crawl → process → index → query.  
- Local GPU support; automatic fallback to Jina Cloud on Render.  
- Hybrid retrieval with BM25 + semantic search.  
- Configurable models and weights via `.env`.  
- Persistent vector storage and checkpointing.  
- Built-in monitoring and logging.

---

## 🧑‍💻 Notes

- Python ≥ 3.10  
- GPU optional (auto-detects CUDA)  
- Works offline locally, cloud-optimized for Render deployment  

---

## 🛡️ License
MIT License — see `LICENSE` for details.  

---

## 🌟 Credits
- [Jina AI](https://jina.ai)  
- [Qdrant Cloud](https://qdrant.tech)  
- [Groq Cloud](https://groq.com)  
- [SentenceTransformers](https://www.sbert.net)  
- [Crawl4AI](https://github.com/nidhaloff/crawl4ai)  
