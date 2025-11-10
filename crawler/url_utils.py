from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

class URLNormalizer:
    def __init__(self, domain: str, seed_prefix: str):
        self.domain = domain
        self.seed_prefix = seed_prefix
        self.tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 
            'utm_term', 'utm_content', 'gclid', 'fbclid'
        }

    def normalize(self, url: str) -> str | None:
        try:
            parts = urlparse(url)
            
            if parts.netloc != self.domain:
                return None
        
            
            path = parts.path.strip()
            if not path:
                path = '/' 
            query_params = parse_qs(parts.query)
            clean_params = {
                k: v for k, v in query_params.items() 
                if k.lower() not in self.tracking_params
            }
            query_clean = urlencode(clean_params, doseq=True)

            normalized = urlunparse((
                parts.scheme,
                parts.netloc,
                path,
                parts.params,
                query_clean,
                ''  
            ))
            
            return normalized.rstrip('/')
            
        except Exception:
            return None 

class URLFilter:
    def __init__(self):
        self.bad_extensions = {
            '.zip', '.gz', '.tar', '.pdf', '.png', '.jpg', '.jpeg', '.gif',
            '.css', '.js', '.xml', '.rss', '.svg', '.mp4', '.mp3', '.avi',
            '.json', '.txt', '.rst', '.md',
        }

        self.negative_keywords = {
            'login', 'register', 'signup', 'signin', 'logout', 'account',
            'cart', 'checkout', 'shop', 'store', 'product', 'price',
            'career', 'jobs', 'hire', 'about', 'contact', 'team',
            'policy', 'terms', 'privacy', 'legal', 'security',
            'forum', 'blog', 'news', 'community', 'support',
            'tag', 'tags', 'category', 'categories', 'author', 'user',
            'profile', 'settings', 'dashboard', 'download', 'subscribe',
            'search', 'feed', 'go', 'redirect', 'share', 'compare',
            'assets', '_sources', '_downloads',
        }

        self.positive_keywords = {
            'python', 'django', 'flask', 'fastapi', 'numpy', 'pandas',
            'scipy', 'sklearn', 'scikit-learn', 'matplotlib', 'seaborn',
            'pytorch', 'tensorflow', 'keras', 'pytest', 'asyncio', 'sqlalchemy',
            'pydantic', 'datascience', 'machine-learning', 'deep-learning',
        }

        self.generic_keywords = {
            'doc', 'docs', 'documentation', 'tutorial', 'guide', 'howto',
            'getting-started', 'example', 'examples', 'api', 'reference',
            'dsa', 'data-structures', 'algorithm', 'algorithms',
            'programming', 'coding', 'development', 'userguide'
        }

    def _score_url(self, url: str) -> float:
        text = url.lower()
        score = 0

        score += sum(1 for w in self.positive_keywords if w in text)

        if any(w in text for w in self.generic_keywords):
            score += 2

        if '/api/' in text or '/v1/' in text or '/v2/' in text:
            score += 1

        if any(bad in text for bad in ['utm_', '?ref=', 'affiliate']):
            score -= 1

        return score

    def should_crawl(self, url: str) -> bool:
        try:
            parts = urlparse(url)
            path_lower = parts.path.lower()

            if any(path_lower.endswith(ext) for ext in self.bad_extensions):
                return False

            if any(bad in path_lower for bad in self.negative_keywords):
                return False

            text = (parts.netloc + parts.path).lower()

            score = self._score_url(text)

            if score < 1:
                return False

            return True

        except Exception:
            return False