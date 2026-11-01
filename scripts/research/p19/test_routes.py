import routes as R


def test_routes_by_strength():
    assert R.plan("de", "es")["route"] == "direct"
    assert R.plan("am", "es")["route"] == "target-direct"
    assert R.plan("de", "om")["route"] == "source-side"
    assert R.plan("am", "om")["route"] == "pivot"


def test_budget_controls_working_languages():
    eco = R.plan("am", "om", "economy", ["en", "es"])
    q = R.plan("am", "om", "quality", ["en", "es"])
    assert eco["writes_in"] == ["en"] and q["writes_in"] == ["en", "es"]
    assert any("back-translate" in s for s in q["steps"])
    assert R.plan("am", "es", "quality")["writes_in"] == ["es", "en"]
