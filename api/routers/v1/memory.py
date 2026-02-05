import time
from fastapi import APIRouter, HTTPException, Request

from core.models import PreferenceRequest, CleanupRequest, CorrectionRequest
from core.intelligence import Intelligence

router = APIRouter()


@router.get("/")
async def get_all_memories(request: Request, skip: int = 0, limit: int = 100):
    """Get all stored memories with pagination."""
    try:
        # Access memory manager through intelligence
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "memory"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        result = intelligence.memory.get_all_memories(limit=limit, skip=skip)

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
        if not intelligence or not hasattr(intelligence, "memory"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        # Build metadata
        metadata = {
            "timestamp": time.time(),
            "type": "preference",
            "tags": preference.tags,
            "context": preference.context,
        }

        # Store the preference
        intelligence.memory.store(preference.text, metadata)

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
        if not intelligence or not hasattr(intelligence, "memory"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        deleted_count = intelligence.memory.cleanup_old_memories(
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


@router.post("/correction")
async def store_correction(request: Request, correction: CorrectionRequest):
    """Manually store a user correction without auto-detection."""
    try:
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "memory"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        # Build metadata
        metadata = {
            "timestamp": time.time(),
            "type": "correction",
            "entity_id": correction.entity_id,
            "action_description": correction.action_description,
            "manual": True,  # Flag as manually submitted
            "context": correction.context,
        }

        # Store the correction lesson
        intelligence.memory.store(correction.lesson, metadata)

        return {
            "status": "success",
            "message": "Correction stored successfully",
            "lesson": correction.lesson,
            "metadata": metadata,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to store correction: {str(e)}"
        )


@router.get("/stats")
async def get_memory_stats(request: Request):
    """Get statistics about stored memories."""
    try:
        intelligence: Intelligence = request.app.state.intelligence
        if not intelligence or not hasattr(intelligence, "memory"):
            raise HTTPException(status_code=503, detail="Intelligence not available")

        all_memories = intelligence.memory.get_all_memories(limit=10000)

        # Calculate stats
        total = all_memories["total"]

        # Count by type
        type_counts = {}
        success_count = 0
        failed_count = 0
        total_corrections = 0
        corrections_by_entity = {}
        corrections_by_action = {}
        total_correction_time = 0

        for memory in all_memories["memories"]:
            metadata = memory.get("metadata", {})
            mem_type = metadata.get("type", "action")
            type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

            if metadata.get("success") is True:
                success_count += 1
            elif metadata.get("success") is False:
                failed_count += 1

            # Track correction-specific stats
            if mem_type == "correction":
                total_corrections += 1

                entity_name = metadata.get("entity_name", "unknown")
                corrections_by_entity[entity_name] = (
                    corrections_by_entity.get(entity_name, 0) + 1
                )

                action = metadata.get("action", "unknown")
                corrections_by_action[action] = corrections_by_action.get(action, 0) + 1

                elapsed = metadata.get("elapsed_seconds", 0)
                if elapsed:
                    total_correction_time += elapsed

        avg_correction_time = (
            (total_correction_time / total_corrections) if total_corrections > 0 else 0
        )

        return {
            "total_memories": total,
            "by_type": type_counts,
            "successful_actions": success_count,
            "failed_actions": failed_count,
            "corrections": {
                "total": total_corrections,
                "by_entity": corrections_by_entity,
                "by_action": corrections_by_action,
                "average_time_to_correction_seconds": round(avg_correction_time, 1),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
