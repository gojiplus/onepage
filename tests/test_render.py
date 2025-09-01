import pytest

from onepage.models import Entity, Claim, Section, IntermediateRepresentation
from onepage.render import HTMLRenderer


def test_html_renderer_basic():
    entity = Entity(qid="Q1058", labels={"en": "Narendra Modi"})
    claim = Claim(id="c1", text="Narendra Modi is the Prime Minister of India.")
    section = Section(id="lead", items=["c1"])
    ir = IntermediateRepresentation(entity=entity, sections=[section], content={"c1": claim})

    renderer = HTMLRenderer("en")
    html = renderer.render(ir)

    assert "<html>" in html
    assert "<h1>Narendra Modi</h1>" in html
    assert "Narendra Modi is the Prime Minister of India." in html
