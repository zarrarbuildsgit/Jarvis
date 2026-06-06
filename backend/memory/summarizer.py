"""Dependency-free memory summarization helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List
import re


class MemorySummarizer:
    def summarize_texts(self, texts: Iterable[str], max_items: int = 8, max_chars: int = 900) -> str:
        cleaned: list[str] = []
        for text in texts:
            text = " ".join(str(text).split())
            if text and text not in cleaned:
                cleaned.append(text)
        if not cleaned:
            return "No relevant memories."
        bullets = []
        for text in cleaned[:max_items]:
            bullets.append("- " + self._shorten(text, max_chars // max(1, max_items)))
        return "Relevant memory summary:\n" + "\n".join(bullets)

    def summarize_memories(self, memories: Iterable[Dict[str, Any]], max_items: int = 8) -> str:
        texts = []
        for mem in memories:
            texts.append(str(mem.get("document") or mem.get("text") or mem.get("fact") or mem.get("metadata", {}).get("fact") or ""))
        return self.summarize_texts(texts, max_items=max_items)

    def summarize_conversation(self, turns: Iterable[Dict[str, Any]], max_turns: int = 8) -> str:
        lines: list[str] = []
        for turn in list(turns)[-max_turns:]:
            speaker = turn.get("speaker", "unknown")
            text = self._shorten(str(turn.get("text", "")), 140)
            if text:
                lines.append(f"{speaker}: {text}")
        return "Recent conversation:\n" + "\n".join(lines) if lines else ""

    def _shorten(self, text: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."
