"""app.indexing.excel_schema

Expected Excel structure for metadata ingestion.
Sheets: field, table, relationship
"""

REQUIRED_SHEETS = ["field", "table", "relationship"]

FIELD_REQUIRED_COLUMNS = [
    "SCHEMA_NAME", "TABLE_NAME", "COLUMN_NAME",
    "DATA_TYPE", "BUSINESS_NAME", "BUSINESS_DESCRIPTION",
    "PII", "PCI",
]

TABLE_REQUIRED_COLUMNS = [
    "SCHEMA_NAME", "TABLE_NAME",
    "TABLE_BUSINESS_NAME", "TABLE_BUSINESS_DESCRIPTION",
]

REL_REQUIRED_COLUMNS = [
    "FROM_SCHEMA", "FROM_TABLE",
    "TO_SCHEMA", "TO_TABLE",
    "JOIN_TYPE", "JOIN_KEYS",
]
