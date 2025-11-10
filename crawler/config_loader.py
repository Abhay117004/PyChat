from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
import yaml
from loguru import logger

from crawler.models import CrawlSource


class ConfigLoader:
    def __init__(self, sources_file: Path):
        self.sources_file = sources_file
    
    def load_sources(
        self,
        cli_quality_threshold: Optional[int] = None
    ) -> List[CrawlSource]:
        logger.info(f"Loading sources from: {self.sources_file}")
        
        try:
            with open(self.sources_file, 'r') as f:
                config = yaml.safe_load(f)
                sources_config = config.get('sources', {})
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.sources_file}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse config: {e}")
            return []
        
        sources = []
        
        if not isinstance(sources_config, dict):
            logger.error("'sources' key must be a dictionary")
            return []
        
        for category, source_list in sources_config.items():
            if not isinstance(source_list, list):
                continue
            
            for source in source_list:
                if not isinstance(source, dict) or 'url' not in source:
                    continue
                
                url = source['url']
                domain = urlparse(url).netloc
                
                if not domain:
                    continue
                
                parsed_url = urlparse(url)
                seed_prefix = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                sources.append(CrawlSource(
                    domain=domain,
                    url=url,
                    seed_prefix=seed_prefix,
                    max_pages=source.get('max_pages', 5000),
                    priority=source.get('priority', 1),
                    quality_threshold=cli_quality_threshold or source.get('quality_threshold', 45)
                ))
        
        logger.info(f"Loaded {len(sources)} sources")
        return sources