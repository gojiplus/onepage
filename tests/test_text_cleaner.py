import pytest
from onepage.translate import TextCleaner


def test_extract_plain_text_handles_templates_and_refs():
    wikitext = "Start {{temp|1}} middle {{temp2|a=b}} end <ref>ref</ref>"
    cleaned = TextCleaner.extract_plain_text(wikitext)
    assert cleaned == "Start middle end"
