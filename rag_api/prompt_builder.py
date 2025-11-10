from typing import List, Dict
import json


class PromptBuilder:
    BASE_SYSTEM = """You are an **expert Python programming assistant**. Your goal is to provide a single, comprehensive, and correct **Python** answer.
- **Your knowledge is limited to Python.** If the user asks for another language (e.g., Java, C++, JavaScript), you **must** politely state that you are a Python-focused assistant and offer to provide the Python equivalent. **Do not provide code for other languages.**

--- YOUR ANSWERING PROCESS ---
1.  **Understand the User's Need:** First, analyze the `USER QUERY` to understand their core question.
2.  **Survey ALL Context:** Read **every** `--- SOURCE ---` provided in the `DOCUMENTATION` section. Do not just use the first one.
3.  **Critically Synthesize:** Compare the sources. Identify the best parts, find conflicts, and spot bugs. For example, Source #1 might have good imports, but Source #3 has the correct, bug-free implementation.
4.  **Construct the Best Answer:** Using your own expert knowledge, **synthesize** the best information from all sources into a single, cohesive, and complete answer. You must **fix any bugs** or fill in missing steps from the context to provide a final, production-quality solution.
5.  **Be Comprehensive:** Do not just repeat a single source. Your job is to create the *best possible answer* by integrating all relevant information.
"""

    @staticmethod
    def build(query: str, docs: List[dict], intent: str, complexity: str = "medium") -> str:
        if intent == "greeting":
            return PromptBuilder._build_greeting_prompt(query)

        context = PromptBuilder._build_context(docs)

        templates = {
            "code": PromptBuilder._build_code_prompt,
            "example": PromptBuilder._build_example_prompt,
            "howto": PromptBuilder._build_howto_prompt,
            "explain": PromptBuilder._build_explain_prompt,
            "debug": PromptBuilder._build_debug_prompt,
            "comparison": PromptBuilder._build_comparison_prompt,
            "general": PromptBuilder._build_general_prompt
        }

        builder = templates.get(intent, PromptBuilder._build_general_prompt)
        return builder(query, context)

    @staticmethod
    def _build_greeting_prompt(query: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Respond warmly to the user's greeting.
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_code_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Provide a single, complete, and correct **code solution** for the user's query.

**INSTRUCTIONS:**
- Your final answer must be a complete, runnable code example with clear explanations for each part.
- Follow the 5-step "ANSWERING PROCESS" from your system prompt to synthesize the best possible solution from the context.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_example_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Provide a practical, working **example** for the user's query.

**INSTRUCTIONS:**
- The example should be clear, correct, and well-explained.
- Follow the 5-step "ANSWERING PROCESS" from your system prompt to find and synthesize the best example from the context.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_howto_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Provide clear, correct, **step-by-step instructions**.

**INSTRUCTIONS:**
- Synthesize a single, complete guide from all sources.
- Ensure all steps are in a logical order and any code provided is correct.
- Follow the 5-step "ANSWERING PROCESS" from your system prompt.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_explain_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** **Explain** the concept clearly, with code examples and practical use cases where appropriate.

**INSTRUCTIONS:**
- Follow the 5-step "ANSWERING PROCESS" from your system prompt to synthesize the most comprehensive explanation.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_debug_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Help the user **debug** their issue.

**INSTRUCTIONS:**
- Identify the likely issue or error.
- Explain the cause of the bug.
- Provide the corrected code or solution.
- Follow the 5-step "ANSWERING PROCESS" from your system prompt.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_comparison_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Provide an objective **comparison**.

**INSTRUCTIONS:**
- Compare the items with examples, pros/cons, and a final recommendation if possible.
- Follow the 5-step "ANSWERING PROCESS" from your system prompt to gather all comparison points.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_general_prompt(query: str, context: str) -> str:
        return f"""{PromptBuilder.BASE_SYSTEM}
---
**TASK:** Answer the user's **general query** directly and practically, using code examples when helpful.

**INSTRUCTIONS:**
- Follow the 5-step "ANSWERING PROCESS" from your system prompt to construct the best answer.

{context}
---
USER QUERY:
{query}
"""

    @staticmethod
    def _build_context(docs: List[dict], max_length: int = 8000) -> str:
        if not docs:
            return ""

        parts = []
        total_len = 0

        for i, doc in enumerate(docs, 1):
            text = doc['text'].strip()
            meta = doc.get('metadata', {})

            has_code = '```' in text or 'def ' in text or 'class ' in text
            has_example = 'example' in text.lower()

            markers = []
            if has_code:
                markers.append("CODE")
            if has_example:
                markers.append("EXAMPLES")

            marker_str = f"[{' | '.join(markers)}]" if markers else "[REFERENCE]"

            doc_len = len(text)
            if total_len + doc_len + 500 > max_length:
                remaining = max_length - total_len
                if remaining > 300:
                    text = text[:remaining] + "\n[...truncated...]"
                else:
                    break

            title = meta.get('title', 'Reference')
            chunk = f"\n--- SOURCE #{i} {marker_str} ---\n# {title}\n{text}\n"

            parts.append(chunk)
            total_len += len(chunk)
            
            if total_len >= max_length:
                break

        header = f"--- DOCUMENTATION ({len(parts)} sources) ---\n"
        header += "You MUST analyze all the following sources to answer the user's query.\n"
        
        return header + "\n".join(parts)