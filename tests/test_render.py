import pytest

from onepage.models import Entity, Claim, Section, IntermediateRepresentation, Reference
from onepage.render import HTMLRenderer


def test_html_renderer_basic():
    entity = Entity(qid="Q1058", labels={"en": "Narendra Modi"})
    claim = Claim(id="c1", text="Narendra Modi is the Prime Minister of India.")
    section = Section(id="lead", items=["c1"])
    ir = IntermediateRepresentation(entity=entity, sections=[section], content={"c1": claim})

    renderer = HTMLRenderer("en")
    html = renderer.render(ir)

    assert "<html>" in html
    assert "Narendra Modi is the Prime Minister of India." in html
    assert "<h1" in html and "Narendra Modi</h1>" in html


def test_html_renderer_references():
    entity = Entity(qid="Q1", labels={"en": "Test"})
    claim = Claim(id="c1", text="Statement.", sources=["r1"])
    section = Section(id="lead", items=["c1"])
    ref = Reference(id="r1", title="Example", url="https://example.com", author="Author", date="2020")
    ir = IntermediateRepresentation(
        entity=entity,
        sections=[section],
        content={"c1": claim},
        references={"r1": ref},
    )

    renderer = HTMLRenderer("en")
    html = renderer.render(ir)

    assert "[1]" in html
    assert "<ol class=\"references\">" in html
    assert "https://example.com" in html
