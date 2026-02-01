import time
import uuid
from core.memory import MemoryManager
import pytest


@pytest.fixture
def unique_collection():
    """Generate unique collection name for each test."""
    return f"test-{uuid.uuid4()}"


def test_memory_store_and_retrieve(unique_collection):
    """Test basic store and retrieve functionality."""
    # Use ephemeral mode (no persistence) for tests
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    
    # Store a memory
    test_text = "User prefers warm lighting in the evening"
    test_metadata = {"type": "preference", "time": "evening", "category": "lighting"}
    
    memory.store(test_text, test_metadata)
    
    # Retrieve it
    results = memory.retrieve("lighting preferences evening", n=1)
    
    assert len(results["documents"]) > 0
    assert "warm lighting" in results["documents"][0]
    assert results["metadatas"][0]["type"] == "preference"


def test_memory_persistence(unique_collection):
    """Test that memories persist within same collection."""
    # Use ephemeral mode - testing persistence within session
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    memory.store("Test persistent memory", {"type": "test"})
    
    # Retrieve the stored memory
    results = memory.retrieve("persistent memory", n=1)
    
    assert len(results["documents"]) > 0
    assert "persistent" in results["documents"][0]


def test_memory_cleanup(unique_collection):
    """Test weekly cleanup functionality."""
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    
    # Store old memory (8 days ago)
    old_timestamp = time.time() - (8 * 24 * 60 * 60)
    memory.store("Old memory to delete", {"timestamp": old_timestamp, "type": "old"})
    
    # Store recent memory
    memory.store("Recent memory to keep", {"type": "recent"})
    
    # Run cleanup for 7 days
    deleted_count = memory.cleanup_old_memories(days=7)
    
    # Should have deleted 1 old memory
    assert deleted_count == 1
    
    # Verify recent memory still exists
    results = memory.retrieve("recent memory", n=5)
    assert len(results["documents"]) > 0
    assert any("Recent" in doc for doc in results["documents"])


def test_acceptance_criteria_blue_light(unique_collection):
    """Test acceptance criteria: User hates blue light in morning."""
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    
    # Store the constraint
    memory.store(
        "User hates blue light in the morning",
        {"type": "preference", "context": "morning", "category": "lighting"}
    )
    
    # Query with morning scene context
    results = memory.retrieve("Setting morning scene", n=3)
    
    # Should retrieve the blue light constraint
    assert len(results["documents"]) > 0
    
    found_constraint = False
    for doc in results["documents"]:
        if "blue light" in doc.lower() and "morning" in doc.lower():
            found_constraint = True
            break
    
    assert found_constraint, "Should find the blue light constraint when querying morning scene"


def test_get_all_memories_pagination(unique_collection):
    """Test pagination in get_all_memories."""
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    
    # Store multiple memories
    for i in range(15):
        memory.store(f"Memory number {i}", {"index": i, "type": "test"})
    
    # Get first page (10 items)
    page1 = memory.get_all_memories(limit=10, skip=0)
    assert len(page1["memories"]) == 10
    assert page1["total"] == 15
    
    # Get second page (5 items)
    page2 = memory.get_all_memories(limit=10, skip=10)
    assert len(page2["memories"]) == 5
    assert page2["total"] == 15


def test_memory_empty_collection(unique_collection):
    """Test behavior with empty collection."""
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    
    # Query empty collection
    results = memory.retrieve("anything", n=5)
    
    # Filter out cleanup marker if present
    actual_docs = [doc for doc in results["documents"] if "cleanup" not in doc.lower()]
    assert len(actual_docs) == 0
    assert results["metadatas"] == []
    
    # Get all from empty collection
    all_results = memory.get_all_memories()
    assert all_results["total"] == 0
    assert all_results["memories"] == []


def test_memory_error_handling(unique_collection):
    """Test error handling in memory operations."""
    memory = MemoryManager(name=unique_collection, persist_directory=None, auto_cleanup=False)
    
    # Store with missing metadata fields (should still work)
    memory.store("Test without timestamp", {"type": "test"})
    
    # Should auto-add timestamp
    results = memory.retrieve("test without", n=1)
    assert len(results["documents"]) > 0
    assert len(results["metadatas"]) > 0
    assert "timestamp" in results["metadatas"][0]
