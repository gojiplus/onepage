"""Tests for merge utilities."""

from wikifuse.llm import MockLLMService
from wikifuse.merge import ImageMerger, InfoboxMerger, TextMerger
from wikifuse.translate import TextCleaner


def test_extract_plain_text_strips_markup() -> None:
    wikitext = "Hello [[World]]! This is {{template|value}}.<ref>r</ref>"
    assert TextCleaner.extract_plain_text(wikitext) == "Hello World! This is."


def test_text_merger_cleans_sections() -> None:
    sections = {"Intro": "Hello [[World]]! This is {{template|value}}.<ref>r</ref>"}
    merger = TextMerger()
    merged = merger.merge([("en", sections)])
    assert merged["Intro"] == "Hello World! This is."


def test_text_merger_with_llm() -> None:
    """Test text merger with mock LLM service."""
    mock_llm = MockLLMService()
    merger = TextMerger(llm_service=mock_llm, entity_name="Test Entity")
    sections = {"Intro": "Hello World! This is a test."}
    merged = merger.merge([("en", sections)])
    assert "Hello World" in merged["Intro"]


def test_text_merger_static_backward_compat() -> None:
    """Test static merge method for backward compatibility."""
    sections = {"Intro": "Hello [[World]]! This is {{template|value}}.<ref>r</ref>"}
    merged = TextMerger.merge_static([("en", sections)])
    assert merged["Intro"] == "Hello World! This is."


def test_image_merger_union() -> None:
    """Test image merger unions images from multiple articles."""
    images1 = ["File:Image1.jpg", "File:Image2.jpg"]
    images2 = ["File:Image2.jpg", "File:Image3.jpg"]
    merged = ImageMerger.merge([images1, images2])
    assert len(merged) == 3
    assert "File:Image1.jpg" in merged
    assert "File:Image2.jpg" in merged
    assert "File:Image3.jpg" in merged


def test_image_merger_preserves_order() -> None:
    """Test image merger preserves order."""
    images1 = ["File:A.jpg", "File:B.jpg"]
    images2 = ["File:C.jpg"]
    merged = ImageMerger.merge([images1, images2])
    assert merged == ["File:A.jpg", "File:B.jpg", "File:C.jpg"]


def test_infobox_merger_union() -> None:
    """Test infobox merger unions parameters."""
    box1 = {"name": "Test", "born": "1990"}
    box2 = {"name": "Test", "occupation": "Engineer"}
    merged = InfoboxMerger.merge([box1, box2])
    assert "name" in merged
    assert "born" in merged
    assert "occupation" in merged
    assert merged["name"] == ["Test"]
    assert merged["born"] == ["1990"]
    assert merged["occupation"] == ["Engineer"]


def test_infobox_merger_multiple_values() -> None:
    """Test infobox merger handles multiple values for same key."""
    box1 = {"name": "Test1"}
    box2 = {"name": "Test2"}
    merged = InfoboxMerger.merge([box1, box2])
    assert merged["name"] == ["Test1", "Test2"]
