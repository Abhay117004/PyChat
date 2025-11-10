import asyncio
import time
from pathlib import Path
from typing import Dict, Set
from loguru import logger

from crawler.models import CrawlSource, CrawlState
from crawler.state_manager import StateManager


class CrawlMonitor:
    
    def __init__(self, total_capacity: int, checkpoint_interval: int):
        self.total_capacity = total_capacity
        self.checkpoint_interval = checkpoint_interval
        self.start_time = time.time()
        self.state_manager = StateManager(
            checkpoint_file=Path("data/checkpoints/crawl_state.json"),
            auto_resume=True
        )
    
    async def run(
        self,
        state: CrawlState,
        sources: Dict[str, CrawlSource],
        finished_domains: Set[str]
    ):
        try:
            while True:
                await asyncio.sleep(self.checkpoint_interval)
                
                self.state_manager.save_checkpoint(state)
                self._print_progress(state, sources, finished_domains)
        except asyncio.CancelledError:
            logger.debug("Monitor cancelled")
    
    def _print_progress(
        self,
        state: CrawlState,
        sources: Dict[str, CrawlSource],
        finished_domains: Set[str]
    ):
        elapsed = time.time() - self.start_time
        elapsed_min = elapsed / 60
        
        stats = state.get_statistics()
        pages_accepted = stats['pages_accepted']
        
        pages_per_min = pages_accepted / elapsed_min if elapsed_min > 0 else 0
        
        queue_total = sum(
            state.get_queue_size(domain)
            for domain in sources.keys()
        )
        
        active_domains = [
            d for d in sources.keys()
            if d not in finished_domains
        ]
        
        logger.info("\n" + "="*70)
        logger.info("CRAWL PROGRESS")
        logger.info("="*70)
        logger.info(f"Elapsed: {elapsed_min:.1f} min")
        logger.info(f"Pages: {pages_accepted:,} / {self.total_capacity:,}")
        logger.info(f"Speed: {pages_per_min:.1f} pages/min")
        logger.info(f"Queue: {queue_total:,} URLs pending")
        logger.info(f"Domains: {len(finished_domains)}/{len(sources)} finished")
        logger.info(
            f"Active: {', '.join(active_domains[:5])}"
            f"{' ...' if len(active_domains) > 5 else ''}"
        )
        logger.info(
            f"Stats: Accepted={pages_accepted:,} | "
            f"Rejected(Q)={stats['pages_rejected_quality']:,} | "
            f"Rejected(D)={stats['pages_rejected_duplicate']:,} | "
            f"Failed={stats['pages_failed']:,}"
        )
        logger.info("="*70)