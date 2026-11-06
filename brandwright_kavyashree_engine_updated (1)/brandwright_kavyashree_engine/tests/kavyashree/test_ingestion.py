import pytest
from app.review.ingestion import extract_text, extract_file

def test_text_offsets():
    r=extract_text("Hello brand")
    assert r.text=="Hello brand" and r.segments[0].start==0 and r.segments[0].end==11

def test_txt_file(tmp_path):
    p=tmp_path/"x.txt"; p.write_text("Brandwright",encoding="utf-8")
    assert extract_file(p).text=="Brandwright"

def test_unsupported():
    with pytest.raises(ValueError): extract_file(b"x","bad.exe")
