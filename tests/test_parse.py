"""Tests for wikitext parsing utilities."""

from onepage.parse import parse_wikitext


def test_parse_wikitext_basic():
    """Parse sample wikitext into structured components."""
    wikitext = """
Lead.

{{Infobox person
| name = Jane Doe
| occupation = Tester
}}
== Biography ==
Some content with an [[File:Example.jpg|thumb]] image.
<ref>Example reference</ref>
"""

    parsed = parse_wikitext(wikitext)

    # Sections should include lead and Biography
    assert parsed.sections["lead"].startswith("Lead.")
    assert "Biography" in parsed.sections

    # Image links should be captured
    assert parsed.images == ["File:Example.jpg"]

    # Infobox values should be parsed
    assert parsed.infobox["name"] == "Jane Doe"

    # References should be collected
    assert "Example reference" in parsed.references
