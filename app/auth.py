"""app.auth

Managed Identity (MSI) helpers.

This project must authenticate to Azure services using **Managed Identity**,
and specifically supports **User-Assigned Managed Identity** by client_id.

Environment:
  - AZURE_MSI_CLIENT_ID: client_id (GUID) of the user-assigned managed identity.

Usage:
  cred = get_msi_credential()
  token_provider = get_aoai_token_provider()
"""

from __future__ import annotations
import os
from azure.identity import ManagedIdentityCredential, get_bearer_token_provider

_SCOPE_COGSERV = "https://cognitiveservices.azure.com/.default"


def get_msi_client_id() -> str | None:
    """Return MSI client_id from env, if set."""
    v = os.getenv("AZURE_MSI_CLIENT_ID")
    return v.strip() if v and v.strip() else None


def get_msi_credential() -> ManagedIdentityCredential:
    """Create a ManagedIdentityCredential using client_id when provided."""
    client_id = get_msi_client_id()
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    # Fallback to system-assigned MSI if allowed; still MSI, no interactive login.
    return ManagedIdentityCredential()


def get_aoai_token_provider():
    """Return a bearer token provider for Azure OpenAI (Cognitive Services scope)."""
    cred = get_msi_credential()
    return get_bearer_token_provider(cred, _SCOPE_COGSERV)
