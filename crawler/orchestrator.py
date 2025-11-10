import asyncio
import time
from typing import Dict, List, Optional, Set
from loguru import logger
from urllib.parse import urlparse
import aiohttp

from config import settings
from crawler.domain_worker import DomainWorker
from crawler.fetchers import get_fetcher, cleanup_fetcher
from crawler.robots_handler import RobotsHandler
from crawler.monitoring import CrawlMonitor
from crawler.models import CrawlSource, CrawlState
from crawler.url_utils import URLFilter

class CrawlOrchestrator:
    
    def __init__(
        self,
        sources: List[CrawlSource],
        max_pages: Optional[int] = None,
        initial_state: Optional[CrawlState] = None
    ):
        self.sources: Dict[str, CrawlSource] = {}
        domain_seeds: Dict[str, List[str]] = {}

        for src in sources:
            if src.domain not in self.sources:
                self.sources[src.domain] = src
                domain_seeds[src.domain] = [src.url]
            else:
                existing_src = self.sources[src.domain]
                existing_src.max_pages += src.max_pages
                existing_src.priority = min(existing_src.priority, src.priority)
                existing_src.quality_threshold = min(
                    existing_src.quality_threshold, 
                    src.quality_threshold
                )
                domain_seeds[src.domain].append(src.url)

        self.max_pages = max_pages or sum(
            src.max_pages for src in self.sources.values()
        )
        
        if initial_state:
            self.state = initial_state
        else:
            self.state = CrawlState()
            for domain, seeds in domain_seeds.items():
                source_config = self.sources[domain]
                for seed_url in seeds:
                    self.state.add_seed_url(
                        domain=domain,
                        url=seed_url,
                        seed_prefix=source_config.seed_prefix
                    )
        
        self.active_workers: Set[str] = set()
        self.finished_domains: Set[str] = set()
        self.stop_event = asyncio.Event()
        self.start_time = time.time()
        
        self.monitor = CrawlMonitor(
            total_capacity=self.max_pages,
            checkpoint_interval=settings.checkpoint_interval
        )
        
    async def start(self):
        logger.info(f"Starting Crawl4AI-based crawl with {len(self.sources)} domains")
        logger.info(f"Total capacity: {self.max_pages:,} pages")
        logger.info(f"Max concurrent workers: {settings.max_concurrent_crawls}")
        
        fetcher = await get_fetcher()
        robots_handler = RobotsHandler()
        url_filter = URLFilter()
        
        async with aiohttp.ClientSession() as http_session:
            
            logger.info("Loading robots.txt for all domains...")
            
            async def load_domain_robots(domain, session):
                await robots_handler.load_robots(domain, session)

            robots_tasks = [
                load_domain_robots(domain, http_session) 
                for domain in self.sources.keys()
            ]
            await asyncio.gather(*robots_tasks, return_exceptions=True)
            logger.info("Robots.txt loading complete.")
            for domain, source in self.sources.items():
                queue_size = self.state.get_queue_size(domain)
                visited = self.state.get_domain_count(domain)
                logger.info(
                    f"  {domain}: {visited}/{source.max_pages} crawled, "
                    f"{queue_size} queued"
                )
            
            monitor_task = asyncio.create_task(
                self.monitor.run(self.state, self.sources, self.finished_domains)
            )
            
            worker_tasks = set()
            no_work_cycles = 0
            max_no_work_cycles = 3
            
            try:
                while not self.stop_event.is_set():
                    available_slots = (
                        settings.max_concurrent_crawls - len(self.active_workers)
                    )
                    
                    if available_slots > 0:
                        domains_to_start = self._get_domains_to_start(available_slots)
                        
                        if domains_to_start:
                            no_work_cycles = 0
                            for domain in domains_to_start:
                                self.active_workers.add(domain)
                                worker = DomainWorker(
                                    domain=domain,
                                    source_config=self.sources[domain],
                                    state=self.state,
                                    fetcher=fetcher, 
                                    robots_handler=robots_handler,
                                    stop_event=self.stop_event
                                )
                                
                                task = asyncio.create_task(
                                    self._run_worker(worker, domain)
                                )
                                worker_tasks.add(task)
                                task.add_done_callback(worker_tasks.discard)
                                
                                logger.info(
                                    f"Started worker for {domain} "
                                    f"({len(self.active_workers)}/"
                                    f"{settings.max_concurrent_crawls} active)"
                                )
                        else:
                            if len(self.active_workers) == 0:
                                no_work_cycles += 1
                                logger.debug(
                                    f"No work available "
                                    f"(cycle {no_work_cycles}/{max_no_work_cycles})"
                                )
                                
                                if no_work_cycles >= max_no_work_cycles:
                                    if self._all_work_complete():
                                        logger.info("All domains completed")
                                        self.stop_event.set()
                                        break
                    
                    await asyncio.sleep(1)
                
                logger.info("Waiting for remaining workers to complete...")
                if worker_tasks:
                    await asyncio.gather(*worker_tasks, return_exceptions=True)
                
            finally:
                self.stop_event.set()
                monitor_task.cancel()
                
                for task in worker_tasks:
                    if not task.done():
                        task.cancel()
                
                if worker_tasks:
                    await asyncio.gather(*worker_tasks, return_exceptions=True)
                
                await cleanup_fetcher()
                
    def _get_domains_to_start(self, max_count: int) -> List[str]:
        candidates = []
        
        for domain, source in self.sources.items():
            if domain in self.finished_domains:
                continue
            
            if domain in self.active_workers:
                continue
            
            current_count = self.state.get_domain_count(domain)
            if current_count >= source.max_pages:
                if domain not in self.finished_domains:
                    self.finished_domains.add(domain)
                    logger.info(
                        f"Domain {domain} reached limit: "
                        f"{current_count}/{source.max_pages}"
                    )
                continue
            
            if not self.state.has_pending_urls(domain):
                if domain in self.state.domain_stats:
                    if domain not in self.finished_domains:
                        self.finished_domains.add(domain)
                        logger.info(
                            f"Domain {domain} exhausted with "
                            f"{current_count} pages crawled"
                        )
                continue
            
            queue_size = self.state.get_queue_size(domain)
            candidates.append((source.priority, -queue_size, domain))
        
        if not candidates:
            return []
        
        candidates.sort()
        return [domain for _, _, domain in candidates[:max_count]]
    
    async def _run_worker(self, worker: DomainWorker, domain: str):
        try:
            result = await worker.process_domain()
            
            if result.is_complete:
                self.finished_domains.add(domain)
                logger.info(
                    f"Domain {domain} completed: "
                    f"{result.pages_crawled}/{result.page_limit}"
                )
            elif result.is_exhausted:
                self.finished_domains.add(domain)
                logger.info(
                    f"Domain {domain} exhausted at "
                    f"{result.pages_crawled}/{result.page_limit}"
                )
                
        except Exception as e:
            logger.exception(f"Worker error for {domain}: {e}")
            self.finished_domains.add(domain)
        finally:
            self.active_workers.discard(domain)
    
    def _all_work_complete(self) -> bool:
        for domain in self.sources.keys():
            if domain not in self.finished_domains:
                if domain not in self.active_workers:
                    if self.state.has_pending_urls(domain):
                        return False
        
        return len(self.active_workers) == 0
    
    def get_state(self) -> CrawlState:
        return self.state
    
    def print_summary(self):
        elapsed = time.time() - self.start_time
        stats = self.state.get_statistics()
        
        logger.info("\n" + "="*70)
        logger.info("CRAWL SUMMARY (Crawl4AI)")
        logger.info("="*70)
        logger.info(f"Total time: {elapsed/60:.1f} minutes")
        logger.info(f"Pages accepted: {stats['pages_accepted']:,}")
        logger.info(f"Pages rejected (quality): {stats['pages_rejected_quality']:,}")
        logger.info(f"Pages rejected (duplicate): {stats['pages_rejected_duplicate']:,}")
        logger.info(f"Pages rejected (language): {stats['pages_rejected_lang']:,}")
        logger.info(f"Pages failed: {stats['pages_failed']:,}")
        logger.info(f"Domains completed: {len(self.finished_domains)}/{len(self.sources)}")
        logger.info(
            f"Average speed: "
            f"{stats['pages_accepted']/(elapsed/60 if elapsed > 0 else 1):.1f} pages/min"
        )
        
        logger.info("\nDomain breakdown:")
        for domain, source in sorted(self.sources.items()):
            count = self.state.get_domain_count(domain)
            status = "DONE" if domain in self.finished_domains else "PENDING"
            logger.info(f"  [{status}] {domain}: {count}/{source.max_pages}")
        
        logger.info("="*70)