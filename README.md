# company_name Text-to-SQL (Phase 1 + Phase 2) — Reference Implementation

This repo contains a production-oriented prototype for:
- **Phase 1**: Agentic solution (no Redis, no analytics charts required)
- **Phase 2**: Adds Analytics/Report intent + chart generation from aggregated results

## Constraints supported
- Azure OpenAI + Azure AI Search + Azure SQL via **Managed Identity (MSI)** (no API keys in code)
- Read-only analytics: **SELECT-only**, blocks DDL/DML
- Limits configurable in UI: max rows, max columns, max execution time, debug mode
- Modular architecture with clear boundaries

## Quick start (Streamlit UI)
1. Create a Python venv (3.11+)
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables (see `.env.example`).
4. Run UI:
   ```bash
   streamlit run ui/streamlit_app.py
   ```

## Rebuild metadata indexes (Excel → Azure AI Search)
Prepare `rrdw_meta_data.xlsx` with sheets: `field`, `table`, `relationship`.

Run:
```bash
python scripts/rebuild_search_indexes.py --excel /path/to/rrdw_meta_data.xlsx
```

## Notes
- Metadata retrieval uses **text search** across 3 indexes. Vector/hybrid can be added later.
- SQL Server connectivity uses `pyodbc`. With MSI, use ODBC Driver 18 + `Authentication=ActiveDirectoryMsi`.
- Phase 2 charts use matplotlib from aggregated results only.


## FastPath (top ~100 common queries)
See `app/fastpath/`. Add your common queries as templates for fast answers.


## Analytics Report (Phase 2)
The system can generate multi-query aggregated reports and return **business-friendly markdown** plus **charts** (Plotly preferred, Seaborn optional).


## Architecture (best-practice summary)
- Orchestrator (code) enforces guardrails: SELECT-only, limits, retries, truncation.
- First-class AutoGen agents (AssistantAgent): intent routing, clarity, SQL generation, report planning, report writing.
- FastPath templates for top common queries (~100) live in `app/fastpath/` for speed and consistency.
- Analytics reports: planner -> execute 1–5 aggregated queries -> render Plotly/Seaborn charts -> produce executive markdown.


## .env loading
This project automatically loads environment variables from a `.env` file (if present) using `python-dotenv` via `app.env_loader.load_env()`.


## Visualization agent
This project includes a `viz_coder` AutoGen agent that generates SAFE visualization code at runtime (no imports) and a sandbox executor (`app/viz/code_sandbox.py`) that runs it with restricted builtins + timeout.


## Currently available data (fast lane)
The app first tries to answer from small summarized datasets stored under `data/available_json/` (JSON Lines). If the data is not available, it asks whether to search elsewhere (fallback path).

## Role-based questions
The UI includes CEO/CFO/CTO role buttons and a curated list of suggested questions loaded from `data/built_in_questions.json`.


## Authentication (MSI or API key)
This project supports both Managed Identity (Entra ID) and API-key authentication for Azure OpenAI and Azure AI Search.
- Default: `AZURE_OPENAI_AUTH_MODE=auto` uses API key if `AZURE_OPENAI_API_KEY` is set, otherwise MSI.
- Force MSI: set `AZURE_OPENAI_AUTH_MODE=msi`
- Force API key: set `AZURE_OPENAI_AUTH_MODE=apikey` and provide `AZURE_OPENAI_API_KEY`

Similarly for Search: `AZURE_SEARCH_AUTH_MODE` + `AZURE_SEARCH_API_KEY`.
