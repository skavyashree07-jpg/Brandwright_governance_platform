from dataclasses import dataclass, asdict
from pathlib import Path
import io

@dataclass
class Segment:
    text: str
    start: int
    end: int
    page: int | None = None

@dataclass
class Extraction:
    text: str
    segments: list[Segment]
    filename: str | None
    media_type: str
    warnings: list[str]

    def to_dict(self):
        return {"text": self.text, "segments": [asdict(x) for x in self.segments],
                "filename": self.filename, "media_type": self.media_type, "warnings": self.warnings}

def _assemble(parts, filename, media_type):
    text_parts, segments, offset = [], [], 0
    for value, page in parts:
        value = value or ""
        if not value.strip():
            continue
        if text_parts:
            text_parts.append("\n")
            offset += 1
        start = offset
        text_parts.append(value)
        offset += len(value)
        segments.append(Segment(value, start, offset, page))
    return Extraction("".join(text_parts), segments, filename, media_type, [])

def extract_text(text: str, filename=None):
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _assemble([(text, None)], filename, "text/plain")

def _read(file, filename):
    if isinstance(file, bytes):
        return file, filename
    if isinstance(file, (str, Path)):
        p = Path(file)
        return p.read_bytes(), filename or p.name
    if hasattr(file, "read"):
        return file.read(), filename or getattr(file, "name", None)
    raise TypeError("Expected bytes, path, or binary file")

def extract_file(file, filename=None):
    data, name = _read(file, filename)
    suffix = Path(name or "").suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        if isinstance(data, str): return extract_text(data, name)
        return extract_text(data.decode("utf-8-sig", errors="replace"), name)
    if suffix == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # DOCX page layout is not reliably exposed by python-docx; page is null.
        return _assemble([("\n".join(paragraphs), None)], name,
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if suffix == ".pdf":
        import fitz
        with fitz.open(stream=data, filetype="pdf") as pdf:
            result = _assemble([(page.get_text("text"), i + 1) for i, page in enumerate(pdf)],
                               name, "application/pdf")
        if not result.text.strip():
            result.warnings.append("No selectable text found; scanned PDF may require OCR.")
        return result
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        from PIL import Image
        import pytesseract
        text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
        return _assemble([(text, 1)], name, "image/ocr")
    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")
