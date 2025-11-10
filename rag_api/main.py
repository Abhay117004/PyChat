import time
import mimetypes
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from .schemas import (
    QueryRequest, QueryResponse, StatsResponse,
    HealthResponse, SourceInfo
)
from .classifier import QueryClassifier
from .retriever import Retriever
from .prompt_builder import PromptBuilder
from .llm_client import LLMClient
from .utils.logging import (
    log_info, log_success, log_error, log_step, log_warning,
    setup_logging, performance_monitor
)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/html", ".html")

setup_logging(level="INFO")

app = FastAPI(
    title="RAG System",
    version="1.0.0",
    description="Production-ready retrieval-augmented generation API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_error(f"Unhandled error on {request.url.path}: {exc}")
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "path": request.url.path}
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": str(exc), "path": request.url.path}
    )

log_info("Initializing components...")

retriever = Retriever()
llm_client = LLMClient()
classifier = QueryClassifier()

log_success("System ready")

try:
    Instrumentator().instrument(app).expose(app, endpoint="/prometheus")
    log_info("Prometheus metrics enabled at /prometheus")
except ImportError:
    log_warning(
        "prometheus_fastapi_instrumentator not installed, skipping metrics")


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if path.endswith(('.js', '.css')):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    start_time = time.time()

    try:
        original_query = request.query
        log_step("Query", f"'{original_query}'")

        classification = classifier.classify(original_query)
        intent = classification.intent
        complexity = classification.complexity

        log_step("Classify", f"Intent: {intent}, Complexity: {complexity}")

        if not classification.needs_context:
            try:
                prompt = PromptBuilder.build(
                    original_query, [], intent, complexity)
                temperature = _get_temperature(
                    request.mode, request.temperature)
                
                messages = [{"role": "user", "content": prompt}]
                answer = await llm_client.call(messages, temperature)

            except HTTPException as e:
                log_error(f"LLM unavailable for greeting: {e.detail}")
                answer = "Hello! I'm your Python programming assistant. I can help you with Python libraries, frameworks, coding questions, and examples. What would you like to know?"

            latency_ms = (time.time() - start_time) * 1000
            performance_monitor.record("query_greeting", latency_ms)

            return QueryResponse(
                answer=answer,
                sources=[],
                intent=intent,
                complexity=complexity,
                chunks_used=0,
                mode=request.mode,
                original_query=original_query,
                rewritten_query=None,
                success=True,
                metadata={"latency_ms": round(latency_ms, 2)}
            )

        if settings.enable_query_rewriting:
            search_query = await llm_client.rewrite_query(original_query)
        else:
            search_query = original_query

        top_docs = await retriever.get_top_documents(
            query=search_query,
            intent=intent,
            k=settings.top_k_results
        )

        if not top_docs:
            return QueryResponse(
                answer="I couldn't find relevant information in my knowledge base to answer your question.",
                sources=[],
                intent=intent,
                complexity=complexity,
                chunks_used=0,
                mode=request.mode,
                original_query=original_query,
                rewritten_query=search_query,
                success=True,
                metadata={"latency_ms": round(
                    (time.time() - start_time) * 1000, 2)}
            )

        prompt = PromptBuilder.build(
            search_query, top_docs, intent, complexity)

        temperature = _get_temperature(request.mode, request.temperature)
        
        messages = [{"role": "user", "content": prompt}]
        answer = await llm_client.call(messages, temperature)

        if settings.enable_answer_verification and complexity == "complex" and len(top_docs) > 0:
            context_text = "\n".join([doc['text'][:300]
                                     for doc in top_docs[:2]])
            answer = await llm_client.verify_answer(search_query, answer, context_text)

        sources = _format_sources(top_docs)

        latency_ms = (time.time() - start_time) * 1000
        performance_monitor.record("query_full", latency_ms)

        log_success(f"Query completed in {latency_ms:.0f}ms")

        return QueryResponse(
            answer=answer,
            sources=sources,
            intent=intent,
            complexity=complexity,
            chunks_used=len(top_docs),
            mode=request.mode,
            original_query=original_query,
            rewritten_query=search_query if search_query != original_query else None,
            success=True,
            metadata={
                "latency_ms": round(latency_ms, 2),
                "reranked": retriever.reranker is not None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Query processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse)
def stats_endpoint() -> StatsResponse:
    stats = retriever.get_stats()
    return StatsResponse(
        version="1.0.0",
        total_chunks=stats["total_chunks"],
        unique_pages=stats["unique_pages"],
        average_quality=stats["average_quality"],
        content_types=stats["content_types"],
        embedding_model=settings.embedding_model_name,
        reranker_enabled=settings.enable_reranking,
        quality_weighted=settings.enable_quality_weighted_search,
        llm_mode=settings.groq_model, 
        top_k=settings.top_k_results,
        prompt_system="Production"
    )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    llm_healthy = await llm_client.health_check()
    db_stats = retriever.get_stats()
    db_healthy = db_stats["total_chunks"] > 0
    status = "healthy" if (llm_healthy and db_healthy) else "degraded"

    return HealthResponse(
        status=status,
        llm_healthy=llm_healthy,
        database_healthy=db_healthy,
        database_chunks=db_stats["total_chunks"],
        version="1.0.0"
    )


@app.get("/metrics")
def metrics_endpoint() -> Dict[str, Any]:
    from .utils.cache import embedding_cache, rewrite_cache

    return {
        "performance": {
            "query_greeting": performance_monitor.get_stats("query_greeting"),
            "query_full": performance_monitor.get_stats("query_full")
        },
        "cache": {
            "embeddings": embedding_cache.stats(),
            "rewrites": {"size": len(rewrite_cache.cache)},
            "retrievals": {"size": len(retriever.retrieval_cache)}
        },
        "system": retriever.get_stats()
    }


def _get_temperature(mode: str, default: float = None) -> float:
    if default is not None:
        return default

    modes = {
        "precise": settings.temperature_precise,
        "balanced": settings.temperature_balanced,
        "creative": settings.temperature_creative
    }
    return modes.get(mode, settings.default_temperature)


def _format_sources(docs: list) -> list[SourceInfo]:
    import json

    sources = []
    for doc in docs:
        try:
            quality = doc['metadata'].get('quality', '{}')
            if isinstance(quality, str):
                quality = json.loads(quality)
            q_score = quality.get('score', 0)
        except Exception:
            q_score = 0

        snippet = doc['text'][:200] + \
            "..." if len(doc['text']) > 200 else doc['text']

        sources.append(SourceInfo(
            title=doc['metadata'].get('title', 'Untitled'),
            url=doc['metadata'].get('url', ''),
            snippet=snippet,
            quality=round(
                q_score, 1) if settings.show_quality_scores_in_response else None
        ))

    return sources


frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", NoCacheStaticFiles(directory=str(frontend_path),
              html=True), name="frontend")
    log_info(f"Frontend mounted from {frontend_path}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )