import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from config import settings


class RobotsHandler:
    CACHE_FILE = Path("data/robots_cache.json")
    CACHE_TTL_HOURS = 24
    MAX_SITEMAP_URLS = 50
    def __init__(self):
        self.parsers: Dict[str, RobotFileParser] = {}
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, dict]:
        if not self.CACHE_FILE.exists():
            return {}
        try:
            with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
                now = datetime.now()
                fresh_cache = {
                    k: v for k, v in cache.items()
                    if datetime.fromtimestamp(v.get("timestamp", 0)) > now - timedelta(hours=self.CACHE_TTL_HOURS)
                }
                return fresh_cache
        except Exception as e:
            logger.warning(f"Failed to load robots cache: {e}")
            return {}

    def _save_cache(self) -> None:
        try:
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save robots cache: {e}")

    async def load_robots(self, domain: str, http_session: aiohttp.ClientSession):
        if domain in self.parsers:
            return 

        cached = self.cache.get(domain)
        if cached and datetime.fromtimestamp(cached["timestamp"]) > datetime.now() - timedelta(hours=self.CACHE_TTL_HOURS):
            parser = RobotFileParser()
            parser.allow_all = cached.get("allow_all", True)
            self.parsers[domain] = parser
            logger.debug(f"Loaded robots.txt for {domain} from cache")
            return

        robots_url = f"https://{domain}/robots.txt"
        parser = RobotFileParser()
        parser.allow_all = False  

        try:
            async with http_session.get(robots_url, timeout=10.0) as response:
                if 200 <= response.status < 300:
                    text = await response.text()
                    parser.parse(text.splitlines())
                    logger.debug(f"Parsed robots.txt for {domain}")
                else:
                    parser.allow_all = True
                    logger.debug(f"No valid robots.txt for {domain} (status {response.status}) → allow all")
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e} → allowing all")
            parser.allow_all = True

        self.parsers[domain] = parser
        self.cache[domain] = {"allow_all": parser.allow_all, "timestamp": datetime.now().timestamp()}
        self._save_cache()
    async def fetch_sitemaps(self, domain: str, http_session: aiohttp.ClientSession) -> List[str]:
        if domain not in self.parsers:
            logger.error(f"load_robots must be called before fetch_sitemaps for {domain}")
            return []

        cached = self.cache.get(domain, {})
        if "sitemaps" in cached and datetime.fromtimestamp(cached["timestamp"]) > datetime.now() - timedelta(hours=self.CACHE_TTL_HOURS):
            logger.debug(f"Using cached sitemaps for {domain}")
            return cached.get("sitemaps", [])

        parser = self.parsers[domain]
        sitemap_urls = parser.sitemaps or [f"https://{domain}/sitemap.xml"]
        all_page_urls = []

        for sitemap_url in sitemap_urls[:3]:
            try:
                urls = await self._fetch_and_parse_sitemap(
                    sitemap_url,
                    http_session,
                    remaining_quota=self.MAX_SITEMAP_URLS - len(all_page_urls)
                )
                all_page_urls.extend(urls)
                if len(all_page_urls) >= self.MAX_SITEMAP_URLS:
                    break
            except Exception as e:
                logger.warning(f"Failed to parse sitemap {sitemap_url}: {e}")

        all_page_urls = list(set(all_page_urls[:self.MAX_SITEMAP_URLS]))
        self.cache[domain]["sitemaps"] = all_page_urls
        self.cache[domain]["timestamp"] = datetime.now().timestamp()
        self._save_cache()
        return all_page_urls

    async def _fetch_and_parse_sitemap(
        self,
        sitemap_url: str,
        http_session: aiohttp.ClientSession,
        remaining_quota: int = None
    ) -> List[str]:
        if remaining_quota is not None and remaining_quota <= 0:
            return []

        try:
            async with http_session.get(sitemap_url, timeout=20.0) as response:
                if response.status != 200:
                    return []
                xml_content = await response.read()
                soup = BeautifulSoup(xml_content, "xml")

                urls = [tag.find("loc").text for tag in soup.find_all("url") if tag.find("loc")]
                sitemaps = [tag.find("loc").text for tag in soup.find_all("sitemap") if tag.find("loc")]

                collected = urls[:remaining_quota] if remaining_quota else urls
                for nested_url in sitemaps[:3]:
                    nested = await self._fetch_and_parse_sitemap(
                        nested_url, http_session,
                        remaining_quota=(remaining_quota - len(collected)) if remaining_quota else None
                    )
                    collected.extend(nested)
                    if remaining_quota and len(collected) >= remaining_quota:
                        break

                return collected
        except Exception as e:
            logger.warning(f"Error parsing sitemap {sitemap_url}: {e}")
            return []

    def can_fetch(self, domain: str, url: str) -> bool:
        parser = self.parsers.get(domain)
        if not parser:
            logger.warning(f"No robots.txt parser found for {domain}, allowing fetch")
            return True
        path = urlparse(url).path or "/"
        if urlparse(url).query:
            path += "?" + urlparse(url).query
        return parser.can_fetch("*", path)
