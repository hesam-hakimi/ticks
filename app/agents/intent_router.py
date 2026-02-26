"""app.agents.intent_router

Intent Router Agent: classifies the request into intent categories.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext
from app.contracts.models import Intent


class IntentRouterAgent(BaseAgent[Intent]):
    name = "intent_router"

    def __init__(self, llm_tool, tracer, logger):
        self.llm = llm_tool
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> Intent:
        out = self.llm.classify_intent(ctx.request.message, ctx.request.history)
        intent = out.get("intent", "DATA_QA")
        self.tracer.add(self.name, out)
        return intent  # type: ignore
