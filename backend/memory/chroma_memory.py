"""
JARVIS Memory Manager
Episodic + Semantic Memory using ChromaDB
"""

import chromadb
from chromadb.config import Settings
from datetime import datetime
from pathlib import Path
import json
from loguru import logger

class MemoryManager:
    def __init__(self, persist_directory: str = "data/memory"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.episodic = self.client.get_or_create_collection(
            name="episodic_memory",
            metadata={"hnsw:space": "cosine"}
        )
        self.semantic = self.client.get_or_create_collection(
            name="semantic_memory",
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info("MemoryManager initialized with ChromaDB")
    
    def add_episodic(self, action: str, outcome: str, context: str = "", metadata: dict = None):
        """Add episodic memory (specific event/action)"""
        entry = {
            "type": "episodic",
            "action": action,
            "outcome": outcome,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        }
        
        doc_id = f"epi_{datetime.now().timestamp()}_{hash(action) % 10000}"
        self.episodic.add(
            documents=[f"{action} {outcome} {context}"],
            metadatas=[entry],
            ids=[doc_id]
        )
        logger.debug(f"Episodic memory added: {action}")
    
    def add_semantic(self, fact: str, category: str = "general", metadata: dict = None):
        """Add semantic memory (general knowledge/fact)"""
        entry = {
            "type": "semantic",
            "fact": fact,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        }
        
        doc_id = f"sem_{datetime.now().timestamp()}_{hash(fact) % 10000}"
        self.semantic.add(
            documents=[fact],
            metadatas=[entry],
            ids=[doc_id]
        )
        logger.debug(f"Semantic memory added: {fact}")
    
    def query_episodic(self, query: str, n_results: int = 5):
        """Find similar past actions/events"""
        return self.episodic.query(query_texts=[query], n_results=n_results)
    
    def query_semantic(self, query: str, n_results: int = 5):
        """Find relevant knowledge/facts"""
        return self.semantic.query(query_texts=[query], n_results=n_results)
    
    def get_stats(self):
        return {
            "episodic": self.episodic.count(),
            "semantic": self.semantic.count(),
            "total_entries": self.episodic.count() + self.semantic.count()
        }
    
    def export_memories(self, filepath: str):
        """Export memories to JSON"""
        data = {"episodic": [], "semantic": [], "exported_at": datetime.now().isoformat()}
        
        epi = self.episodic.get()
        for i, doc in enumerate(epi["documents"]):
            data["episodic"].append({
                "document": doc,
                "metadata": epi["metadatas"][i] if epi["metadatas"] else {}
            })
        
        sem = self.semantic.get()
        for i, doc in enumerate(sem["documents"]):
            data["semantic"].append({
                "document": doc,
                "metadata": sem["metadatas"][i] if sem["metadatas"] else {}
            })
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Memories exported to {filepath}")
        return filepath
