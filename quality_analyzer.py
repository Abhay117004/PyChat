import re
from dataclasses import dataclass
from typing import Optional, Set
from collections import Counter
from db_utils import DedupDatabase
from config import settings

@dataclass
class PageQuality:
    score: float
    has_code: bool
    word_count: int
    structure_score: float
    clarity_score: float
    uniqueness_score: float
    content_type: str
    is_duplicate: bool = False
    boilerplate_ratio: float = 0.0


class QualityAnalyzer:
    def __init__(self, dedup_db: DedupDatabase):
        self.db = dedup_db
    
    def _calculate_boilerplate_ratio(self, text: str) -> float:
        boilerplate_indicators = [
            'click here', 'read more', 'subscribe', 'newsletter',
            'follow us', 'share this', 'related posts', 'comments',
            'copyright', 'all rights reserved', 'privacy policy',
            'terms of service', 'cookie policy', 'advertisement',
            'sign up', 'log in', 'create account', 'join now',
            'follow @', 'tweet this', 'share on facebook'
        ]
        
        text_lower = text.lower()
        total_chars = len(text)
        if total_chars == 0:
            return 1.0
        
        boilerplate_chars = sum(
            len(indicator) * text_lower.count(indicator) 
            for indicator in boilerplate_indicators
        )
        return min(boilerplate_chars / total_chars, 1.0)
    
    def _is_near_duplicate(self, text: str, title: str) -> bool:
        return self.db.check_duplicate(text, title)

    def calculate_quality(self, text: str, url: str, title: str) -> PageQuality:
        is_duplicate = False
        boilerplate_ratio = 0.0
        
        if settings.enable_content_deduplication:
            is_duplicate = self._is_near_duplicate(text, title)
        
        boilerplate_ratio = self._calculate_boilerplate_ratio(text)
        
        scores = {}
        
        code_indicators = [
            '```', 'def ', 'class ', 'import ', 'function ',
            '>>>', 'print(', 'return ', 'for ', 'if ', 'while ',
            'const ', 'let ', 'var ', 'public ', 'private ',
            'void ', 'int ', 'string ', 'float ', 'double '
        ]
        has_code = any(ind in text for ind in code_indicators)
        code_blocks = text.count('```') // 2
        
        if has_code:
            scores['code'] = min(25, 10 + (code_blocks * 5))
        else:
            scores['code'] = 0

        words = text.split()
        word_count = len(words)
        
        if word_count < 50:
            scores['clarity'] = 0
        elif word_count < 150:
            scores['clarity'] = 10
        elif word_count < 500:
            scores['clarity'] = 15
        else:
            scores['clarity'] = 20

        structure_score = 0
        has_headers = bool(re.search(r'^#{1,4} ', text, re.MULTILINE))
        if has_headers: structure_score += 7
        has_lists = '•' in text or bool(re.search(r'^\d+\.', text, re.MULTILINE))
        if has_lists: structure_score += 4
        has_paragraphs = text.count('\n\n') > 2
        if has_paragraphs: structure_score += 4
        scores['structure'] = structure_score

        if 100 < word_count < 2000:
            scores['length'] = 10
        elif 50 < word_count <= 100 or 2000 <= word_count < 3000:
            scores['length'] = 7
        else:
            scores['length'] = 3

        unique_words = len(set(word.lower() for word in words if len(word) > 3))
        uniqueness_ratio = unique_words / max(word_count, 1)
        if uniqueness_ratio > 0.5:
            scores['uniqueness'] = 15
        elif uniqueness_ratio > 0.3:
            scores['uniqueness'] = 10
        else:
            scores['uniqueness'] = 5

        completeness_score = 0
        has_examples = 'example' in text.lower() or has_code
        if has_examples: completeness_score += 7
        has_explanation = word_count > 100
        if has_explanation: completeness_score += 5
        no_broken = not text.endswith('...')
        if no_broken: completeness_score += 3
        scores['completeness'] = completeness_score

        total_score = sum(scores.values())
        total_score -= (boilerplate_ratio * 30)
        if is_duplicate:
            total_score *= 0.5
        
        content_type = self.classify_content(text, url, title)
        if content_type in ['tutorial', 'example', 'guide']:
            total_score = min(100, total_score * 1.1)
        
        return PageQuality(
            score=round(max(0, total_score), 1),
            has_code=has_code,
            word_count=word_count,
            structure_score=scores['structure'] / 15,
            clarity_score=scores['clarity'] / 20,
            uniqueness_score=scores['uniqueness'] / 15,
            content_type=content_type,
            is_duplicate=is_duplicate,
            boilerplate_ratio=round(boilerplate_ratio, 2)
        )

    @staticmethod
    def classify_content(text: str, url: str, title: str) -> str:
        text_lower = text.lower()
        title_lower = title.lower()
        url_lower = url.lower()

        if any(kw in title_lower or kw in url_lower for kw in ['tutorial', 'guide', 'how to', 'getting started', 'learn']):
            return 'tutorial'
        if any(kw in title_lower for kw in ['example', 'cookbook', 'recipe', 'sample']) or text.count('```') > 3:
            return 'example'
        if any(kw in title_lower or kw in url_lower for kw in ['reference', 'api', 'documentation', 'method', 'function', 'class', 'module']):
            return 'reference'
        if any(kw in title_lower for kw in ['guide', 'overview', 'best practices', 'tips']):
            return 'guide'
        if title_lower.startswith('how to') or 'how to' in url_lower:
            return 'howto'
        return 'general'