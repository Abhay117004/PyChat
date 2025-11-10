import click
import httpx
import json
import shutil
import sys
import os

from loguru import logger
from config import settings, BASE_DIR

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/run.log", rotation="10 MB", level="DEBUG")

DATA_DIR = BASE_DIR / "data"


@click.group()
def cli():
    pass


@cli.command()
@click.option('--quality-threshold', default=None, type=int, help='Min quality score (overrides config)')
@click.option('--max-pages', default=None, type=int, help='Max pages to crawl (overrides sources.yaml total)')
@logger.catch
def crawl(quality_threshold, max_pages):
    from crawler import main as crawl_main
    crawl_main(
        cli_max_pages=max_pages,
        cli_quality_threshold=quality_threshold
    )


@cli.command()
@logger.catch
def index():
    from indexer import main as index_main
    logger.info("\nStarting Smart Indexer\n")
    index_main()


@cli.command()
@click.option('--host', default=None, help='API host (overrides config)')
@click.option('--port', default=None, type=int, help='API port (overrides config)')
@logger.catch
def serve(host, port):
    import uvicorn
    api_host = host or settings.api_host
    api_port = port or settings.api_port

    logger.info(f"\n" + "="*60 + f"\nRAG API SERVER" + "\n" + "="*60)
    logger.info(f"Address: http://{api_host}:{api_port}")
    logger.info(f"API docs: http://{api_host}:{api_port}/docs" + "\n" + "="*60 + "\n")

    uvicorn.run("rag_api.main:app", host=api_host, port=api_port, reload=False, log_level="info")


@cli.command()
@click.argument('query')
@click.option('--mode', default='balanced', type=click.Choice(['precise', 'balanced', 'creative']))
@click.option('--show-sources/--no-sources', default=True, help='Show source documents')
@logger.catch
def query(query, mode, show_sources):
    logger.info(f"\nQuerying with mode: {mode}\nQuestion: {query}\n")
    try:
        response = httpx.post(
            f"http://{settings.api_host}:{settings.api_port}/query",
            json={"query": query, "mode": mode},
            timeout=120
        )
        if response.status_code != 200:
            logger.error(f"Error: API returned status {response.status_code}\nResponse: {response.text}\n")
            return

        data = response.json()
        print(f"ANSWER (Intent: {data.get('intent', 'unknown')})")
        print("="*60 + f"\n{data['answer']}\n" + "="*60 + "\n")

        if show_sources and data.get('sources'):
            print(f"SOURCES ({len(data['sources'])} documents)" + "\n" + "-"*60)
            for i, src in enumerate(data['sources'], 1):
                print(f"\n{i}. {src['title']}\n   URL: {src['url']}")
                if src.get('quality'): print(f"   Quality: {src['quality']}", end="")
                print(f"\n   {src['snippet']}")
        print()

    except httpx.ConnectError:
        logger.error(f"Connection Error: Could not connect to API at http://{settings.api_host}:{settings.api_port}")
        logger.error("   Make sure the server is running: python run.py serve\n")
    except Exception as e:
        logger.error(f"Error: {str(e)}\n")


@cli.command()
@logger.catch
def analyze():
    from analytics import main as analyze_main
    analyze_main()


@cli.command()
@click.confirmation_option(prompt='This will EMPTY the entire /data directory (jsonl, db, vectordb, checkpoints). Continue?')
@logger.catch
def clean():
    deleted_items = []

    if not DATA_DIR.exists():
        logger.info(f"Data directory '{DATA_DIR}' not found, nothing to clean.\n")
        return

    logger.warning(f"Cleaning directory: {DATA_DIR}")

    for item in DATA_DIR.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
                deleted_items.append(f"{item.name}/ (dir)")
            else:
                item.unlink()
                deleted_items.append(item.name)
        except Exception as e:
            logger.error(f"Failed to delete {item.name}: {e}")

    if deleted_items:
        logger.info(f"Emptied data directory. Deleted: {', '.join(deleted_items)}\n")
    else:
        logger.info(f"Data directory was already empty.\n")


if __name__ == "__main__":
    cli()