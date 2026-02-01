import asyncio
import time
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
from core.feedback import CorrectionDetector, LessonGenerator
from core.logger import logger
from api.routers.v1 import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize engine and run in background."""
    from core.models import WorldState

    world_state = WorldState()
    phy_engine = PhysicsEngine(physics_data=[])
    intelligence = Intelligence(cooldown_seconds=30)
    correction_detector = CorrectionDetector(correction_window=300)
    lesson_generator = LessonGenerator()

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
    app.state.intelligence = intelligence
    app.state.correction_detector = correction_detector
    app.state.lesson_generator = lesson_generator

    # Create correction detection function
    async def detect_and_learn(state, tick):
        """Detect user corrections and generate lessons."""
        try:
            recent_actions = intelligence.get_recent_actions(within_seconds=300)
            if not recent_actions:
                return

            corrections = correction_detector.detect_contradictions(
                state, recent_actions
            )

            for correction in corrections:
                # Generate lesson
                lesson = lesson_generator.generate_lesson(correction, state)

                if lesson:
                    # Store lesson in memory
                    metadata = {
                        "timestamp": time.time(),
                        "type": "correction",
                        "action": correction.action.action,
                        "entity_id": correction.entity_id,
                        "entity_name": correction.entity_name,
                        "elapsed_seconds": correction.time_elapsed,
                        "confidence": correction.confidence,
                    }

                    intelligence.instructor.memory.store(lesson, metadata)
                    logger.info(
                        "Correction lesson stored",
                        entity=correction.entity_name,
                        lesson=lesson[:80],
                    )

                    # Remove this action from tracking to avoid duplicate detections
                    intelligence.recent_actions = [
                        a
                        for a in intelligence.recent_actions
                        if a["entity_id"] != correction.action.target_entity_id
                        or a["timestamp"] != correction.action
                    ]
        except Exception as e:
            logger.error("Correction detection failed", error=str(e))

    # Wrap plugin tick function to include correction detection
    original_tick_fn = plugin_loader.call_tick_hooks

    async def combined_tick_fn(state, tick):
        await original_tick_fn(state, tick)
        await detect_and_learn(state, tick)

    engine_task = asyncio.create_task(
        sim_engine.run_loop_async(
            world_state=world_state,
            physics_fn=phy_engine.apply_physics,
            decision_fn=intelligence.make_decision_async,
            action_fn=intelligence.apply_action,
            plugin_tick_fn=combined_tick_fn,
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
