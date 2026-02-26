"""app.indexing.search_index_manager

Drops + recreates Azure AI Search indexes, then uploads docs.
Uses **Managed Identity (MSI)** via ManagedIdentityCredential(client_id=...).
"""

from __future__ import annotations
from typing import Any

from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchableField, SearchFieldDataType

from app.auth import get_msi_credential


class SearchIndexManager:
    """Create/recreate indexes and upload documents."""

    def __init__(self, endpoint: str, logger):
        self.endpoint = endpoint
        self.credential = get_msi_credential()
        self.logger = logger
        self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=self.credential)

    def drop_index_if_exists(self, name: str) -> None:
        try:
            self.index_client.get_index(name)
            self.index_client.delete_index(name)
            self.logger.info(f"Deleted index {name}")
        except Exception:
            pass

    def create_field_index(self, name: str) -> None:
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="schema_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="table_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="column_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="data_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="pii", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="pci", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="business_name", type=SearchFieldDataType.String),
            SearchableField(name="business_description", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
        ]
        self.index_client.create_index(SearchIndex(name=name, fields=fields))
        self.logger.info(f"Created index {name}")

    def create_table_index(self, name: str) -> None:
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="schema_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="table_name", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="table_business_name", type=SearchFieldDataType.String),
            SearchableField(name="table_business_description", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
        ]
        self.index_client.create_index(SearchIndex(name=name, fields=fields))
        self.logger.info(f"Created index {name}")

    def create_relationship_index(self, name: str) -> None:
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="from_schema", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="from_table", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="to_schema", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="to_table", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="join_type", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="join_keys", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
        ]
        self.index_client.create_index(SearchIndex(name=name, fields=fields))
        self.logger.info(f"Created index {name}")

    def upload_docs(self, index_name: str, docs: list[dict[str, Any]]) -> None:
        client = SearchClient(endpoint=self.endpoint, index_name=index_name, credential=self.credential)
        batch: list[dict[str, Any]] = []
        for d in docs:
            batch.append(d)
            if len(batch) >= 1000:
                client.upload_documents(documents=batch)
                batch = []
        if batch:
            client.upload_documents(documents=batch)
        self.logger.info(f"Uploaded {len(docs)} documents to {index_name}")
