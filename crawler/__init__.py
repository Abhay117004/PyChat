import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from config import settings
from crawler.orchestrator import CrawlOrchestrator
from crawler.config_loader import ConfigLoader
from crawler.state_manager import StateManager


class CrawlerApplication:
    def __init__(
        self,
        max_pages: Optional[int] = None,
        quality_threshold: Optional[int] = None
    ):
        self.max_pages = max_pages
        self.quality_threshold = quality_threshold
        self.config_loader = ConfigLoader(settings.sources_file)
        self.state_manager = StateManager(
            checkpoint_file=settings.checkpoint_dir / "crawl_state.json",
            auto_resume=settings.auto_resume
        )
        
    async def run(self):
        logger.info("Initializing crawler application")
        
        sources = self.config_loader.load_sources(
            cli_quality_threshold=self.quality_threshold
        )
        
        if not sources:
            logger.error("No valid sources configured")
            return
            
        state = None
        if self.state_manager.checkpoint_exists():
            state = self.state_manager.load_checkpoint()
            
        orchestrator = CrawlOrchestrator(
            sources=sources,
            max_pages=self.max_pages,
            initial_state=state
        )
        
        try:
            await orchestrator.start()
        except KeyboardInterrupt:
            logger.info("Crawl interrupted by user")
        except Exception as e:
            logger.exception(f"Fatal crawler error: {e}")
        finally:
            final_state = orchestrator.get_state()
            self.state_manager.save_checkpoint(final_state)
            orchestrator.print_summary()


def main(cli_max_pages=None, cli_quality_threshold=None):
    app = CrawlerApplication(
        max_pages=cli_max_pages,
        quality_threshold=cli_quality_threshold
    )
    asyncio.run(app.run())


__all__ = [
    'CrawlerApplication',
    'main'
]