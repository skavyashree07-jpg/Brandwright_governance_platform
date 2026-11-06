from app.review.rule_engine import run_rule_engine

def test_banned_preferred_and_superlative():
    rules=[
      {"id":"1","type":"banned_term","text":"Avoid cheap","config":{"term":"cheap","replacement":"affordable"}},
      {"id":"2","type":"preferred_term","text":"Use battery pack","config":{"preferred":"battery pack","variants":["battery"]}},
      {"id":"3","type":"superlative","text":"Substantiate superlatives","config":{"terms":["safest"]}},
    ]
    fs=run_rule_engine("cheap battery is safest",rules)
    assert len(fs)==3 and all(f.source for f in fs)

def test_missing_disclaimer():
    rule={"id":"4","type":"required_disclaimer","text":"Add terms","config":{"phrase":"Terms apply"}}
    assert run_rule_engine("Offer ends today",[rule])[0].span.start==0
