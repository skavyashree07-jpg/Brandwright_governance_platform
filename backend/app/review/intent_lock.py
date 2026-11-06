import re

def preserves_intent(original_intent, original_text, suggestion, key_facts=None):
    if not suggestion or not suggestion.strip(): return False
    number = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|x|times)?\b", re.I)
    original_numbers, new_numbers = set(number.findall(original_text)), set(number.findall(suggestion))
    if original_numbers and not original_numbers.issubset(new_numbers): return False
    for fact in key_facts or []:
        if fact.casefold() in original_text.casefold() and fact.casefold() not in suggestion.casefold():
            return False
    terms = [x.casefold() for x in re.findall(r"[a-zA-Z]{4,}", original_intent)]
    terms = [x for x in terms if x not in {"about","with","from","that","this","into"}]
    return not terms or any(x in suggestion.casefold() for x in terms)

def enforce_intent_lock(intent, original_text, suggestion, key_facts=None):
    return {"text":suggestion,"intent_preserved":True} if preserves_intent(
        intent, original_text, suggestion, key_facts) else None
