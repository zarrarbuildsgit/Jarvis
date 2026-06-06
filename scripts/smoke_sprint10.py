"""Sprint 10 smoke checks.

Run with:
    uv run python scripts/smoke_sprint10.py

Validates scoring, preference extraction/storage, retrieval ranking, and summary
without requiring ChromaDB or model downloads.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.memory.preferences import PreferenceExtractor, PreferenceStore
from backend.memory.retriever import MemoryRetriever
from backend.memory.scoring import MemoryScorer
from backend.memory.summarizer import MemorySummarizer


class FakeMemoryManager:
    def query_episodic(self, query, n_results=5):
        return {
            "documents": [["User prefers Brave browser for research", "Opened Notepad yesterday"]],
            "metadatas": [[{"timestamp": "2099-01-01T00:00:00+00:00", "use_count": 4}, {"use_count": 1}]],
            "ids": [["e1", "e2"]],
        }

    def query_semantic(self, query, n_results=5):
        return {
            "documents": [["Default project folder is C:/Projects/Jarvis"]],
            "metadatas": [[{"importance": 0.9, "confidence": 0.9}]],
            "ids": [["s1"]],
        }


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    scorer = MemoryScorer()
    important = scorer.score_text("Always use Brave as my default browser", {"use_count": 5}, query="browser")
    smalltalk = scorer.score_text("thanks", {}, query="browser")
    assert_true(important.final > smalltalk.final, "important memory outranks smalltalk")
    enriched = scorer.enrich_metadata("I prefer VS Code", {})
    assert_true("memory_score" in enriched and isinstance(enriched["score_reasons"], str), "metadata enriched safely")

    extractor = PreferenceExtractor()
    prefs = extractor.extract("I prefer Brave and call me Zarrar", source="smoke")
    keys = {p.key for p in prefs}
    assert_true("preferred_browser" in keys and "preferred_name" in keys, "preferences extracted")

    with TemporaryDirectory() as tmp:
        store = PreferenceStore(str(Path(tmp) / "prefs.json"))
        saved = store.ingest_text("I prefer Chrome", source="smoke")
        assert_true(saved and store.get("preferred_browser").value == "chrome", "preference stored/retrieved")
        context = store.as_context()
        assert_true("preferred_browser" in context, "preference context")

        retriever = MemoryRetriever(FakeMemoryManager(), preference_store=store)
        result = retriever.retrieve("browser project", n_results=3)
        assert_true(result["memories"], "memories retrieved")
        assert_true(result["memories"][0]["score"]["final"] >= result["memories"][-1]["score"]["final"], "memories ranked")
        assert_true("Known user preferences" in result["preference_context"], "retriever includes preferences")
        assert_true("Relevant memory summary" in result["summary"], "summary generated")

    summary = MemorySummarizer().summarize_texts(["one", "two", "one"])
    assert_true(summary.count("- one") == 1, "summary deduplicates")

    print("✅ Sprint 10 smoke checks passed")


if __name__ == "__main__":
    main()
