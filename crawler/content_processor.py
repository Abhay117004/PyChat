from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse
from langdetect import detect, LangDetectException
from loguru import logger

from config import settings
from crawler.url_utils import URLNormalizer, URLFilter
from quality_analyzer import QualityAnalyzer
from db_utils import DedupDatabase


@dataclass
class ProcessResult:
    accepted: bool
    quality_score: float = 0.0
    page_data: Optional[dict] = None
    links: List[str] = None
    rejection_reason: Optional[str] = None


class ContentProcessor:
    
    def __init__(
        self,
        domain: str,
        seed_prefix: str,
        quality_threshold: int,
        dedup_db: DedupDatabase
    ):
        self.domain = domain
        self.seed_prefix = seed_prefix
        self.quality_threshold = quality_threshold
        
        self.url_normalizer = URLNormalizer(domain, seed_prefix)
        self.url_filter = URLFilter()
        self.quality_analyzer = QualityAnalyzer(dedup_db)
    
    async def process(
        self,
        url: str,
        markdown: Optional[str],
        text_content: Optional[str],
        title: str,
        links: List[str],
        metadata: Optional[dict] = None
    ) -> ProcessResult:
        
        filtered_links = self._filter_links(links, url) 
        
        content_to_process = markdown
        is_raw_content = False

        if not content_to_process or not content_to_process.strip():
            if url.endswith(('.ipynb', '.py')) and text_content:
                logger.debug(f"Using raw text content for {url}")
                content_to_process = text_content
                is_raw_content = True
            else:
                return ProcessResult(
                    accepted=False,
                    rejection_reason='empty',
                    links=filtered_links
                )
        
        if len(content_to_process.strip()) < settings.min_char_count:
             return ProcessResult(
                accepted=False,
                rejection_reason='empty_strip',
                links=filtered_links
            )
        
        word_count = len(content_to_process.split())
        if word_count < settings.min_word_count:
            return ProcessResult(
                accepted=False,
                rejection_reason='too_short',
                links=filtered_links
            )
        
        if not self._is_english(content_to_process):
            return ProcessResult(
                accepted=False,
                rejection_reason='language',
                links=filtered_links
            )
        
        quality = self.quality_analyzer.calculate_quality(content_to_process, url, title)
        
        if quality.is_duplicate:
            return ProcessResult(
                accepted=False,
                quality_score=quality.score,
                rejection_reason='duplicate',
                links=filtered_links
            )
        
        if quality.score < self.quality_threshold:
            return ProcessResult(
                accepted=False,
                quality_score=quality.score,
                rejection_reason='quality',
                links=filtered_links
            )
        
        page_data = {
            'url': url,
            'title': title,
            'text': content_to_process,
            'domain': self.domain,
            'quality_score': quality.score,
            'content_type': quality.content_type,
            'is_duplicate': quality.is_duplicate,
            'boilerplate_ratio': quality.boilerplate_ratio,
            'word_count': quality.word_count,
            'has_code': quality.has_code,
        }
        
        if metadata:
            page_data.update({
                'metadata_word_count': metadata.get('word_count', 0),
                'code_blocks': metadata.get('code_blocks', 0),
                'has_tables': metadata.get('has_tables', False),
            })
        
        if is_raw_content:
            page_data['has_code'] = True
            page_data['content_type'] = 'code'
        
        return ProcessResult(
            accepted=True,
            quality_score=quality.score,
            page_data=page_data,
            links=filtered_links
        )
    
    def _is_english(self, text: str) -> bool:
        try:
            lang = detect(text[:500])
            return lang == 'en'
        except LangDetectException:
            logger.debug("Could not detect language, assuming English")
            return True
    
    def _filter_links(self, links: List[str], base_url: str) -> List[str]:
        filtered = []
        if not links:
            return []
        
        for link in links:
            try:
                normalized = self.url_normalizer.normalize(link)
                
                if normalized and self.url_filter.should_crawl(normalized):
                    filtered.append(normalized)
            except Exception:
                continue
        
        return list(set(filtered))