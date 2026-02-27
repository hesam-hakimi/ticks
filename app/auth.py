"""app.auth

Authentication helpers supporting BOTH:
- Managed Identity (MSI / Entra ID)
- API key (for environments where a key is permitted)

Policy:
- Default mode is "auto":
    - If AZURE_OPENAI_API_KEY is set, use API key for Azure OpenAI.
    - Otherwise, use MSI.
  You can override with AZURE_OPENAI_AUTH_MODE = msi | apikey | auto.

Similar logic applies to Azure AI Search with AZURE_SEARCH_API_KEY and AZURE_SEARCH_AUTH_MODE.

Environment variables
---------------------
Azure OpenAI:
  - AZURE_OPENAI_AUTH_MODE: auto | msi | apikey
  - AZURE_OPENAI_API_KEY: (optional) Azure OpenAI resource key
  - AZURE_MSI_CLIENT_ID: (optional) user-assigned managed identity client_id

Azure AI Search:
  - AZURE_SEARCH_AUTH_MODE: auto | msi | apikey
  - AZURE_SEARCH_API_KEY: (optional) Azure AI Search admin/query key

Notes
-----
- MSI path uses ManagedIdentityCredential (no interactive login).
- API keys should be stored in .env and NEVER committed to source control.
"""

from __future__ import annotations

import os
from typing import Any

from azure.identity import ManagedIdentityCredential, get_bearer_token_provider
from azure.core.credentials import AzureKeyCredential

_SCOPE_COGSERV = "https://cognitiveservices.azure.com/.default"


def _norm(v: str | None) -> str:
    return (v or "").strip().lower()


def get_msi_client_id() -> str | None:
    v = os.getenv("AZURE_MSI_CLIENT_ID")
    return v.strip() if v and v.strip() else None


def get_msi_credential() -> ManagedIdentityCredential:
    """Create a ManagedIdentityCredential using client_id when provided."""
    client_id = get_msi_client_id()
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return ManagedIdentityCredential()


# -------- Azure OpenAI --------
def get_aoai_auth_mode() -> str:
    return _norm(os.getenv("AZURE_OPENAI_AUTH_MODE", "auto")) or "auto"


def get_aoai_api_key() -> str | None:
    v = os.getenv("AZURE_OPENAI_API_KEY")
    return v.strip() if v and v.strip() else None


def use_aoai_api_key() -> bool:
    mode = get_aoai_auth_mode()
    if mode == "apikey":
        return True
    if mode == "msi":
        return False
    # auto
    return bool(get_aoai_api_key())


def get_aoai_token_provider():
    """Return a bearer token provider for Azure OpenAI (Cognitive Services scope)."""
    cred = get_msi_credential()
    return get_bearer_token_provider(cred, _SCOPE_COGSERV)


def get_aoai_client_kwargs() -> dict[str, Any]:
    """Kwargs for openai.AzureOpenAI: either api_key or azure_ad_token_provider."""
    if use_aoai_api_key():
        return {"api_key": get_aoai_api_key()}
    return {"azure_ad_token_provider": get_aoai_token_provider()}


# -------- Azure AI Search --------
def get_search_auth_mode() -> str:
    return _norm(os.getenv("AZURE_SEARCH_AUTH_MODE", "auto")) or "auto"


def get_search_api_key() -> str | None:
    v = os.getenv("AZURE_SEARCH_API_KEY")
    return v.strip() if v and v.strip() else None


def use_search_api_key() -> bool:
    mode = get_search_auth_mode()
    if mode == "apikey":
        return True
    if mode == "msi":
        return False
    return bool(get_search_api_key())


def get_search_credential():
    """Return an Azure Search credential: AzureKeyCredential or MSI credential."""
    if use_search_api_key():
        return AzureKeyCredential(get_search_api_key() or "")
    return get_msi_credential()
