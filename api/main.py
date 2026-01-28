import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine import SimulationEngine
from core.physics import PhysicsEngine
from core.intelligence import Intelligence
from core.plugins import PluginLoader
from core.logger import logger
from api.routers.v1 import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize engine and run in background."""
    from core.models import WorldState

    world_state = WorldState()
    phy_engine = PhysicsEngine(physics_data=[])
    intelligence = Intelligence(cooldown_seconds=30)

    plugin_loader = PluginLoader()
    plugin_loader.load_from_directory(
        directory_path=str(Path(__file__).parent.parent / "plugins")
    )
    plugin_loader.initialize_all(intelligence.dispatcher, phy_engine)
    plugin_loader.call_startup_hooks(world_state)

    sim_engine = SimulationEngine(step=1.0)

    app.state.world_state = world_state
    app.state.engine = sim_engine
    app.state.plugin_loader = plugin_loader

    engine_task = asyncio.create_task(
        sim_engine.run_loop_async(
            world_state=world_state,
            physics_fn=phy_engine.apply_physics,
            decision_fn=intelligence.make_decision_async,
            action_fn=intelligence.apply_action,
            plugin_tick_fn=plugin_loader.call_tick_hooks,
            log_fn=None,
        )
    )

    logger.info("Engine started", message="Engine running in background")

    yield

    sim_engine.stop()
    await engine_task
    logger.info("Engine stopped")


app = FastAPI(
    title="Farz Home API",
    version="1.0.0",
    description="Autonomous home automation engine with LLM intelligence",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api")
