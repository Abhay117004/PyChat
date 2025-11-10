from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    mode: Optional[str] = Field("balanced")


class SourceInfo(BaseModel):
    title: str
    url: str
    snippet: str
    quality: Optional[float] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    intent: str
    complexity: str
    chunks_used: int
    mode: str
    original_query: str
    rewritten_query: Optional[str]
    success: bool
    metadata: Optional[Dict[str, Any]] = None


class StatsResponse(BaseModel):
    version: str
    total_chunks: int
    unique_pages: int
    average_quality: float
    content_types: Dict[str, int]
    embedding_model: str
    reranker_enabled: bool
    quality_weighted: bool
    llm_mode: str
    top_k: int
    prompt_system: str


class HealthResponse(BaseModel):
    status: str
    llm_healthy: bool
    database_healthy: bool
    database_chunks: int
    version: str


class QueryClassification(BaseModel):
    intent: str
    needs_context: bool
    complexity: str


class RetrievalCandidate(BaseModel):
    text: str
    metadata: Dict[str, Any]
    score: float
