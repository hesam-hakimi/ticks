"""scripts.validate_excel

Validates Excel structure only.

Usage:
  python scripts/validate_excel.py --excel /path/to/rrdw_meta_data.xlsx
"""

from __future__ import annotations
import argparse
from app.indexing.excel_loader import ExcelLoader


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True)
    args = ap.parse_args()
    ExcelLoader().load(args.excel)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
