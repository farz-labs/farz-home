import uuid

from enum import Enum
from typing import Callable

from core.logger import log_with_tui
from core.models import WorldState, Decision


class ActionType(Enum):
    SET_ATTRIBUTE = "SET_ATTRIBUTE"
    TOGGLE_STATE = "TOGGLE_STATE"


class Dispatcher:
    _instance = None

    def __init__(self):
        self._registry: dict[str, Callable] = {}

        # Register standard library
        self.register(ActionType.SET_ATTRIBUTE.value, self.action_set_attribute)
        self.register(ActionType.TOGGLE_STATE.value, self.action_toggle_state)

    @classmethod
    def get_instance(cls) -> "Dispatcher":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, action_name: str, func: Callable):
        self._registry[action_name] = func

    def dispatch(self, world: WorldState, decision: Decision):
        action_func = self._registry.get(decision.action)

        if action_func:
            try:
                log_with_tui(
                    "info",
                    "dispatch_start",
                    action=decision.action,
                    target_id=str(decision.target_entity_id),
                )
                action_func(world, decision.target_entity_id, decision.params)
                log_with_tui(
                    "info",
                    "dispatch_complete",
                    action=decision.action,
                )
            except Exception as e:
                log_with_tui(
                    "error",
                    "dispatch_failed",
                    action=decision.action,
                    error=str(e),
                )
        else:
            log_with_tui(
                "warning",
                "unknown_action_attempted",
                action=decision.action,
            )

    def action_set_attribute(
        self, world: WorldState, target_id: uuid.UUID, params: dict
    ):
        key = params.get("attribute")
        value = params.get("value")

        if key is None or value is None:
            log_with_tui(
                "error",
                "missing_parameters",
                target_id=str(target_id),
                params=str(params),
            )
            return

        try:
            world.set_attribute_value(target_id, key, value)
            log_with_tui(
                "info",
                "attribute_set_success",
                target_id=str(target_id),
                attribute=key,
                value=value,
            )
        except KeyError:
            log_with_tui(
                "error",
                "entity_not_found",
                target_id=str(target_id),
            )
        except Exception as e:
            log_with_tui(
                "error",
                "attribute_set_failed",
                target_id=str(target_id),
                error=str(e),
            )

    def action_toggle_state(
        self, world: WorldState, target_id: uuid.UUID, params: dict
    ):
        key = params.get("attribute")

        try:
            current_val = world.get_attribute_value(target_id, key)

            if isinstance(current_val, bool):
                new_val = not current_val
                world.set_attribute_value(target_id, key, new_val)
                log_with_tui(
                    "info",
                    "toggle_success",
                    target_id=str(target_id),
                    attribute=key,
                    old_value=current_val,
                    new_value=new_val,
                )
            else:
                log_with_tui(
                    "error",
                    "invalid_attribute_type",
                    target_id=str(target_id),
                    attribute=key,
                    current_type=type(current_val).__name__,
                )
        except KeyError:
            log_with_tui(
                "error",
                "entity_not_found",
                target_id=str(target_id),
            )
        except Exception as e:
            log_with_tui(
                "error",
                "toggle_failed",
                target_id=str(target_id),
                error=str(e),
            )
