"""Base classes and models for multi-agent decision making."""

import uuid
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

from core.models import WorldState, Decision
from core.agents.orchestrator import ActionIntent
from core.memory import MemoryManager
from core.logger import logger


class AgentProposal(BaseModel):
    """A proposal from a specialist agent."""

    agent_name: str
    domain: str  # "security", "comfort", "energy"
    decision: Decision | ActionIntent | None
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0
    priority_score: float = Field(
        default=0.5
    )  # How important this agent thinks this action is
    
    model_config = {"arbitrary_types_allowed": True}


class BaseAgent(ABC):
    """Abstract base class for specialist agents."""

    def __init__(self, name: str, domain: str, model: str = "llama3.2:latest"):
        self.name = name
        self.domain = domain
        self.model = model
        self.memory = MemoryManager()

    @abstractmethod
    async def propose_action(
        self, world_state: WorldState, memory_context: str
    ) -> AgentProposal:
        """
        Analyze state and propose an action within this agent's domain.

        Args:
            world_state: Current world state
            memory_context: Relevant memories from vector store

        Returns:
            AgentProposal with decision or None if no action needed
        """
        pass

    def _filter_entities_by_domain(
        self, world_state: WorldState, domains: list[str]
    ) -> list[tuple[uuid.UUID, str, str, str]]:
        """
        Filter entities relevant to this agent's domain.

        Returns:
            List of (entity_id, name, state, ha_entity_id) tuples
        """
        relevant = []
        for entity in world_state.entities.values():
            ha_entity_id = entity.attributes.get("ha_entity_id", "")
            
            # Check if any domain keyword is contained in the full ha_entity_id
            # e.g., "light" matches "input_boolean.virtual_lamp" if we're looking for lamp-related entities
            # or "lock" matches "lock.front_door"
            if any(domain in ha_entity_id for domain in domains):
                state = entity.attributes.get("state", "unknown")
                relevant.append((entity.id, entity.name, state, ha_entity_id))

        return relevant

    def _get_memory_context(
        self, world_state: WorldState, domain_filter: list[str] | None = None
    ) -> str:
        """
        Retrieve relevant memories for decision-making.

        Args:
            world_state: Current world state
            domain_filter: Optional list of domains to filter query (e.g., ['light', 'switch'])

        Returns:
            Formatted memory context string
        """
        query_parts = []

        # Build query from relevant entities
        for entity in world_state.entities.values():
            ha_entity_id = entity.attributes.get("ha_entity_id", "")
            if ha_entity_id:
                # Filter by domain if specified (check if any domain keyword is in ha_entity_id)
                if domain_filter:
                    if not any(d in ha_entity_id for d in domain_filter):
                        continue

                # Extract domain for categorization
                domain = ha_entity_id.split(".")[0] if "." in ha_entity_id else ""

                # Add controllable entities
                if domain in [
                    "light",
                    "switch",
                    "input_boolean",
                    "climate",
                    "lock",
                    "cover",
                    "fan",
                ]:
                    query_parts.append(f"{entity.name} {domain}")

        # Add context (time/weather) - always include for all agents
        for entity in world_state.entities.values():
            ha_entity_id = entity.attributes.get("ha_entity_id", "")
            if ha_entity_id:
                domain = ha_entity_id.split(".")[0] if "." in ha_entity_id else ""
                if domain in ["sun", "weather"]:
                    state = entity.attributes.get("state", "")
                    query_parts.append(f"{domain} {state}")

        # Combine for semantic search
        memory_query = " ".join(query_parts[:5])  # Limit to avoid too long query

        if not memory_query:
            return "No relevant memories found."

        relevant_memory = self.memory.retrieve(memory_query, n=3)
        memory_docs = relevant_memory.get("documents", [])

        if memory_docs:
            logger.debug(
                f"[{self.name}] Memories retrieved",
                count=len(memory_docs),
                query=memory_query[:60],
            )
            return "\n".join(f"- {doc}" for doc in memory_docs)
        else:
            logger.debug(
                f"[{self.name}] No relevant memories", query=memory_query[:60]
            )
            return "No relevant memories found."
