import asyncio
import time
import random
from typing import Optional
from loguru import logger

from config import settings
from crawler.models import CrawlSource, CrawlState, DomainResult, PageResult
from crawler.fetchers import Crawl4AIFetcher
from crawler.content_processor import ContentProcessor
from crawler.robots_handler import RobotsHandler
from db_utils import DedupDatabase, MetadataDatabase


class DomainWorker:

    def __init__(
        self,
        domain: str,
        source_config: CrawlSource,
        state: CrawlState,
        fetcher: Crawl4AIFetcher,
        robots_handler: RobotsHandler,
        stop_event: asyncio.Event
    ):
        self.domain = domain
        self.config = source_config
        self.state = state
        self.fetcher = fetcher
        self.robots_handler = robots_handler
        self.stop_event = stop_event

        self.dedup_db = DedupDatabase(settings.dedup_db_path)
        self.meta_db = MetadataDatabase(settings.meta_db_path)

        self.content_processor = ContentProcessor(
            domain=domain,
            seed_prefix=source_config.seed_prefix,
            quality_threshold=source_config.quality_threshold,
            dedup_db=self.dedup_db
        )

        self.consecutive_failures = 0
        self.max_failures = 100

        self.page_buffer = []
        self.buffer_limit = 50

    async def process_domain(self) -> DomainResult:
        logger.info(f"Starting worker for {self.domain}")

        try:
            pages_crawled = 0

            while not self.stop_event.is_set():
                if not self._can_continue():
                    break

                try:
                    url = self.state.pop_url(self.domain)
                except IndexError:
                    return DomainResult(
                        domain=self.domain,
                        pages_crawled=pages_crawled,
                        page_limit=self.config.max_pages,
                        is_complete=False,
                        is_exhausted=True
                    )

                if self.state.is_visited(url):
                    continue

                if not self._should_crawl_url(url):
                    self.state.mark_visited(url)
                    continue

                self.state.mark_visited(url)
                result = await self._process_url(url)

                if result.success:
                    self.consecutive_failures = 0
                    pages_crawled += 1
                    self.state.increment_domain_count(self.domain)
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_failures:
                        logger.warning(f"Domain {self.domain} exceeded failure limit")
                        break

                await self._apply_delay()

            await self._flush_buffer()

            is_complete = self.state.get_domain_count(self.domain) >= self.config.max_pages

            return DomainResult(
                domain=self.domain,
                pages_crawled=pages_crawled,
                page_limit=self.config.max_pages,
                is_complete=is_complete,
                is_exhausted=not is_complete
            )

        except Exception as e:
            logger.exception(f"Fatal error in domain worker for {self.domain}: {e}")
            await self._flush_buffer()
            return DomainResult(
                domain=self.domain,
                pages_crawled=0,
                page_limit=self.config.max_pages,
                is_complete=False,
                is_exhausted=False
            )

    async def _process_url(self, url: str) -> PageResult:
        start_time = time.time()

        try:
            logger.debug(f"[Crawl4AI] Processing: {url}")
            self.state.increment_stat('fetch_crawl4ai')

            fetch_result = await self.fetcher.fetch(url)

            latency = time.time() - start_time
            self.state.update_latency(self.domain, latency)

            if not fetch_result.success:
                self.state.increment_stat('pages_failed')
                return PageResult(url=url, success=False, error=fetch_result.error, new_links=[])

            process_result = await self.content_processor.process(
                url=url,
                markdown=fetch_result.markdown,
                text_content=fetch_result.text,
                title=fetch_result.title,
                links=fetch_result.links,
                metadata=fetch_result.metadata
            )

            if process_result.accepted:
                self.state.increment_stat('pages_accepted')
                await self._save_page(process_result.page_data)
                logger.success(
                    f"[{self.state.get_domain_count(self.domain)}/{self.config.max_pages}] "
                    f"{self.domain} | Q:{process_result.quality_score:.0f} | {url[:80]}"
                )
                return PageResult(url=url, success=True, new_links=process_result.links)
            else:
                if process_result.rejection_reason == 'duplicate':
                    self.state.increment_stat('pages_rejected_duplicate')
                elif process_result.rejection_reason == 'quality':
                    self.state.increment_stat('pages_rejected_quality')
                elif process_result.rejection_reason == 'language':
                    self.state.increment_stat('pages_rejected_lang')
                elif process_result.rejection_reason == 'empty':
                    self.state.increment_stat('pages_rejected_empty')
                elif process_result.rejection_reason == 'too_short':
                    self.state.increment_stat('pages_rejected_short')

                logger.debug(f"[REJECTED: {process_result.rejection_reason}] {url}")
                return PageResult(url=url, success=False, new_links=process_result.links)

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            self.state.increment_stat('pages_failed')
            return PageResult(url=url, success=False, error=str(e), new_links=[])

    def _can_continue(self) -> bool:
        current_count = self.state.get_domain_count(self.domain)
        return current_count < self.config.max_pages

    def _should_crawl_url(self, url: str) -> bool:
        return self.robots_handler.can_fetch(self.domain, url)

    async def _apply_delay(self):
        base_delay = random.uniform(settings.base_delay_min, settings.base_delay_max)
        latency_penalty = self.state.get_avg_latency(self.domain) * settings.latency_adjustment_factor
        total_delay = base_delay + latency_penalty
        await asyncio.sleep(total_delay)

    async def _save_page(self, page_data: dict):
        try:
            self.page_buffer.append(page_data)
            self.meta_db.update_metadata(
                url=page_data["url"],
                domain=page_data["domain"],
                status="crawled",
                quality=page_data["quality_score"],
                word_count=page_data["word_count"],
            )
            if len(self.page_buffer) >= self.buffer_limit:
                await self._flush_buffer()
        except Exception as e:
            logger.error(f"Error buffering page {page_data.get('url')}: {e}")

    async def _flush_buffer(self):
        if not self.page_buffer:
            return
        try:
            import json
            with open(settings.crawled_file, "a", encoding="utf-8") as f:
                f.writelines(json.dumps(p) + "\n" for p in self.page_buffer)
            logger.debug(f"Flushed {len(self.page_buffer)} pages to disk.")
            self.page_buffer.clear()
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")
