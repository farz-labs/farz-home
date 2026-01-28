import uuid

from enum import Enum
from typing import Callable

from core.logger import logger
from core.models import WorldState, Decision, DecisionParams


class ActionType(Enum):
    SET_ATTRIBUTE = "SET_ATTRIBUTE"
    TOGGLE_STATE = "TOGGLE_STATE"
    INCREMENT_VALUE = "INCREMENT_VALUE"
    DECREMENT_VALUE = "DECREMENT_VALUE"


class Dispatcher:
    _instance = None

    def __init__(self):
        self._registry: dict[str, Callable] = {}

        self.register(ActionType.SET_ATTRIBUTE.value, self.action_set_attribute)
        self.register(ActionType.TOGGLE_STATE.value, self.action_toggle_state)
        self.register(ActionType.INCREMENT_VALUE.value, self.action_increment_value)
        self.register(ActionType.DECREMENT_VALUE.value, self.action_decrement_value)

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
                logger.info(
                    "Dispatch start",
                    action=decision.action,
                    target_id=str(decision.target_entity_id),
                )
                action_func(world, decision.target_entity_id, decision.params)
                logger.info(
                    "Dispatch complete",
                    action=decision.action,
                )
            except Exception as e:
                logger.error(
                    "Dispatch failed",
                    action=decision.action,
                    error=str(e),
                )
        else:
            logger.warning(
                "Unknown action attempted",
                action=decision.action,
            )

    def _convert_string_to_type(
        self, value_str: str, target_type: type = None
    ) -> bool | float | int | str:
        """Convert string value to appropriate type."""
        if target_type is bool or value_str.lower() in ("true", "false", "on", "off"):
            return value_str.lower() in ("true", "on", "1", "yes")

        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str

    def action_set_attribute(
        self, world: WorldState, target_id: uuid.UUID, params: DecisionParams | dict
    ):
        if isinstance(params, DecisionParams):
            key = params.attribute_name
            value_str = params.target_value
        else:
            key = params.get("attribute") or params.get("attribute_name")
            value_str = params.get("value") or params.get("target_value")

        if key is None or value_str is None:
            logger.error(
                "Missing parameters",
                target_id=str(target_id),
                params=str(params),
            )
            return

        try:
            # Get current value to infer type
            try:
                current_val = world.get_attribute_value(target_id, key)
                target_type = type(current_val)
            except (KeyError, AttributeError):
                target_type = None

            # Convert string to appropriate type
            if isinstance(value_str, str):
                value = self._convert_string_to_type(value_str, target_type)
            else:
                value = value_str

            world.set_attribute_value(target_id, key, value)
            logger.info(
                "Attribute set success",
                target_id=str(target_id),
                attribute=key,
                value=value,
            )
        except KeyError:
            logger.error(
                "Entity not found",
                target_id=str(target_id),
            )
        except Exception as e:
            logger.error(
                "Attribute set failed",
                target_id=str(target_id),
                error=str(e),
            )

    def action_toggle_state(
        self, world: WorldState, target_id: uuid.UUID, params: DecisionParams | dict
    ):
        if isinstance(params, DecisionParams):
            key = params.attribute_name
        else:
            key = params.get("attribute") or params.get("attribute_name")

        # Common string state mappings
        STRING_STATE_PAIRS = {
            "OFF": "ON",
            "ON": "OFF",
            "LOCKED": "UNLOCKED",
            "UNLOCKED": "LOCKED",
            "CLOSED": "OPEN",
            "OPEN": "CLOSED",
            "IDLE": "ACTIVE",
            "ACTIVE": "IDLE",
            "SLEEP": "ON",
            "CLEAR": "DETECTED",
            "DETECTED": "CLEAR",
        }

        try:
            current_val = world.get_attribute_value(target_id, key)

            if isinstance(current_val, bool):
                new_val = not current_val
                world.set_attribute_value(target_id, key, new_val)
                logger.info(
                    "Toggle success",
                    target_id=str(target_id),
                    attribute=key,
                    old_value=current_val,
                    new_value=new_val,
                )
            elif isinstance(current_val, str) and current_val in STRING_STATE_PAIRS:
                new_val = STRING_STATE_PAIRS[current_val]
                world.set_attribute_value(target_id, key, new_val)
                logger.info(
                    "Toggle success",
                    target_id=str(target_id),
                    attribute=key,
                    old_value=current_val,
                    new_value=new_val,
                )
            else:
                logger.error(
                    "Invalid attribute type",
                    target_id=str(target_id),
                    attribute=key,
                    current_type=type(current_val).__name__,
                    current_value=str(current_val),
                    supported="bool or string pairs (ON/OFF, LOCKED/UNLOCKED, etc.)",
                )
        except KeyError:
            logger.error(
                "Entity not found",
                target_id=str(target_id),
            )
        except Exception as e:
            logger.error(
                "Toggle failed",
                target_id=str(target_id),
                error=str(e),
            )

    def action_increment_value(
        self, world: WorldState, target_id: uuid.UUID, params: DecisionParams | dict
    ):
        if isinstance(params, DecisionParams):
            key = params.attribute_name
            delta = params.delta or 1
        else:
            key = params.get("attribute") or params.get("attribute_name")
            delta = params.get("delta", 1)

        try:
            current_val = world.get_attribute_value(target_id, key)

            if isinstance(current_val, (int, float)):
                new_val = current_val + delta
                world.set_attribute_value(target_id, key, new_val)
                logger.info(
                    "Increment success",
                    target_id=str(target_id),
                    attribute=key,
                    delta=delta,
                    new_value=new_val,
                )
            else:
                logger.error(
                    "Invalid attribute type",
                    target_id=str(target_id),
                    attribute=key,
                    current_type=type(current_val).__name__,
                )
        except KeyError:
            logger.error(
                "Entity not found",
                target_id=str(target_id),
            )
        except Exception as e:
            logger.error(
                "Increment failed",
                target_id=str(target_id),
                error=str(e),
            )

    def action_decrement_value(
        self, world: WorldState, target_id: uuid.UUID, params: DecisionParams | dict
    ):
        if isinstance(params, DecisionParams):
            key = params.attribute_name
            delta = params.delta or 1
        else:
            key = params.get("attribute") or params.get("attribute_name")
            delta = params.get("delta", 1)

        try:
            current_val = world.get_attribute_value(target_id, key)

            if isinstance(current_val, (int, float)):
                new_val = current_val - delta
                world.set_attribute_value(target_id, key, new_val)
                logger.info(
                    "Decrement success",
                    target_id=str(target_id),
                    attribute=key,
                    delta=delta,
                    new_value=new_val,
                )
            else:
                logger.error(
                    "Invalid attribute type",
                    target_id=str(target_id),
                    attribute=key,
                    current_type=type(current_val).__name__,
                )
        except KeyError:
            logger.error(
                "Entity not found",
                target_id=str(target_id),
            )
        except Exception as e:
            logger.error(
                "Decrement failed",
                target_id=str(target_id),
                error=str(e),
            )
