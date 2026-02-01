import json
from dotenv import load_dotenv

from ollama import chat, ChatResponse, Message

from core.models import WorldState, Decision
from core.actions import ActionType
from core.memory import MemoryManager
from core.logger import logger

load_dotenv()


class Instructor:
    def __init__(self, model: str = "llama3.2:latest"):
        self.model = model
        self.last_decision: Decision | None = None
        self.memory = MemoryManager()

    def _summarize_state(self, world_state: WorldState) -> str:
        """Create a concise state summary."""
        controllable_domains = [
            "light",
            "switch",
            "input_boolean",
            "climate",
            "cover",
            "fan",
            "lock",
            "media_player",
        ]

        controllable = []
        context = []

        for entity in world_state.entities.values():
            ha_entity_id = entity.attributes.get("ha_entity_id", "")
            domain = ha_entity_id.split(".")[0] if "." in ha_entity_id else ""
            state = entity.attributes.get("state", "")

            if domain in controllable_domains:
                controllable.append(
                    f"- {entity.name} (id={str(entity.id)}): state={state}, ha_entity_id={ha_entity_id}"
                )
            elif domain in ["sun", "weather"]:
                context.append(f"- {entity.name}: {state}")

        result = []
        if controllable:
            result.append("CONTROLLABLE:")
            result.extend(controllable)
        if context:
            result.append("\nCONTEXT:")
            result.extend(context)

        return "\n".join(result)

    def _format_last_decision(self) -> str:
        """Format last decision for context in prompt."""
        if not self.last_decision:
            return "None"

        return f"{self.last_decision.action} on {self.last_decision.target_entity_id}: {self.last_decision.reasoning[:50]}"

    def consult_oracle(self, world_state: WorldState) -> Decision | None:
        """Query the LLM for the next optimal action based on current state."""
        response = None
        try:
            available_actions = [action.value for action in ActionType]
            available_actions.append("HA_CALL_SERVICE")
            state_summary = self._summarize_state(world_state)
            last_decision_formatted = self._format_last_decision()
            
            # Retrieve relevant memories - use broader query for better matches
            # Query both with full state and with key context (time, entities)
            query_parts = []
            
            # Add controllable entities to query
            for entity in world_state.entities.values():
                ha_entity_id = entity.attributes.get('ha_entity_id', '')
                if ha_entity_id:
                    domain = ha_entity_id.split('.')[0]
                    if domain in ['light', 'switch', 'input_boolean']:
                        query_parts.append(f"{entity.name} {domain}")
            
            # Add context (time/weather)
            for entity in world_state.entities.values():
                ha_entity_id = entity.attributes.get('ha_entity_id', '')
                if ha_entity_id:
                    domain = ha_entity_id.split('.')[0]
                    if domain in ['sun', 'weather']:
                        state = entity.attributes.get('state', '')
                        query_parts.append(f"{domain} {state}")
            
            # Combine for semantic search
            memory_query = " ".join(query_parts[:5])  # Limit to avoid too long query
            
            relevant_memory = self.memory.retrieve(memory_query, n=3)
            memory_docs = relevant_memory.get('documents', [])
            memory_text = ""
            if memory_docs:
                memory_text = "\n\nPAST EVENTS & PREFERENCES:\n" + "\n".join(f"- {doc}" for doc in memory_docs)
                logger.info("Memories retrieved", count=len(memory_docs), query=memory_query[:60])
            else:
                logger.info("No relevant memories found", query=memory_query[:60])

            system_instruction = f"""You control Home Assistant devices. Available actions: {", ".join(available_actions)}

Examples:
1. Turn on light when sun is down:
{{"action": "HA_CALL_SERVICE", "target_entity_id": "<uuid>", "params": {{"service": "turn_on"}}, "reasoning": "Sun below horizon"}}

2. Toggle input_boolean:
{{"action": "HA_CALL_SERVICE", "target_entity_id": "<uuid>", "params": {{"service": "toggle"}}, "reasoning": "Trigger automation"}}

3. Set light brightness:
{{"action": "HA_CALL_SERVICE", "target_entity_id": "<uuid>", "params": {{"service": "turn_on", "service_data": {{"brightness": 128}}}}, "reasoning": "Dim for evening"}}

Use exact UUIDs from state. Return null if no action needed

Last action: {last_decision_formatted}"""

            user_prompt = f"""State:
{state_summary}{memory_text}

Decide ONE action or return null."""

            logger.info("LLM API call starting", model=self.model)

            decision_schema = Decision.model_json_schema()

            system_message = Message(role="system", content=system_instruction)
            user_message = Message(role="user", content=user_prompt)

            response: ChatResponse = chat(
                model=self.model,
                messages=[system_message, user_message],
                format=decision_schema,
            )

            logger.info("LLM API call completed", has_response=bool(response))

            if not response.message.content:
                logger.info("LLM decision none")
                return None

            content_dict = json.loads(response.message.content)

            if not content_dict:
                logger.info("LLM decision empty")
                self.last_decision = None
                return None

            decision = Decision.model_validate(content_dict)

            ed = decision.target_entity_id

            if decision.action == "null":
                logger.info("LLM decision empty")
                self.last_decision = None
                return None

            # Update last decision tracking
            self.last_decision = decision

            logger.info(
                "LLM decision made",
                action=decision.action,
                target=decision.target_entity_id,
                reasoning=decision.reasoning[:100],  # Truncate for logging
            )
            return decision

        except json.JSONDecodeError as e:
            raw_response = (
                response.message.content if response and response.message else "N/A"
            )
            logger.error(
                "LLM JSON parse failed",
                error=str(e),
                response_text=raw_response[:200],
            )
            return None
        except Exception as e:
            raw_response = (
                response.message.content if response and response.message else "N/A"
            )
            logger.error(
                "LLM consult failed",
                error=str(e),
                response_text=raw_response[:200],
            )
            return None

    def reset_context(self):
        """Reset last decision context (useful for testing or new sessions)."""
        self.last_decision = None
        logger.info("LLM context reset")
