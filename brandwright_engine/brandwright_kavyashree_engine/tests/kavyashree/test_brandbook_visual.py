from io import BytesIO
from PIL import Image
from app.review.brandbook import parse_brand_book
from app.review.visual_checks import contrast_ratio, inspect_image


def test_brandbook_parser_returns_owner_approval_drafts():
    rules = parse_brand_book("""1.1 Brand voice\nUse a friendly and clear tone on social channels.\n2.1 Terminology\nUse battery pack in all product descriptions.""")
    assert len(rules) == 2
    assert rules[0]["clause_number"] == "1.1"
    assert "social" in rules[0]["channel_tags"]
    assert all(x["status"] == "draft" and x["requires_owner_approval"] for x in rules)


def test_wcag_contrast_calculation():
    assert contrast_ratio("#000000", "#FFFFFF") == 21.0
    assert contrast_ratio("#777777", "#FFFFFF") < 4.5


def test_image_visual_checks_flag_missing_alt_and_low_contrast():
    image = Image.new("RGB", (32, 32), "white")
    buf = BytesIO(); image.save(buf, format="PNG")
    result = inspect_image(buf.getvalue(), alt_text="", foreground="#777777", background="#FFFFFF")
    checks = {x["category"] for x in result["findings"]}
    assert "accessibility" in checks
    assert result["width"] == 32
