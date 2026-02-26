from app.policy.sql_policy import SqlPolicy

def test_blocks_dml():
    p = SqlPolicy()
    assert p.validate("DELETE FROM x")

def test_allows_select():
    p = SqlPolicy()
    assert p.validate("SELECT 1") == []
