import os
import uuid
import requests
from core.plugins import BasePlugin
from core.logger import logger
from core.models import Entity, WorldState, DecisionParams


class HomeAssistantPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self._ha_url = None
        self._ha_token = None
        self._entity_map = {}
        self._tick_counter = 0
        self._poll_interval = 5

    @property
    def name(self) -> str:
        return "Home Assistant Bridge"

    def _get_ha_url(self) -> str:
        if not self._ha_url:
            self._ha_url = os.getenv("HASSIO_URL", "").rstrip("/")
            if not self._ha_url:
                raise ValueError("HASSIO_URL environment variable not set")
        return self._ha_url

    def _get_ha_token(self) -> str:
        if not self._ha_token:
            self._ha_token = os.getenv("HASSIO_TOKEN", "")
            if not self._ha_token:
                raise ValueError("HASSIO_TOKEN environment variable not set")
        return self._ha_token

    def _fetch_ha_entities(self) -> list[dict]:
        try:
            url = f"{self._get_ha_url()}/api/states"
            headers = {
                "Authorization": f"Bearer {self._get_ha_token()}",
                "Content-Type": "application/json",
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("HA fetch failed", error=str(e))
            return []

    def _call_ha_service(self, domain: str, service: str, entity_id: str, **kwargs):
        try:
            url = f"{self._get_ha_url()}/api/services/{domain}/{service}"
            headers = {
                "Authorization": f"Bearer {self._get_ha_token()}",
                "Content-Type": "application/json",
            }
            payload = {"entity_id": entity_id, **kwargs}
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(
                "HA service called", domain=domain, service=service, entity=entity_id
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("HA service failed", error=str(e), entity=entity_id)
            raise

    def _map_ha_entity_to_farz(self, ha_entity: dict) -> Entity:
        entity_id = ha_entity["entity_id"]
        domain = entity_id.split(".")[0]
        state = ha_entity["state"]
        attributes = ha_entity.get("attributes", {})

        tags = [f"ha:{domain}"]
        if domain == "light":
            tags.append("device:light")
        elif domain == "switch":
            tags.append("device:switch")
        elif domain == "sensor":
            tags.append("sensor")
        elif domain == "climate":
            tags.append("device:climate")

        farz_attributes = {
            "state": state,
            "ha_entity_id": entity_id,
        }

        if domain == "light":
            farz_attributes["brightness"] = attributes.get("brightness", 0)
            farz_attributes["color_temp"] = attributes.get("color_temp", 0)
        elif domain == "sensor":
            if state not in ["unknown", "unavailable"]:
                try:
                    farz_attributes["value"] = float(state)
                except ValueError:
                    farz_attributes["value"] = state
        elif domain == "climate":
            farz_attributes["temperature"] = attributes.get("temperature", 20.0)
            farz_attributes["current_temperature"] = attributes.get(
                "current_temperature", 20.0
            )

        return Entity(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, entity_id),
            name=attributes.get("friendly_name", entity_id),
            tags=tags,
            attributes=farz_attributes,
        )

    def _sync_state(self, world_state):
        """Sync current HA states to existing entities."""
        ha_entities = self._fetch_ha_entities()
        if not ha_entities:
            return

        updated_count = 0
        for ha_entity in ha_entities:
            ha_entity_id = ha_entity["entity_id"]
            farz_id = self._entity_map.get(ha_entity_id)

            if farz_id and farz_id in world_state.entities:
                entity = world_state.entities[farz_id]
                state = ha_entity["state"]
                attributes = ha_entity.get("attributes", {})

                entity.attributes["state"] = state

                domain = ha_entity_id.split(".")[0]
                if domain == "light":
                    entity.attributes["brightness"] = attributes.get("brightness", 0)
                    entity.attributes["color_temp"] = attributes.get("color_temp", 0)
                elif domain == "sensor":
                    if state not in ["unknown", "unavailable"]:
                        try:
                            entity.attributes["value"] = float(state)
                        except ValueError:
                            entity.attributes["value"] = state
                elif domain == "climate":
                    entity.attributes["temperature"] = attributes.get(
                        "temperature", 20.0
                    )
                    entity.attributes["current_temperature"] = attributes.get(
                        "current_temperature", 20.0
                    )

                updated_count += 1

        if updated_count > 0:
            logger.debug("HA state synced", updated=updated_count)

    def register_actions(self, dispatcher):
        def ha_call_service_action(
            world: WorldState, target_id: str, params: DecisionParams
        ):
            entity = world.get_entity_by_id(target_id)
            if not entity:
                logger.error("HA action no entity", target=str(target_id))
                return

            ha_entity_id = entity.attributes.get("ha_entity_id")
            if not ha_entity_id:
                logger.error("HA action not HA entity", entity=entity.name)
                return

            domain = ha_entity_id.split(".")[0]
            service = params.service
            service_data = params.service_data or {}

            try:
                self._call_ha_service(domain, service, ha_entity_id, **service_data)

                if service == "turn_on":
                    entity.attributes["state"] = "on"
                elif service == "turn_off":
                    entity.attributes["state"] = "off"

            except Exception as e:
                logger.error("HA action failed", error=str(e))

        dispatcher.register("HA_CALL_SERVICE", ha_call_service_action)

    def register_physics(self, physics_engine):
        pass

    def on_startup(self, state):
        try:
            ha_entities = self._fetch_ha_entities()
            if not ha_entities:
                logger.warning(
                    "HA no entities", message="No entities fetched from Home Assistant"
                )
                return

            synced_count = 0
            for ha_entity in ha_entities:
                try:
                    farz_entity = self._map_ha_entity_to_farz(ha_entity)

                    entity_state = farz_entity.attributes.get("state")
                    if entity_state in ["unknown", "unavailable"]:
                        logger.debug(
                            "Skipping unknown entity", entity=ha_entity.get("entity_id")
                        )
                        continue

                    state.entities[farz_entity.id] = farz_entity
                    self._entity_map[ha_entity["entity_id"]] = farz_entity.id
                    synced_count += 1
                except Exception as e:
                    logger.warning(
                        "HA entity map failed",
                        entity=ha_entity.get("entity_id"),
                        error=str(e),
                    )

            logger.info("HA sync complete", total=len(ha_entities), synced=synced_count)

        except Exception as e:
            logger.error("HA startup failed", error=str(e))

    async def on_tick(self, state, tick: int):
        """Sync HA state every N ticks."""
        self._tick_counter += 1

        if self._tick_counter >= self._poll_interval:
            self._tick_counter = 0
            try:
                self._sync_state(state)
            except Exception as e:
                logger.error("HA tick sync failed", error=str(e))
