import shutil
import pytest

from onepage import HTMLRenderer, IntermediateRepresentation, Claim, Entity, Section


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_html_renderer_basic():
    entity = Entity(qid="Q1", labels={"en": "Test"})
    claim = Claim(id="c1", text="Hello world.")
    section = Section(id="lead", items=["c1"])
    ir = IntermediateRepresentation(entity=entity, sections=[section], content={"c1": claim})

    renderer = HTMLRenderer("en")
    html = renderer.render(ir)

    assert "Hello world." in html
    assert "<html" in html.lower()
