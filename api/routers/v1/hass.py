import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ServiceCallRequest(BaseModel):
    entity_id: str
    service: str
    service_data: dict = {}


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.get("/state")
async def get_state(request: Request):
    """Get current world state."""
    world_state = request.app.state.world_state
    return world_state.to_dict()


@router.get("/entities")
async def get_entities(request: Request):
    """List all entities synced from Home Assistant."""
    world_state = request.app.state.world_state
    ha_entities = [
        {
            "id": str(entity.id),
            "name": entity.name,
            "tags": entity.tags,
            "attributes": entity.attributes,
        }
        for entity in world_state.entities.values()
        if "ha:" in ":".join(entity.tags)
    ]
    return {"entities": ha_entities, "count": len(ha_entities)}


@router.post("/call")
async def call_service(request: Request, service_call: ServiceCallRequest):
    """Proxy Home Assistant service call."""
    world_state = request.app.state.world_state

    entity_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, service_call.entity_id)
    entity = world_state.get_entity_by_id(entity_uuid)

    if not entity:
        raise HTTPException(
            status_code=404, detail=f"Entity {service_call.entity_id} not found"
        )

    from core.models import Decision, DecisionParams

    decision = Decision(
        action="HA_CALL_SERVICE",
        target_entity_id=entity_uuid,
        params=DecisionParams(
            attribute_name="service",
            target_value=service_call.service,
        ),
        reasoning="Manual API call",
    )

    decision.params = {
        "service": service_call.service,
        "service_data": service_call.service_data,
    }

    from core.intelligence import Intelligence

    intelligence = Intelligence()
    intelligence.execute_decision(world_state, decision)

    return {
        "status": "success",
        "entity_id": service_call.entity_id,
        "service": service_call.service,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time state updates with heartbeat."""
    await manager.connect(websocket)
    tick = 0

    try:
        while True:
            world_state = websocket.app.state.world_state
            state_dict = world_state.to_dict()
            
            # Send heartbeat message
            await websocket.send_json({
                "type": "heartbeat",
                "tick": tick,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Send state update message
            await websocket.send_json({
                "type": "state",
                "data": state_dict,
                "tick": tick
            })
            
            tick += 1
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
