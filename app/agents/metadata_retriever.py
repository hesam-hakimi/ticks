"""app.agents.metadata_retriever

Retrieves metadata docs from Azure AI Search and builds a compact grounding text.
"""

from __future__ import annotations
from app.contracts.agent_base import BaseAgent, ChatContext
from app.contracts.models import GroundingPack, Citation


def _doc_snippet(doc: dict, max_len: int = 220) -> str:
    txt = str(doc.get("content") or doc.get("business_description") or doc.get("BUSINESS_DESCRIPTION") or doc)
    txt = " ".join(txt.split())
    return (txt[:max_len] + "...") if len(txt) > max_len else txt


class MetadataRetrieverAgent(BaseAgent[GroundingPack]):
    name = "metadata_retriever"

    def __init__(self, search_tool, tracer, logger):
        self.search = search_tool
        self.tracer = tracer
        self.logger = logger

    def run(self, ctx: ChatContext) -> GroundingPack:
        raw = self.search.search(ctx.request.message, top_k=8)
        citations: list[Citation] = []

        for source_key in ("field", "table", "relationship"):
            for doc in raw.get(source_key, [])[:8]:
                doc_id = str(doc.get("id") or doc.get("ID") or doc.get("key") or "")
                citations.append(Citation(
                    source=source_key,  # type: ignore
                    doc_id=doc_id,
                    snippet=_doc_snippet(doc),
                    schema_name=doc.get("schema_name") or doc.get("SCHEMA_NAME"),
                    table_name=doc.get("table_name") or doc.get("TABLE_NAME"),
                    column_name=doc.get("column_name") or doc.get("COLUMN_NAME"),
                ))

        grounding_lines = []
        for c in citations[:25]:
            grounding_lines.append(f"[{c.source}] {c.schema_name or ''}.{c.table_name or ''}.{c.column_name or ''} :: {c.snippet}")
        grounding_text = "\n".join(grounding_lines) if grounding_lines else "(no metadata found)"

        pack = GroundingPack(citations=citations, raw_docs=raw, grounding_text=grounding_text)
        self.tracer.add(self.name, {"citations_preview": [c.__dict__ for c in citations[:10]], "grounding_len": len(grounding_text)})
        return pack
