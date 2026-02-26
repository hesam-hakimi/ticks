"""app.agents.requirement_clarity

Clarify-first step. Uses metadata grounding to identify ambiguity.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext
from app.contracts.models import ClarificationResult


class RequirementClarityAgent(BaseAgent[ClarificationResult]):
    name = "requirement_clarity"

    def __init__(self, llm_tool, tracer, logger, max_turns: int = 5):
        self.llm = llm_tool
        self.tracer = tracer
        self.logger = logger
        self.max_turns = max_turns

    def run(self, ctx: ChatContext) -> ClarificationResult:
        grounding = ctx.grounding.grounding_text if ctx.grounding else ""
        out = self.llm.check_clarity(ctx.request.message, grounding, ctx.request.history)
        self.tracer.add(self.name, out)
        return ClarificationResult(
            is_clear=bool(out.get("is_clear", True)),
            questions=list(out.get("questions", []))[:5],
            assumptions_if_proceed=list(out.get("assumptions_if_proceed", []))[:10],
        )
