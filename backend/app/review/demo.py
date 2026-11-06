from .pipeline import review_text

if __name__ == "__main__":
    rules = [
        {"id":"r2.1","text":"Use battery pack, not battery.","type":"preferred_term",
         "config":{"preferred":"battery pack","variants":["battery"]}},
        {"id":"r4.2","text":"Avoid unsupported superlatives.","type":"superlative",
         "config":{"terms":["safest"]}},
    ]
    facts = [{"id":"f40","text":"Battery pack lasts up to 40% longer than our previous model."}]
    result = review_text("Our battery is the safest and lasts 3x longer than competitors.",
        "announce battery performance to customers", rules, facts)
    for finding in result["findings"]: print(finding.to_dict())
    print("AI services:", result["ai_services_used"])
