import pytest
from app.signal_listener import parse_message


def test_parse_text_message():
    result = parse_message("123456 hello world", attachments=[])
    assert result["totp"] == "123456"
    assert result["body"] == "hello world"
    assert result["content_type"] == "text"


def test_parse_code_only_no_body():
    result = parse_message("123456", attachments=[])
    assert result["totp"] == "123456"
    assert result["body"] is None
    assert result["content_type"] == "text"


def test_parse_attachment_with_caption():
    result = parse_message("123456 my caption", attachments=[{"content_type": "image/jpeg", "filename": "photo.jpg"}])
    assert result["totp"] == "123456"
    assert result["body"] == "my caption"
    assert result["content_type"] == "image"


def test_parse_attachment_no_caption():
    result = parse_message("123456", attachments=[{"content_type": "video/mp4", "filename": "clip.mp4"}])
    assert result["body"] is None
    assert result["content_type"] == "video"


def test_parse_link_message():
    result = parse_message("123456 https://example.com/article", attachments=[])
    assert result["content_type"] == "link"
    assert result["body"] == "https://example.com/article"


def test_short_code_rejected():
    result = parse_message("12345 hello", attachments=[])
    assert result is None


def test_missing_code_rejected():
    result = parse_message("hello world", attachments=[])
    assert result is None
