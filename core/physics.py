from core.models import WorldState, Physics, Entity
from core.logger import log_with_tui
from core.utils import increment_attribute


class PhysicsEngine:
    def __init__(self, physics_data: list[Physics]):
        self.physics_data = physics_data
        self.stats = {
            "rules_evaluated": 0,
            "rules_fired": 0,
            "entities_affected": set(),
        }

    def apply_physics(self, world_state: WorldState):
        # Reset stats for this tick
        self.stats = {
            "rules_evaluated": 0,
            "rules_fired": 0,
            "entities_affected": set(),
        }

        # Phase 1: Apply entity-local physics rules
        for physics in self.physics_data:
            entities = world_state.get_entities_by_tag(physics.target_tag)

            for entity in entities:
                self.stats["rules_evaluated"] += 1

                # Check condition if specified
                if physics.condition:
                    if not self._eval_condition(entity, physics.condition, world_state):
                        continue

                # Rule fired - apply the physics
                self.stats["rules_fired"] += 1
                self.stats["entities_affected"].add(entity.name)

                # Special handling for global attributes
                if physics.target_tag == "global":
                    self._update_global_attribute(
                        world_state, physics.attribute, physics.delta
                    )
                else:
                    increment_attribute(
                        world=world_state,
                        entity_name=entity.name,
                        attribute_name=physics.attribute,
                        delta=physics.delta,
                    )

        # Phase 2: Aggregation (network load from devices to router)
        self._aggregate_network_load(world_state)

        # Log summary
        log_with_tui(
            "info",
            "physics_summary",
            rules_evaluated=self.stats["rules_evaluated"],
            rules_fired=self.stats["rules_fired"],
            entities_affected=len(self.stats["entities_affected"]),
        )

    def _aggregate_network_load(self, world_state: WorldState):
        """Aggregate network load contributions to router"""
        routers = world_state.get_entities_by_tag("type:router")
        
        for router in routers:
            # Sum all network load contributions from devices
            total_load = 0.0
            active_devices = []
            
            for entity in world_state.entities.values():
                contribution = entity.attributes.get("network_load_contribution", 0.0)
                if contribution > 0:
                    total_load += contribution
                    active_devices.append(entity.name)
            
            # Update router's network load
            try:
                current_load = world_state.get_attribute_value(router.id, "network_load")
                new_load = max(0.0, min(100.0, current_load + total_load))  # Clamp 0-100
                world_state.set_attribute_value(router.id, "network_load", new_load)
                
                # Update connected devices count
                world_state.set_attribute_value(router.id, "connected_devices_count", len(active_devices))
                
                if total_load > 0:
                    log_with_tui(
                        "debug",
                        "network_aggregation",
                        router=router.name,
                        total_load=round(total_load, 1),
                        active_devices=len(active_devices),
                        new_network_load=round(new_load, 1),
                    )
            except KeyError:
                pass

    def _update_global_attribute(
        self, world_state: WorldState, attribute: str, delta: float
    ):
        """Update global attribute with special logic for time wraparound"""
        current = world_state.global_attributes.get(attribute, 0.0)
        
        if isinstance(current, (int, float)):
            new_value = current + delta
            
            # Time wraparound: reset to 0 after 24 hours
            if attribute == "time_of_day" and new_value >= 24.0:
                new_value = new_value % 24.0
            elif attribute == "time_of_day" and new_value < 0.0:
                new_value = 24.0 + (new_value % 24.0)
            
            world_state.global_attributes[attribute] = new_value
            
            # Auto-update derived attributes
            if attribute == "time_of_day":
                world_state.global_attributes["is_night"] = (
                    new_value < 6.0 or new_value >= 20.0
                )
        else:
            # Non-numeric global attribute (like weather string)
            world_state.global_attributes[attribute] = current

    def _eval_condition(self, entity: Entity, condition: str, world_state: WorldState) -> bool:
        """Safely evaluate condition like 'state == "ON"' with global attribute access"""
        try:
            # Create safe namespace with entity attributes and global attributes
            namespace = entity.attributes.copy()
            namespace["g"] = world_state.global_attributes
            
            # Safe eval with restricted builtins
            result = eval(condition, {"__builtins__": {}}, namespace)
            return bool(result)
        except Exception as e:
            log_with_tui(
                "debug",
                "condition_eval_failed",
                entity=entity.name,
                condition=condition,
                error=str(e),
            )
            return False

    def add_physics_rule(self, physics: Physics) -> None:
        """Add a single physics rule (typically called by plugins)."""
        self.physics_data.append(physics)
        log_with_tui(
            "debug",
            "physics_rule_added",
            target_tag=physics.target_tag,
            attribute=physics.attribute,
            delta=physics.delta,
        )

    def add_multiple_rules(self, rules: list[Physics]) -> None:
        """Bulk add multiple physics rules."""
        self.physics_data.extend(rules)
        log_with_tui(
            "info",
            "physics_rules_bulk_added",
            count=len(rules),
        )

    def get_rules_by_tag(self, tag: str) -> list[Physics]:
        """Query existing physics rules by target tag."""
        return [p for p in self.physics_data if p.target_tag == tag]
