"""Memory retrieval/ranking adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.memory.preferences import PreferenceStore
from backend.memory.scoring import MemoryScorer
from backend.memory.summarizer import MemorySummarizer


class MemoryRetriever:
    """Ranks Chroma-style memory results and preference context."""

    def __init__(self, memory_manager=None, preference_store: PreferenceStore | None = None, scorer: MemoryScorer | None = None):
        self.memory_manager = memory_manager
        self.preferences = preference_store or PreferenceStore()
        self.scorer = scorer or MemoryScorer()
        self.summarizer = MemorySummarizer()

    def retrieve(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        memories: list[dict[str, Any]] = []
        if self.memory_manager is not None:
            memories.extend(self._query_manager(query, n_results))
        ranked = self.scorer.rank(memories, query=query)[:n_results]
        prefs = [pref.to_dict() for pref in self.preferences.list()]
        return {
            "query": query,
            "memories": ranked,
            "preferences": prefs,
            "summary": self.summarizer.summarize_memories(ranked),
            "preference_context": self.preferences.as_context(),
        }

    def build_context(self, query: str, n_results: int = 5) -> str:
        retrieved = self.retrieve(query, n_results=n_results)
        parts = [retrieved["preference_context"], retrieved["summary"]]
        return "\n\n".join(part for part in parts if part and not part.endswith("No relevant memories."))

    def ingest_text_for_preferences(self, text: str, source: str = "conversation") -> List[Dict[str, Any]]:
        return [pref.to_dict() for pref in self.preferences.ingest_text(text, source)]

    def _query_manager(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for method_name, kind in [("query_episodic", "episodic"), ("query_semantic", "semantic")]:
            method = getattr(self.memory_manager, method_name, None)
            if not method:
                continue
            try:
                result = method(query, n_results=n_results)
                docs = (result or {}).get("documents", [[]])[0] if isinstance(result, dict) else []
                metas = (result or {}).get("metadatas", [[]])[0] if isinstance(result, dict) else []
                ids = (result or {}).get("ids", [[]])[0] if isinstance(result, dict) else []
                for idx, doc in enumerate(docs):
                    output.append({
                        "id": ids[idx] if idx < len(ids) else "",
                        "kind": kind,
                        "document": doc,
                        "metadata": metas[idx] if idx < len(metas) else {},
                    })
            except Exception:
                continue
        return output
