import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.intelligence import Intelligence

router = APIRouter()


class PreferenceRequest(BaseModel):
    text: str
    tags: list[str] = []
    context: str = ""


class CleanupRequest(BaseModel):
    days: int = 7


@router.get("/")
async def get_all_memories(request: Request, skip: int = 0, limit: int = 100):
    """Get all stored memories with pagination."""
    try:
        # Access memory manager through intelligence
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "instructor"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        result = intelligence.instructor.memory.get_all_memories(limit=limit, skip=skip)

        return {
            "memories": result["memories"],
            "total": result["total"],
            "skip": skip,
            "limit": limit,
            "has_more": result["total"] > (skip + limit),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch memories: {str(e)}"
        )


@router.post("/preference")
async def store_preference(request: Request, preference: PreferenceRequest):
    """Store a user preference or constraint in memory."""
    try:
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "instructor"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        # Build metadata
        metadata = {
            "timestamp": time.time(),
            "type": "preference",
            "tags": preference.tags,
            "context": preference.context,
        }

        # Store the preference
        intelligence.instructor.memory.store(preference.text, metadata)

        return {
            "status": "success",
            "message": "Preference stored successfully",
            "text": preference.text,
            "metadata": metadata,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to store preference: {str(e)}"
        )


@router.delete("/cleanup")
async def cleanup_memories(request: Request, cleanup_req: CleanupRequest):
    """Manually trigger memory cleanup."""
    try:
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "instructor"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        deleted_count = intelligence.instructor.memory.cleanup_old_memories(
            days=cleanup_req.days
        )

        return {
            "status": "success",
            "deleted": deleted_count,
            "days": cleanup_req.days,
            "message": f"Deleted {deleted_count} memories older than {cleanup_req.days} days",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/stats")
async def get_memory_stats(request: Request):
    """Get statistics about stored memories."""
    try:
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "instructor"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        all_memories = intelligence.instructor.memory.get_all_memories(limit=10000)

        # Calculate stats
        total = all_memories["total"]

        # Count by type
        type_counts = {}
        success_count = 0
        failed_count = 0

        for memory in all_memories["memories"]:
            metadata = memory.get("metadata", {})
            mem_type = metadata.get("type", "action")
            type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

            if metadata.get("success") is True:
                success_count += 1
            elif metadata.get("success") is False:
                failed_count += 1

        return {
            "total_memories": total,
            "by_type": type_counts,
            "successful_actions": success_count,
            "failed_actions": failed_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
