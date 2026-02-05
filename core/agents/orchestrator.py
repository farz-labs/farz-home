"""ActionOrchestrator agent - translates high-level intents into properly formatted HA service calls."""

from pydantic import BaseModel

from core.models import WorldState, Decision, DecisionParams
from core.logger import logger


class ActionIntent(BaseModel):
    """High-level action intent from specialist agents."""

    entity_name: str  # e.g., "Living Room Light"
    intent: str  # e.g., "turn_on", "turn_off", "lock", "set_temperature_22"
    reasoning: str


class ActionOrchestrator:
    """
    Translates high-level action intents into properly formatted Decision objects.
    Knows all Home Assistant services and their required parameters.
    """

    # Map of common HA services and their requirements
    HA_SERVICES = {
        # Lights and switches
        "turn_on": {"domains": ["light", "switch", "fan", "media_player"], "params": {}},
        "turn_off": {"domains": ["light", "switch", "fan", "media_player"], "params": {}},
        "toggle": {"domains": ["light", "switch", "input_boolean"], "params": {}},
        # Climate
        "set_temperature": {
            "domains": ["climate"],
            "params": {"temperature": "required"},
        },
        "set_hvac_mode": {
            "domains": ["climate"],
            "params": {"hvac_mode": "required"},  # heat, cool, auto, off
        },
        # Locks
        "lock": {"domains": ["lock"], "params": {}},
        "unlock": {"domains": ["lock"], "params": {}},
        # Covers
        "open_cover": {"domains": ["cover"], "params": {}},
        "close_cover": {"domains": ["cover"], "params": {}},
        "set_cover_position": {"domains": ["cover"], "params": {"position": "required"}},
        # Media
        "media_play": {"domains": ["media_player"], "params": {}},
        "media_pause": {"domains": ["media_player"], "params": {}},
        "volume_set": {
            "domains": ["media_player"],
            "params": {"volume_level": "required"},
        },
    }

    def __init__(self):
        pass

    def format_decision(
        self, intent: ActionIntent, world_state: WorldState
    ) -> Decision | None:
        """
        Convert high-level intent into properly formatted Decision.

        Args:
            intent: ActionIntent with entity_name and intent
            world_state: Current state to lookup entity UUID

        Returns:
            Decision object or None if invalid
        """
        # Find entity by name
        entity = None
        for e in world_state.entities.values():
            if e.name.lower() == intent.entity_name.lower():
                entity = e
                break

        if not entity:
            logger.error(
                f"[ActionOrchestrator] Entity not found: {intent.entity_name}"
            )
            return None

        ha_entity_id = entity.attributes.get("ha_entity_id", "")
        if not ha_entity_id:
            logger.error(
                f"[ActionOrchestrator] No ha_entity_id for {intent.entity_name}"
            )
            return None

        domain = ha_entity_id.split(".")[0]

        # Parse intent (may include parameters like "set_temperature_22")
        service, service_data = self._parse_intent(intent.intent, domain)

        if not service:
            logger.error(f"[ActionOrchestrator] Unknown service: {intent.intent}")
            return None

        # Validate service is appropriate for domain
        service_info = self.HA_SERVICES.get(service)
        if service_info and domain not in service_info["domains"]:
            logger.error(
                f"[ActionOrchestrator] Service {service} not valid for domain {domain}"
            )
            return None

        # Build Decision
        params = DecisionParams(service=service, service_data=service_data)

        decision = Decision(
            action="HA_CALL_SERVICE",
            target_entity_id=entity.id,
            params=params,
            reasoning=intent.reasoning,
        )

        logger.info(
            "[ActionOrchestrator] Formatted decision",
            entity=intent.entity_name,
            service=service,
            data=service_data,
        )

        return decision

    def _parse_intent(self, intent: str, domain: str) -> tuple[str, dict]:
        """
        Parse intent string into service name and parameters.

        Examples:
            "turn_on" -> ("turn_on", {})
            "set_temperature_22" -> ("set_temperature", {"temperature": 22})
            "set_brightness_128" -> ("turn_on", {"brightness": 128})
            "lock" -> ("lock", {})

        Returns:
            Tuple of (service_name, service_data_dict)
        """
        intent_lower = intent.lower().strip()

        # Simple services without parameters
        if intent_lower in self.HA_SERVICES:
            return intent_lower, {}

        # Parse parameterized intents
        parts = intent_lower.split("_")

        # Temperature setting
        if "temperature" in intent_lower and len(parts) >= 3:
            try:
                temp = int(parts[-1])
                return "set_temperature", {"temperature": temp}
            except ValueError:
                pass

        # Brightness setting (light domain)
        if "brightness" in intent_lower and domain == "light":
            try:
                brightness = int(parts[-1])
                return "turn_on", {"brightness": brightness}
            except ValueError:
                pass

        # Cover position
        if "position" in intent_lower and domain == "cover":
            try:
                position = int(parts[-1])
                return "set_cover_position", {"position": position}
            except ValueError:
                pass

        # Volume level
        if "volume" in intent_lower and domain == "media_player":
            try:
                volume = float(parts[-1])
                return "volume_set", {"volume_level": volume}
            except ValueError:
                pass

        # HVAC mode
        if "hvac" in intent_lower or "mode" in intent_lower:
            if "heat" in intent_lower:
                return "set_hvac_mode", {"hvac_mode": "heat"}
            elif "cool" in intent_lower:
                return "set_hvac_mode", {"hvac_mode": "cool"}
            elif "auto" in intent_lower:
                return "set_hvac_mode", {"hvac_mode": "auto"}
            elif "off" in intent_lower:
                return "set_hvac_mode", {"hvac_mode": "off"}

        # Fallback: try to use intent as-is if it's a known service
        if intent_lower in self.HA_SERVICES:
            return intent_lower, {}

        logger.warning(
            f"[ActionOrchestrator] Could not parse intent: {intent}, using as-is"
        )
        return intent_lower, {}
