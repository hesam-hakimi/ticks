# Demo data v3 (trend-focused) — company_name

This pack adds more datasets designed specifically for trend visualizations (monthly and weekly).

## Trend datasets
- executive_financial_overview_monthly.csv  (3 years)
- balance_sheet_trends_monthly.csv          (3 years)
- product_mix_trends_monthly.csv            (3 years x product)
- region_trends_monthly.csv                 (3 years x region)
- customer_churn_cohorts_monthly.csv        (3 years x segment x channel)
- credit_quality_trends_monthly.csv         (3 years x portfolio)
- branch_geo_weekly.csv                     (52 weeks x branch; includes lat/lon)
- tech_reliability_trends_weekly.csv        (52 weeks x service)

## Helpers
- built_in_questions.yaml
- intent_registry.yaml

Notes:
- All data is synthetic for demo.
- No special alert symbols are used.


## JSON versions
All datasets are also provided under `data/available_json/` in two formats:
- `.jsonl` (JSON Lines; one record per line)
- `.json` (single JSON array)
