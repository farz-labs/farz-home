"""Manager agent - orchestrates specialist agents and resolves conflicts."""

import asyncio
import json
from ollama import chat, Message

from core.agents import AgentProposal
from core.agents.orchestrator import ActionIntent
from core.logger import logger


class ManagerAgent:
    """
    Manager that coordinates specialist agents and makes final decisions.
    Reviews proposals from Security, Comfort, and Energy specialists.
    """

    def __init__(self, model: str = "llama3.2:latest"):
        self.model = model
        self.priority_order = ["security", "comfort", "energy"]  # Default priorities

    def set_priorities(self, priorities: list[str]):
        """Update domain priority order (highest to lowest)."""
        self.priority_order = priorities

    async def decide(
        self, proposals: list[AgentProposal], memory_context: str
    ) -> tuple[ActionIntent | None, str]:
        """
        Review all specialist proposals and make final decision.

        Args:
            proposals: List of proposals from specialist agents
            memory_context: User preferences and past decisions

        Returns:
            Tuple of (final_action_intent, reasoning)
        """

        # Filter out error proposals
        valid_proposals = [p for p in proposals if p.confidence > 0.0]

        # If no valid proposals, return null
        if not valid_proposals:
            logger.info("[Manager] No valid proposals from specialists")
            return None, "No specialists proposed actions"

        # If only one proposal with action, accept it
        proposals_with_actions = [p for p in valid_proposals if p.decision is not None]

        if len(proposals_with_actions) == 0:
            logger.info("[Manager] All specialists proposed null actions")
            return None, "All specialists agree: no action needed"

        if len(proposals_with_actions) == 1:
            proposal = proposals_with_actions[0]
            reasoning = f"[Manager] Accepted {proposal.agent_name} proposal (only action): {proposal.reasoning}"
            logger.info(reasoning)
            return proposal.decision, reasoning

        # Multiple proposals - need LLM arbitration
        return await self._arbitrate_with_llm(
            proposals_with_actions, memory_context
        )

    async def _arbitrate_with_llm(
        self, proposals: list[AgentProposal], memory_context: str
    ) -> tuple[ActionIntent | None, str]:
        """Use LLM to choose between conflicting proposals."""

        # Build proposal summary
        proposal_lines = []
        for i, prop in enumerate(proposals, 1):
            if isinstance(prop.decision, ActionIntent):
                action_str = f"{prop.decision.intent} on {prop.decision.entity_name}"
            else:
                action_str = "null"
            
            proposal_lines.append(
                f"{i}. [{prop.agent_name}] {action_str}\n"
                f"   Reasoning: {prop.reasoning}\n"
                f"   Priority Score: {prop.priority_score:.2f}\n"
                f"   Confidence: {prop.confidence:.2f}"
            )

        proposals_text = "\n\n".join(proposal_lines)

        # Build arbitration prompt
        system_prompt = f"""You are a MANAGER agent coordinating a smart home system. You must choose ONE action from multiple specialist proposals.

DEFAULT PRIORITY ORDER: {' > '.join(self.priority_order)}
This means: if conflicts arise, favor {self.priority_order[0]} over {self.priority_order[1]} over {self.priority_order[2]}.

HOWEVER: Also consider:
- User preferences from memory (may override default priorities)
- Urgency (priority_score from each agent)
- Confidence levels
- Reasoning quality

YOUR JOB:
1. Review all proposals
2. Check memory for user preferences
3. Select the BEST action
4. Explain your decision clearly

Respond with JSON:
{{
  "selected_proposal_number": 1 or 2 or 3 or null,
  "reasoning": "why you chose this proposal over others"
}}"""

        user_prompt = f"""PROPOSALS:
{proposals_text}

USER PREFERENCES & MEMORY:
{memory_context}

Which proposal should be executed? Consider priorities, urgency, and user preferences."""

        # Call LLM
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: chat(
                model=self.model,
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_prompt),
                ],
                format="json",
                options={"temperature": 0.2},  # Low temp for consistent decisions
            ),
        )

        # Parse response
        try:
            result = json.loads(response.message.content)
            selected_num = result.get("selected_proposal_number")
            reasoning = result.get("reasoning", "No reasoning provided")

            if selected_num is None or selected_num == "null":
                logger.info(f"[Manager] Decided null action: {reasoning}")
                return None, f"[Manager] {reasoning}"

            # Get selected proposal (1-indexed)
            if 1 <= selected_num <= len(proposals):
                selected = proposals[selected_num - 1]
                full_reasoning = f"[Manager] Selected {selected.agent_name}: {reasoning}"
                logger.info(full_reasoning)
                return selected.decision, full_reasoning
            else:
                logger.error(
                    f"[Manager] Invalid proposal number: {selected_num} (max {len(proposals)})"
                )
                return None, "Manager error: invalid proposal selection"

        except Exception as e:
            logger.error(f"[Manager] Failed to arbitrate: {e}")
            # Fallback: choose by priority order
            for domain in self.priority_order:
                for prop in proposals:
                    if prop.domain == domain and prop.decision:
                        fallback_reasoning = f"[Manager] Fallback to {prop.agent_name} (LLM error, using priority order)"
                        logger.warning(fallback_reasoning)
                        return prop.decision, fallback_reasoning

            return None, f"[Manager] Arbitration failed: {e}"
