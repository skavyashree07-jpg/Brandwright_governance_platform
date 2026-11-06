"""Deterministic visual checks using explicit brand configuration and image metadata."""
import re
from PIL import Image


def _rgb(value: str):
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not match:
        raise ValueError(f"Invalid hex colour: {value}")
    raw = match.group(1)
    return tuple(int(raw[i:i+2], 16) for i in (0, 2, 4))


def _luminance(rgb):
    channels = []
    for c in rgb:
        c = c / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float:
    a, b = sorted((_luminance(_rgb(foreground)), _luminance(_rgb(background))), reverse=True)
    return round((a + 0.05) / (b + 0.05), 2)


def inspect_image(file_bytes: bytes, *, alt_text: str | None = None,
                  allowed_palette: list[str] | None = None, palette_tolerance: int = 55,
                  logo_bbox: list[int] | None = None, min_logo_width: int = 0,
                  min_logo_height: int = 0, foreground: str | None = None,
                  background: str | None = None, min_contrast: float = 4.5) -> dict:
    """Returns objective checks. Logo presence is only assessed when bbox metadata is supplied."""
    from io import BytesIO
    image = Image.open(BytesIO(file_bytes)).convert("RGB")
    width, height = image.size
    findings = []
    if not (alt_text or "").strip():
        findings.append({"check_type": "accessibility", "category": "accessibility",
                         "severity": "medium", "status": "violation",
                         "explanation": "Alternative text is missing.", "span": None})
    if allowed_palette:
        allowed = [_rgb(c) for c in allowed_palette]
        sample = image.copy(); sample.thumbnail((160, 160))
        pixels = list(sample.getdata())
        nonmatching = 0
        for px in pixels:
            if min(sum((px[i] - ref[i]) ** 2 for i in range(3)) ** 0.5 for ref in allowed) > palette_tolerance:
                nonmatching += 1
        ratio = nonmatching / max(len(pixels), 1)
        if ratio > 0.35:
            findings.append({"check_type": "visual", "category": "visual", "severity": "medium",
                             "status": "violation", "explanation": f"Approximately {ratio:.0%} of sampled pixels fall outside the configured brand palette."})
    if logo_bbox is not None:
        if len(logo_bbox) != 4:
            raise ValueError("logo_bbox must be [x, y, width, height]")
        _, _, logo_w, logo_h = [int(v) for v in logo_bbox]
        if logo_w < min_logo_width or logo_h < min_logo_height:
            findings.append({"check_type": "visual", "category": "visual", "severity": "medium",
                             "status": "violation", "explanation": "Logo is smaller than the configured minimum dimensions."})
    if foreground and background:
        ratio = contrast_ratio(foreground, background)
        if ratio < min_contrast:
            findings.append({"check_type": "accessibility", "category": "accessibility", "severity": "high",
                             "status": "violation", "explanation": f"Configured text/background contrast is {ratio}:1; minimum is {min_contrast}:1."})
    return {"width": width, "height": height, "findings": findings,
            "checks": {"alt_text": "checked", "palette": "checked" if allowed_palette else "not_configured",
                       "logo_size": "checked" if logo_bbox is not None else "not_measurable_without_logo_bbox",
                       "contrast": "checked" if foreground and background else "not_configured"}}
