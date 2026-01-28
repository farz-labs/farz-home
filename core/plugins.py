import sys
import inspect
import pkgutil

from pathlib import Path
from importlib import import_module

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from core.logger import logger

if TYPE_CHECKING:
    from core.actions import Dispatcher
    from core.physics import PhysicsEngine
    from core.models import WorldState


class BasePlugin(ABC):
    """
    Abstract base class for all system plugins.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique identifier for the plugin."""
        pass

    @abstractmethod
    def register_actions(self, dispatcher: "Dispatcher") -> None:
        """Register custom action handlers to the dispatcher."""
        pass

    @abstractmethod
    def register_physics(self, physics_engine: "PhysicsEngine") -> None:
        """Programmatically add physics rules using physics_engine.add_physics_rule(Physics(...))."""
        pass

    def on_startup(self, state: "WorldState") -> None:
        """
        Optional hook called when the simulation starts.
        Default implementation does nothing.
        """
        pass

    async def on_tick(self, state: "WorldState", tick: int) -> None:
        """
        Optional hook called every engine tick.
        Plugins can use this for continuous state synchronization.
        Default implementation does nothing.
        """
        pass


class PluginLoader:
    def __init__(self):
        self.plugins: list[BasePlugin] = []

    def load_from_directory(self, directory_path: str):
        """
        Loads plugins from a file system path.
        Example: loader.load_from_directory("plugins")
        """
        path = Path(directory_path).resolve()

        if str(path.parent) not in sys.path:
            sys.path.insert(0, str(path.parent))

        package_name = path.name

        for _, module_name, is_pkg in pkgutil.iter_modules([str(path)]):
            full_module_path = f"{package_name}.{module_name}"

            try:
                module = import_module(full_module_path)

                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        try:
                            plugin_instance = obj()
                            self.plugins.append(plugin_instance)
                            logger.info(
                                "Plugin loaded",
                                name=plugin_instance.name,
                                module=full_module_path,
                            )
                        except Exception as e:
                            logger.error(
                                "Plugin instantiation failed",
                                class_name=obj.__name__,
                                error=str(e),
                            )

            except ImportError as e:
                logger.error(
                    "Plugin import failed",
                    module=full_module_path,
                    error=str(e),
                )
            except Exception as e:
                logger.error(
                    "Plugin load failed",
                    module=full_module_path,
                    error=str(e),
                )

    def initialize_all(self, dispatcher, physics_engine):
        """Standardizes the setup flow for all discovered plugins."""
        for plugin in self.plugins:
            try:
                plugin.register_actions(dispatcher)
                plugin.register_physics(physics_engine)
            except Exception as e:
                logger.error(
                    "Plugin registration failed",
                    name=plugin.name,
                    error=str(e),
                )

        logger.info(
            "Plugins initialized",
            count=len(self.plugins),
            names=[p.name for p in self.plugins],
        )

    def call_startup_hooks(self, state: "WorldState") -> None:
        """Call on_startup for all loaded plugins."""
        for plugin in self.plugins:
            try:
                plugin.on_startup(state)
            except Exception as e:
                logger.error(
                    "Plugin startup failed",
                    name=plugin.name,
                    error=str(e),
                )

    async def call_tick_hooks(self, state: "WorldState", tick: int) -> None:
        """Call on_tick for all loaded plugins."""
        for plugin in self.plugins:
            try:
                await plugin.on_tick(state, tick)
            except Exception as e:
                logger.error(
                    "Plugin tick failed",
                    name=plugin.name,
                    error=str(e),
                )

    def get_all_plugins(self) -> list[BasePlugin]:
        """Return all loaded plugin instances."""
        return self.plugins
