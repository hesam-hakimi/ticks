"""scripts.rebuild_search_indexes

Rebuild Azure AI Search metadata indexes from Excel (drop + recreate + upload).

Usage:
  python scripts/rebuild_search_indexes.py --excel /path/to/rrdw_meta_data.xlsx
"""

from __future__ import annotations
import argparse

from app.config import Settings
from app.logging_utils import build_logger
from app.indexing.excel_loader import ExcelLoader
from app.indexing.doc_builder import DocBuilder
from app.indexing.search_index_manager import SearchIndexManager


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True, help="Path to rrdw_meta_data.xlsx")
    args = ap.parse_args()

    settings = Settings.load()
    logger = build_logger(settings.log_dir, name="indexing")

    loader = ExcelLoader()
    data = loader.load(args.excel)

    builder = DocBuilder()
    docs = builder.build(data)

    mgr = SearchIndexManager(settings.azure_search_endpoint, logger=logger)

    mgr.drop_index_if_exists(settings.index_field)
    mgr.drop_index_if_exists(settings.index_table)
    mgr.drop_index_if_exists(settings.index_relationship)

    mgr.create_field_index(settings.index_field)
    mgr.create_table_index(settings.index_table)
    mgr.create_relationship_index(settings.index_relationship)

    mgr.upload_docs(settings.index_field, docs["field"])
    mgr.upload_docs(settings.index_table, docs["table"])
    mgr.upload_docs(settings.index_relationship, docs["relationship"])

    logger.info("Index rebuild complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
