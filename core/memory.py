import uuid
import time
from pathlib import Path
from chromadb import PersistentClient, EphemeralClient
from core.logger import logger

# Global client instance to avoid ChromaDB singleton conflicts
_ephemeral_client = None


class MemoryManager:
    def __init__(
        self, 
        name: str = "farz-home-memory", 
        persist_directory: str | None = "./chroma_db",
        auto_cleanup: bool = True
    ) -> None:
        global _ephemeral_client
        
        try:
            # Ephemeral mode (testing) - single shared client
            if persist_directory is None:
                if _ephemeral_client is None:
                    _ephemeral_client = EphemeralClient()
                self.chroma_client = _ephemeral_client
            else:
                # Persistent mode (production)
                persist_path = Path(persist_directory)
                persist_path.mkdir(parents=True, exist_ok=True)
                self.chroma_client = PersistentClient(path=str(persist_path))
            
            self.collection = self.chroma_client.get_or_create_collection(name=name)
            self.last_cleanup = time.time()
            
            # Auto-cleanup on initialization if enabled (skip for tests)
            if auto_cleanup:
                self._auto_cleanup()
            
            logger.info("Memory initialized", collection=name, persist_dir=persist_directory)
        except Exception as e:
            logger.error("Memory init failed", error=str(e))
            raise

    def store(self, text: str, metadata: dict) -> None:
        """Store a memory with text and metadata."""
        try:
            # Add timestamp to metadata if not present
            if "timestamp" not in metadata:
                metadata["timestamp"] = time.time()
            
            # ChromaDB doesn't support lists in metadata - convert to strings
            cleaned_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, list):
                    # Convert list to comma-separated string
                    cleaned_metadata[key] = ",".join(str(v) for v in value) if value else ""
                elif value is None:
                    # Convert None to empty string
                    cleaned_metadata[key] = ""
                else:
                    cleaned_metadata[key] = value
            
            memory_id = str(uuid.uuid4())
            self.collection.upsert(
                ids=[memory_id], 
                documents=[text], 
                metadatas=[cleaned_metadata]
            )
            logger.debug("Memory stored", id=memory_id[:8], text=text[:50])
        except Exception as e:
            logger.error("Memory store failed", error=str(e), text=text[:50])

    def retrieve(self, query: str, n: int = 3) -> dict:
        """Retrieve top N relevant memories."""
        try:
            result = self.collection.query(query_texts=[query], n_results=n)
            
            # Extract documents from nested list format: [[doc1, doc2]]
            documents = result.get('documents', [[]])[0] if result else []
            metadatas = result.get('metadatas', [[]])[0] if result else []
            
            logger.debug("Memory retrieved", query=query[:30], count=len(documents))
            return {
                "documents": documents,
                "metadatas": metadatas
            }
        except Exception as e:
            logger.error("Memory retrieve failed", error=str(e), query=query[:30])
            return {"documents": [], "metadatas": []}

    def cleanup_old_memories(self, days: int = 7) -> int:
        """Delete memories older than specified days."""
        try:
            cutoff_timestamp = time.time() - (days * 24 * 60 * 60)
            
            # Get all items
            all_items = self.collection.get()
            
            # Filter old items
            old_ids = []
            if all_items and all_items.get('metadatas'):
                for i, metadata in enumerate(all_items['metadatas']):
                    if metadata.get('timestamp', float('inf')) < cutoff_timestamp:
                        old_ids.append(all_items['ids'][i])
            
            if old_ids:
                self.collection.delete(ids=old_ids)
                logger.info("Memory cleanup complete", deleted=len(old_ids), days=days)
                return len(old_ids)
            else:
                logger.debug("Memory cleanup: no old items", days=days)
                return 0
        except Exception as e:
            logger.error("Memory cleanup failed", error=str(e))
            return 0

    def _auto_cleanup(self) -> None:
        """Auto-cleanup if 7+ days since last cleanup."""
        try:
            # Check if cleanup metadata exists
            cleanup_meta = self.collection.get(where={"type": "cleanup_marker"})
            
            should_cleanup = True
            if cleanup_meta and cleanup_meta.get('metadatas'):
                last_cleanup_time = cleanup_meta['metadatas'][0].get('timestamp', 0)
                days_since_cleanup = (time.time() - last_cleanup_time) / (24 * 60 * 60)
                should_cleanup = days_since_cleanup >= 7
            
            if should_cleanup:
                deleted = self.cleanup_old_memories(days=7)
                # Store cleanup marker
                self.collection.upsert(
                    ids=["cleanup_marker"],
                    documents=["Last cleanup timestamp"],
                    metadatas=[{"type": "cleanup_marker", "timestamp": time.time()}]
                )
                if deleted > 0:
                    logger.info("Auto-cleanup triggered", deleted=deleted)
        except Exception as e:
            logger.debug("Auto-cleanup skipped", error=str(e))

    def get_all_memories(self, limit: int = 100, skip: int = 0) -> dict:
        """Get all memories with pagination."""
        try:
            all_items = self.collection.get()
            
            if not all_items or not all_items.get('documents'):
                return {"memories": [], "total": 0}
            
            # Filter out cleanup marker
            memories = []
            for i, doc in enumerate(all_items['documents']):
                metadata = all_items['metadatas'][i] if all_items.get('metadatas') else {}
                mem_type = metadata.get('type', 'unknown')
                
                if mem_type != 'cleanup_marker':
                    memories.append({
                        "id": all_items['ids'][i],
                        "text": doc,
                        "metadata": metadata
                    })
            
            # Apply pagination
            total = len(memories)
            paginated = memories[skip:skip + limit]
            
            return {
                "memories": paginated,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        except Exception as e:
            logger.error("Get all memories failed", error=str(e))
            return {"memories": [], "total": 0}
