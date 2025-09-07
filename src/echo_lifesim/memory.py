from __future__ import annotations
from typing import List
from .models import Episode, PersonaState

class MemoryIndex:
    """Simple heuristic retrieval without vectors."""
    def __init__(self, state: PersonaState):
        self.state = state

    def relevance(self, ep: Episode, query_tokens: List[str], now: float) -> float:
        overlap = sum(1 for t in query_tokens if t in ep.text.lower())
        overlap_score = overlap / max(1, len(query_tokens))
        recency = 1.0 / (1.0 + (now - ep.ts) / 3600.0)
        return overlap_score * 0.7 + ep.importance * 0.3 + recency * 0.2

    def retrieve(self, query: str, k: int = 5) -> List[Episode]:
        tokens = [t for t in query.lower().split() if len(t) > 2]
        now = self.state.episodes[-1].ts if self.state.episodes else 0.0
        scored = [ (self.relevance(ep, tokens, now), ep) for ep in self.state.episodes[-100:] ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _score, ep in scored[:k]]
