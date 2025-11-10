from rag_api.main import app

if __name__ == "__main__":
    import uvicorn
    from config import settings

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )
