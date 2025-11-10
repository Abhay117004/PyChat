from .schemas import QueryClassification


class QueryClassifier:
    @staticmethod
    def classify(query: str) -> QueryClassification:
        q = query.lower().strip()
        words = q.split()

        if len(words) <= 3 and any(g in q for g in ['hi', 'hello', 'hey', 'greetings']):
            return QueryClassification(intent="greeting", needs_context=False, complexity="simple")

        if q.startswith(('how to', 'how do', 'how can', 'how should', 'how would')):
            return QueryClassification(intent="howto", needs_context=True, complexity="medium")

        code_words = ['code', 'function', 'implement',
                      'write', 'create', 'script', 'program', 'build']
        if any(w in q for w in code_words):
            return QueryClassification(intent="code", needs_context=True, complexity="medium")

        if 'example' in q or 'show me' in q or 'demonstrate' in q:
            return QueryClassification(intent="example", needs_context=True, complexity="simple")

        compare_words = ['difference between', 'compare', 'vs',
                         'versus', 'better than', 'which one', 'which is']
        if any(w in q for w in compare_words):
            return QueryClassification(intent="comparison", needs_context=True, complexity="complex")

        explain_words = ['what is', "what's", 'explain',
                         'describe', 'define', 'tell me about', 'what are']
        if any(w in q for w in explain_words):
            return QueryClassification(intent="explain", needs_context=True, complexity="medium")

        debug_words = ['error', 'fix', 'bug', 'issue', 'problem',
                       'not working', 'broken', 'fails', 'exception']
        if any(w in q for w in debug_words):
            return QueryClassification(intent="debug", needs_context=True, complexity="medium")

        return QueryClassification(intent="general", needs_context=True, complexity="medium")
