from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from collections import Counter, deque


@dataclass
class CrawlSource:
    domain: str
    url: str
    seed_prefix: str
    max_pages: int
    priority: int
    quality_threshold: int


@dataclass
class PageResult:
    url: str
    success: bool
    new_links: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class DomainResult:
    domain: str
    pages_crawled: int
    page_limit: int
    is_complete: bool
    is_exhausted: bool


class SmartQueue:
    
    def __init__(self):
        self.high_priority = deque()
        self.medium_priority = deque()
        self.low_priority = deque()
        self.all_urls: Set[str] = set()
    
    def add(self, url: str) -> bool:
        if url in self.all_urls:
            return False
            
        self.all_urls.add(url)
        url_lower = url.lower()
        
        if any(kw in url_lower for kw in [
            'tutorial', 'guide', 'example', 'getting-started', 'howto'
        ]):
            self.high_priority.append(url)
        elif any(kw in url_lower for kw in [
            'docs', 'documentation', 'reference', 'api'
        ]):
            self.medium_priority.append(url)
        else:
            self.low_priority.append(url)
            
        return True
    
    def pop(self) -> str:
        if self.high_priority:
            url = self.high_priority.popleft()
        elif self.medium_priority:
            url = self.medium_priority.popleft()
        elif self.low_priority:
            url = self.low_priority.popleft()
        else:
            raise IndexError("Queue is empty")
            
        self.all_urls.discard(url)
        return url
    
    def __len__(self) -> int:
        return (
            len(self.high_priority) + 
            len(self.medium_priority) + 
            len(self.low_priority)
        )
    
    def to_list(self) -> List[str]:
        return (
            list(self.high_priority) + 
            list(self.medium_priority) + 
            list(self.low_priority)
        )
    
    @classmethod
    def from_list(cls, urls: List[str]) -> 'SmartQueue':
        queue = cls()
        for url in urls:
            queue.add(url)
        return queue


class CrawlState:
    
    def __init__(self):
        self.visited: Set[str] = set()
        self.queues: Dict[str, SmartQueue] = {}
        self.domain_counts: Counter = Counter()
        self.domain_stats: Dict[str, Dict] = {}
        self.statistics: Dict = {
            'pages_accepted': 0,
            'pages_rejected_quality': 0,
            'pages_rejected_duplicate': 0,
            'pages_rejected_lang': 0,
            'pages_rejected_empty': 0,
            'pages_rejected_short': 0,
            'pages_failed': 0,
            'fetch_crawl4ai': 0, 
        }
        
    def add_seed_url(self, domain: str, url: str, seed_prefix: str):
        if domain not in self.queues:
            self.queues[domain] = SmartQueue()
            self.domain_stats[domain] = {
                'seed_prefix': seed_prefix,
                'avg_latency': 1.0,
                'request_count': 0,
                'total_latency': 0.0
            }
        self.queues[domain].add(url)
    
    def mark_visited(self, url: str):
        self.visited.add(url)
    
    def is_visited(self, url: str) -> bool:
        return url in self.visited
    
    def add_url_to_queue(self, domain: str, url: str) -> bool:
        if domain not in self.queues:
            return False
        return self.queues[domain].add(url)
    
    def pop_url(self, domain: str) -> str:
        return self.queues[domain].pop()
    
    def has_pending_urls(self, domain: str) -> bool:
        if domain not in self.queues:
            return False
        queue_len = len(self.queues[domain])
        return queue_len > 0
    
    def get_queue_size(self, domain: str) -> int:
        return len(self.queues.get(domain, []))
    
    def increment_domain_count(self, domain: str):
        self.domain_counts[domain] += 1
    
    def get_domain_count(self, domain: str) -> int:
        return self.domain_counts.get(domain, 0)
    
    def update_latency(self, domain: str, latency: float):
        stats = self.domain_stats[domain]
        stats['request_count'] += 1
        stats['total_latency'] += latency
        stats['avg_latency'] = stats['total_latency'] / stats['request_count']
    
    def get_seed_prefix(self, domain: str) -> Optional[str]:
        return self.domain_stats.get(domain, {}).get('seed_prefix')
    
    def get_avg_latency(self, domain: str) -> float:
        return self.domain_stats.get(domain, {}).get('avg_latency', 1.0)
    
    def increment_stat(self, stat_name: str):
        if stat_name in self.statistics:
            self.statistics[stat_name] += 1
    
    def get_statistics(self) -> Dict:
        return self.statistics.copy()
    
    def to_dict(self) -> Dict:
        return {
            'visited': list(self.visited),
            'queues': {
                domain: queue.to_list()
                for domain, queue in self.queues.items()
            },
            'domain_counts': dict(self.domain_counts),
            'domain_stats': self.domain_stats,
            'statistics': self.statistics
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlState':
        state = cls()
        state.visited = set(data.get('visited', []))
        state.queues = {
            domain: SmartQueue.from_list(urls)
            for domain, urls in data.get('queues', {}).items()
        }
        state.domain_counts = Counter(data.get('domain_counts', {}))
        state.domain_stats = data.get('domain_stats', {})
        state.statistics = data.get('statistics', state.statistics)
        return state