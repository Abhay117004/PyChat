import re
from typing import List, Optional
from loguru import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter


class SmartTextSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int, min_chunk_size: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        self.separators = [
            "\n```python\n", "\n```\n", "\n```java\n", "\n```bash\n", "\n```sql\n",
            "\n# ", "\n## ", "\n### ", "\n#### ",
            "\n- ", "\n* ", "\n1. ", "\n\n", "\n", " ", ""
        ]

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=self.separators
        )

    def split_text(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        if text.count("```") % 2 == 1:
            logger.debug("Unbalanced code block detected — auto-closing ```")
            text += "\n```"

        if len(text.strip()) < self.min_chunk_size:
            return []
        if len(text) > 200_000:
            text = text[:200_000] + "\n[...truncated...]"

        chunks = self.splitter.split_text(text)

        final_chunks = [
            chunk for chunk in chunks
            if len(chunk.strip()) >= self.min_chunk_size
        ]

        return final_chunks
