import asyncio
from typing import Optional, List, Dict
from fastapi import HTTPException
from spellchecker import SpellChecker

try:
    from groq import Groq, RateLimitError, AuthenticationError, APIConnectionError, GroqError
except ImportError:
    Groq = None
    RateLimitError = None
    AuthenticationError = None
    APIConnectionError = None
    GroqError = None

from config import settings
from .utils.logging import log_step, log_error, timeit
from .utils.cache import rewrite_cache


class LLMClient:
    REWRITE_TEMPLATE = """You are an expert query optimizer. Fix typos and clarify the user's query to make it ideal for a vector search.
Respond ONLY with the improved query. Do not add explanations."""

    VERIFICATION_TEMPLATE = """You are a fact-checker. Verify if ANSWER is fully supported by CONTEXT.
- If fully accurate, respond: VERIFIED
- If not, correct it using CONTEXT only."""

    def __init__(self):
        if not Groq:
            raise RuntimeError("Groq library not installed. Install with: pip install groq")
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY not found in environment variables")

        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        self.max_tokens = settings.max_output_tokens
        self.max_context = getattr(settings, "max_verification_context", 8000)

        self.spell = SpellChecker()
        self.spell.word_frequency.load_words([
            # core tech terms
            "python", "pandas", "numpy", "torch", "pytorch", "tensorflow",
            "sklearn", "scikit-learn", "fastapi", "flask", "django",
            "asyncio", "sqlite", "mongodb", "postgres", "docker", "kubernetes",
            "aws", "gcp", "azure", "huggingface", "openai", "groq",
            "yolo", "yolov5", "yolov8", "bert", "transformer", "rag",
            "mnist", "csv", "json", "yaml", "http", "api", "rest"
        ])

    @timeit
    async def call(self, messages: List[Dict[str, str]], temperature: float) -> str:
        try:
            completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
                top_p=1,
                stream=False,
                stop=None,
            )
            return completion.choices[0].message.content.strip()
        except (RateLimitError, AuthenticationError, APIConnectionError, GroqError) as e:
            log_error(f"Groq API Error: {e}")
            code = 502
            if isinstance(e, RateLimitError):
                code = 429
            elif isinstance(e, AuthenticationError):
                code = 401
            elif isinstance(e, APIConnectionError):
                code = 504
            raise HTTPException(status_code=code, detail=str(e))
        except Exception as e:
            log_error(f"Generic Error in call(): {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    def _quick_spell_check(self, query: str) -> str:
        tokens = query.split()
        corrected_tokens = []
        skip_words = {
            "csv", "json", "yaml", "api", "rest", "fastapi", "flask", "django",
            "python", "pandas", "numpy", "torch", "pytorch", "tensorflow",
        }

        for token in tokens:
            clean = token.strip(".,!?()[]{}").lower()
            if clean in skip_words:
                corrected_tokens.append(token)
                continue

            if not self.spell.known([clean]):
                correction = self.spell.correction(clean)
                if correction and correction != clean:
                    token = token.replace(clean, correction)
            corrected_tokens.append(token)

        return " ".join(corrected_tokens)

    @timeit
    async def rewrite_query(self, query: str) -> str:
        cached = rewrite_cache.get(query)
        if cached:
            log_step("Cache", "Rewrite cache hit")
            return cached

        spell_checked = self._quick_spell_check(query)
        if spell_checked != query:
            log_step("Spell", f"'{query}' -> '{spell_checked}'")
            rewrite_cache.set(query, spell_checked)
            return spell_checked

        words = query.split()
        if (
            len(words) > 5
            and query.strip().endswith("?")
            and query.lower().startswith(("how", "what", "why", "when", "where", "can", "should"))
        ):
            log_step("Rewrite", "Query well-formed, skipping LLM rewrite")
            rewrite_cache.set(query, query)
            return query

        try:
            messages = [
                {"role": "system", "content": self.REWRITE_TEMPLATE},
                {"role": "user", "content": query},
            ]
            rewritten = await self.call(messages, temperature=0.0)
            rewritten = rewritten.strip().strip("`'\"").strip()
            if not rewritten or len(rewritten) > len(query) * 2.5:
                rewritten = query
            rewrite_cache.set(query, rewritten)
            return rewritten
        except Exception as e:
            log_error(f"Rewrite failed: {e}")
            return query

    @timeit
    async def verify_answer(self, query: str, answer: str, context: str) -> str:
        try:
            truncated = context[:self.max_context]
            user_prompt = f"CONTEXT:\n{truncated}\n\n---\n\nQUESTION: {query}\n\nANSWER: {answer}"
            messages = [
                {"role": "system", "content": self.VERIFICATION_TEMPLATE},
                {"role": "user", "content": user_prompt},
            ]
            result = await self.call(messages, temperature=0.1)
            if result.strip().upper() == "VERIFIED":
                log_step("Verify", "Answer VERIFIED")
                return answer
            log_step("Verify", "Answer corrected after verification")
            return result.strip()
        except Exception as e:
            log_error(f"Verification failed: {e}")
            return answer

    async def health_check(self) -> bool:
        try:
            await self.call(messages=[{"role": "user", "content": "test"}], temperature=0.1)
            return True
        except Exception:
            return False
