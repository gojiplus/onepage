"""Tests for merge utilities."""

from onepage.translate import TextCleaner
from onepage.merge import TextMerger


def test_extract_plain_text_strips_markup() -> None:
    wikitext = "Hello [[World]]! This is {{template|value}}.<ref>r</ref>"
    assert TextCleaner.extract_plain_text(wikitext) == "Hello World! This is."


def test_text_merger_cleans_sections() -> None:
    sections = {"Intro": "Hello [[World]]! This is {{template|value}}.<ref>r</ref>"}
    merged = TextMerger.merge([("en", sections)])
    assert merged["Intro"] == "Hello World! This is."
