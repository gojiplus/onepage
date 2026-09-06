"""Treat article and comparison content as text at every HTML boundary."""

from urllib.parse import unquote, urlsplit

import pytest
from bs4 import BeautifulSoup

from wikifuse.diff import (
    ArticleStats,
    ComparisonResult,
    SectionDiff,
    generate_diff_html,
)
from wikifuse.models import (
    Claim,
    Entity,
    IntermediateRepresentation,
    Reference,
    Section,
)
from wikifuse.render import HTMLRenderer

PAYLOAD = '"><img src=x onerror=alert(1)><script>alert(2)</script>& "quoted"'


def assert_no_injected_markup(soup):
    assert not soup.select("script, iframe, object, embed, svg")
    for element in soup.find_all(True):
        assert not any(name.lower().startswith("on") for name in element.attrs)
    assert not soup.select('img[src="x"]')


def test_article_text_metadata_and_image_names_are_escaped():
    ir = IntermediateRepresentation(
        entity=Entity("Q1", {"en": PAYLOAD}),
        sections=[
            Section("lead", items=["c"]),
            Section("other", title={"en": PAYLOAD}, items=[]),
        ],
        content={"c": Claim("c", text=PAYLOAD, sources=["r"])},
        references={
            "r": Reference(
                "r",
                title=PAYLOAD,
                author=PAYLOAD,
                publisher=PAYLOAD,
                date=PAYLOAD,
                doi=PAYLOAD,
                url='https://example.org/?x="quoted"&y=1',
            )
        },
        metadata={"infobox": {PAYLOAD: [PAYLOAD]}, "images": ["File:" + PAYLOAD]},
    )
    soup = BeautifulSoup(HTMLRenderer().render(ir), "html.parser")
    assert_no_injected_markup(soup)
    assert soup.h1.get_text() == PAYLOAD
    assert soup.h2.get_text() == PAYLOAD
    assert soup.select_one(".infobox th").get_text() == PAYLOAD
    assert soup.select_one(".infobox td").get_text() == PAYLOAD
    assert PAYLOAD in soup.select_one("cite").get_text()
    image = soup.select_one("img")
    assert image["alt"] == PAYLOAD
    assert urlsplit(image["src"]).hostname == "commons.wikimedia.org"
    assert unquote(urlsplit(image["src"]).path).endswith(PAYLOAD)
    assert urlsplit(image["src"]).query == "width=300"
    assert (
        soup.select_one("a.external")["href"] == 'https://example.org/?x="quoted"&y=1'
    )


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "//example.org/path",
        "/relative",
        "https://",
        "https://[bad",
        "https://example.org:invalid",
        "https://example.org:70000",
        "https://example.org:0",
        "java\nscript:alert(1)",
        "\x00javascript:alert(1)",
        "https://example.org/\r\npath",
        "https:\\evil.org",
    ],
)
def test_unsafe_reference_urls_are_plain_text(url):
    ir = IntermediateRepresentation(
        entity=Entity("Q1"),
        sections=[Section("lead", items=["c"])],
        content={"c": Claim("c", text="Statement.", sources=["r"])},
        references={"r": Reference("r", title="Source", url=url)},
    )
    soup = BeautifulSoup(HTMLRenderer().render(ir), "html.parser")
    assert_no_injected_markup(soup)
    assert soup.select_one("cite").get_text() == "Source"
    assert not soup.select("cite a")
    assert soup.select_one("sup a")["href"] == "#cite_note-1"


@pytest.mark.parametrize(
    "url",
    ["http://example.org/path", "https://example.org/?a=1&b=2", "https://[::1]:443/a"],
)
def test_absolute_http_links_are_preserved(url):
    rendered = HTMLRenderer()._format_reference(Reference("r", title="A & B", url=url))
    link = BeautifulSoup(rendered, "html.parser").a
    assert link["href"] == url
    assert link.get_text() == "A & B"


def test_comparison_escapes_all_external_text(tmp_path):
    comparison = ComparisonResult(
        qid=PAYLOAD,
        entity_name=PAYLOAD,
        base_lang=PAYLOAD,
        compare_langs=[PAYLOAD],
        base_stats=ArticleStats(),
        merged_stats=ArticleStats(),
        new_sections=[PAYLOAD],
        section_diffs={
            "s": SectionDiff(PAYLOAD, base_text=PAYLOAD, merged_text=PAYLOAD)
        },
    )
    path = tmp_path / "diff.html"
    generate_diff_html(comparison, str(path))
    soup = BeautifulSoup(path.read_text(), "html.parser")
    assert_no_injected_markup(soup)
    assert soup.select_one(".base-content p").get_text() == PAYLOAD
    assert soup.select_one(".merged-content p").get_text() == PAYLOAD
    assert soup.select_one(".new-sections li").get_text() == PAYLOAD
    assert PAYLOAD in soup.h1.get_text()


def test_renderer_language_attribute_is_escaped():
    ir = IntermediateRepresentation(Entity("Q1"))
    soup = BeautifulSoup(HTMLRenderer(PAYLOAD).render(ir), "html.parser")
    assert_no_injected_markup(soup)
    assert soup.html["lang"] == PAYLOAD
