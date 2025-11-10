from dataclasses import dataclass
from typing import Optional, List
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from loguru import logger
from config import settings
_fetcher_instance = None


@dataclass
class FetchResult:
    success: bool
    html: Optional[str] = None
    markdown: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None
    links: List[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None


class Crawl4AIFetcher:
    
    def __init__(self):
        self.crawler = None
        self._browser_config = None
        self._run_config = None
        self._initialized = False
        
    async def initialize(self):
        if self._initialized:
            return
            
        logger.info("Initializing Crawl4AI crawler...")
        
        self._browser_config = BrowserConfig(
            headless=settings.crawl4ai_headless,
            verbose=settings.crawl4ai_verbose,
            browser_type=settings.crawl4ai_browser_type,
        )
        
        self._run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=settings.crawl4ai_page_timeout,
            word_count_threshold=settings.crawl4ai_word_count_threshold,
            exclude_external_links=settings.crawl4ai_exclude_external_links,
            remove_forms=settings.crawl4ai_remove_forms,
            wait_for="body",
        )
        
        self.crawler = AsyncWebCrawler(config=self._browser_config)
        await self.crawler.__aenter__()
        
        self._initialized = True
        logger.success("Crawl4AI crawler initialized successfully")
        
    async def cleanup(self):
        if self.crawler and self._initialized:
            await self.crawler.__aexit__(None, None, None)
            self._initialized = False
            logger.info("Crawl4AI crawler cleaned up")
    
    async def fetch(self, url: str) -> FetchResult:
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.debug(f"[Crawl4AI] Fetching: {url}")
            
            result = await self.crawler.arun(
                url=url,
                config=self._run_config
            )
            
            if not result.success:
                return FetchResult(
                    success=False,
                    error=result.error_message or "Crawl failed"
                )
            
            links = []
            if result.links:
                internal_links = result.links.get('internal', [])
                links = [link.get('href') for link in internal_links if link.get('href')]
            
            metadata = {
                'word_count': len(result.markdown.split()) if result.markdown else 0,
                'code_blocks': result.markdown.count('```') // 2 if result.markdown else 0,
                'has_tables': '|' in result.markdown if result.markdown else False,
            }
            
            return FetchResult(
                success=True,
                html=result.html,
                markdown=result.markdown,
                text=result.cleaned_html,
                title=result.metadata.get('title', 'No Title') if result.metadata else 'No Title',
                links=links,
                status_code=200,
                metadata=metadata
            )
            
        except asyncio.TimeoutError:
            return FetchResult(
                success=False,
                error="Timeout"
            )
        except Exception as e:
            logger.error(f"Crawl4AI fetch error for {url}: {e}")
            return FetchResult(
                success=False,
                error=str(e)
            )


async def get_fetcher() -> Crawl4AIFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = Crawl4AIFetcher()
        await _fetcher_instance.initialize()
    return _fetcher_instance


async def cleanup_fetcher():
    global _fetcher_instance
    if _fetcher_instance:
        await _fetcher_instance.cleanup()
        _fetcher_instance = None