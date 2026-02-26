"""app.tools.azure_search_tool

Azure AI Search tool using **Managed Identity (MSI)** authentication.

This matches the pattern in your VM notebook:
  msi = ManagedIdentityCredential(client_id=...)
  SearchClient(endpoint=..., index_name=..., credential=msi)

This implementation performs simple text search across:
- field index
- table index
- relationship index

Vector/hybrid can be added later.
"""

from __future__ import annotations
from typing import Any
from azure.search.documents import SearchClient

from app.auth import get_msi_credential


class AzureAISearchTool:
    """Metadata search client (MSI)."""

    def __init__(self, endpoint: str, index_field: str, index_table: str, index_relationship: str, logger):
        self.endpoint = endpoint
        self.index_field = index_field
        self.index_table = index_table
        self.index_relationship = index_relationship
        self.credential = get_msi_credential()
        self.logger = logger

    def _client(self, index_name: str) -> SearchClient:
        return SearchClient(endpoint=self.endpoint, index_name=index_name, credential=self.credential)

    def search(self, query: str, top_k: int) -> dict[str, list[dict[str, Any]]]:
        """Return raw docs grouped by index type."""
        results: dict[str, list[dict[str, Any]]] = {"field": [], "table": [], "relationship": []}

        for key, idx in (("field", self.index_field), ("table", self.index_table), ("relationship", self.index_relationship)):
            try:
                client = self._client(idx)
                resp = client.search(search_text=query, top=top_k)
                for doc in resp:
                    results[key].append(dict(doc))
            except Exception as e:
                self.logger.error(f"AI Search query failed for index={idx}: {e}")
        return results
