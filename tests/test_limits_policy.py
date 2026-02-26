from app.policy.limits_policy import LimitsPolicy

def test_sqlserver_top_injected():
    lp = LimitsPolicy()
    s = lp.apply_row_limit("SELECT col FROM t", "sqlserver", 10)
    assert "TOP" in s.upper()

def test_sqlite_limit_appended():
    lp = LimitsPolicy()
    s = lp.apply_row_limit("SELECT col FROM t", "sqlite", 10)
    assert "LIMIT 10" in s.upper()
