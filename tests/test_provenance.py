"""Regression tests for source fidelity through the full merge pipeline."""

import json
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup
from click.testing import CliRunner

from wikifuse import render as rendering
from wikifuse.api import WikipediaClient
from wikifuse.cli import cli
from wikifuse.llm import LLMService
from wikifuse.merge import merge_article
from wikifuse.models import (
    Claim,
    Entity,
    IntermediateRepresentation,
    Provenance,
    Reference,
    Section,
)
from wikifuse.parse import parse_wikitext
from wikifuse.render import HTMLRenderer, WikitextRenderer


def fetched_articles(english, french=None):
    articles = {
        "en": {
            "wikitext": english,
            "provenance": Provenance("enwiki", "Example", 123),
        }
    }
    if french is not None:
        articles["fr"] = {
            "wikitext": french,
            "provenance": Provenance("frwiki", "Exemple", 456),
        }
    return {"entity": Entity("Q1", {"en": "Example"}), "articles": articles}


def test_merge_keeps_citations_with_passages_and_roundtrips_provenance():
    fetched = fetched_articles(
        'Born in Paris.<ref name="birth">{{cite web|title=Birth|url=https://example.org/birth}}</ref> '
        "Worked as an engineer.<ref>Career source</ref>\n\n"
        'Uncited background.\n== Family ==\nBorn in Paris.<ref name="birth"/>'
    )
    with patch("wikifuse.merge.ArticleFetcher.fetch_all", return_value=fetched):
        ir = merge_article("Q1", ["en"], use_llm=False)
    restored = IntermediateRepresentation.from_json(ir.to_json())
    claims = list(restored.content.values())
    assert [claim.text for claim in claims] == [
        "Born in Paris.",
        "Worked as an engineer.",
        "Uncited background.",
        "Born in Paris.",
    ]
    assert [[restored.references[r].title for r in c.sources] for c in claims] == [
        ["Birth"],
        ["Career source"],
        [],
        ["Birth"],
    ]
    assert claims[0].sources == claims[3].sources
    assert all(c.provenance == [Provenance("enwiki", "Example", 123)] for c in claims)
    assert len(restored.references) == 2
    rendered = WikitextRenderer().render(restored)
    assert (
        "Born in Paris.<ref>{{cite web|title=Birth|url=https://example.org/birth}}</ref>"
        in rendered
    )


def test_named_references_resolve_forward_definitions_and_groups():
    parsed = parse_wikitext(
        'First fact.<ref name="shared"/><ref name="shared" group="note"/>\n'
        '== Sources ==\n<references><ref name="shared">Main source</ref>'
        '<ref name="shared" group="note">Note source</ref></references>'
    )
    assert parsed.passages["lead"][0].references == ["Main source", "Note source"]
    assert parsed.passages["Sources"] == []


@pytest.mark.parametrize(
    "text",
    [
        'A fact.<ref name="missing"/>',
        'A fact.<ref name="x">One</ref>Another.<ref name="x">Two</ref>',
    ],
)
def test_unresolved_or_conflicting_references_fail_explicitly(text):
    with pytest.raises(ValueError, match="named reference"):
        parse_wikitext(text)


def test_nested_and_repeated_sections_do_not_duplicate_or_lose_passages():
    parsed = parse_wikitext(
        "== Career ==\nFirst job.<ref>First</ref>\n"
        "=== Awards ===\nAn award.<ref>Award</ref>\n"
        "== Career ==\nSecond job.<ref>Second</ref>"
    )
    assert [p.text for p in parsed.passages["Career"]] == ["First job.", "Second job."]
    assert [p.text for p in parsed.passages["Awards"]] == ["An award."]


def test_translated_duplicates_keep_both_revisions_and_references():
    fetched = fetched_articles(
        'Born in Paris.<ref name="x">English birth source</ref>',
        'Née à Paris.<ref name="x">French birth source</ref>',
    )
    translations = {"lead": "lead", "Née à Paris.": "Born in Paris."}
    with (
        patch("wikifuse.merge.ArticleFetcher.fetch_all", return_value=fetched),
        patch(
            "wikifuse.merge.TranslationService.translate",
            side_effect=lambda text, lang, target: (translations[text], 1.0),
        ),
    ):
        ir = merge_article("Q1", ["en", "fr"], use_llm=False)
    assert len(ir.content) == 1
    claim = next(iter(ir.content.values()))
    assert claim.text == "Born in Paris."
    assert [ir.references[r].title for r in claim.sources] == [
        "English birth source",
        "French birth source",
    ]
    assert claim.provenance == [
        Provenance("enwiki", "Example", 123),
        Provenance("frwiki", "Exemple", 456),
    ]
    assert (
        IntermediateRepresentation.from_json(ir.to_json()).content[claim.id].provenance
        == claim.provenance
    )
    attribution = rendering.render_attribution(ir)
    assert "oldid=123" in attribution and "oldid=456" in attribution
    assert "action=history" in attribution


def test_html_reference_targets_follow_first_use_and_distinguish_sources():
    references = {
        key: Reference(key, title=key) for key in ["unused", "birth", "career"]
    }
    ir = IntermediateRepresentation(
        entity=Entity("Q1"),
        sections=[Section("lead", items=["c1", "c2", "c3"])],
        content={
            "c1": Claim("c1", text="Work.", sources=["career"]),
            "c2": Claim("c2", text="Birth.", sources=["birth"]),
            "c3": Claim("c3", text="More work.", sources=["career"]),
        },
        references=references,
    )
    renderer = HTMLRenderer()
    for _ in range(2):
        soup = BeautifulSoup(renderer.render(ir), "html.parser")
        links = soup.select("sup a")
        assert [soup.select_one(link["href"]).get_text() for link in links] == [
            "career",
            "birth",
            "career",
        ]
        assert len(soup.select("ol.references li")) == 2
        ids = [element["id"] for element in soup.select("[id]")]
        assert len(ids) == len(set(ids))


def test_llm_reorders_passages_without_reassigning_citations():
    service = LLMService.__new__(LLMService)
    service._call_llm = Mock(return_value='["claim_1", "claim_0"]')
    fetched = fetched_articles(
        "Born in Paris.<ref>Birth</ref> Worked as an engineer.<ref>Career</ref>"
    )
    with (
        patch("wikifuse.merge.ArticleFetcher.fetch_all", return_value=fetched),
        patch("wikifuse.llm.LLMService", return_value=service),
    ):
        ir = merge_article("Q1", ["en"], llm_api_key="test-key")
    claims = [ir.content[key] for key in ir.sections[0].items]
    assert [c.text for c in claims] == ["Worked as an engineer.", "Born in Paris."]
    assert [[ir.references[r].title for r in c.sources] for c in claims] == [
        ["Career"],
        ["Birth"],
    ]
    assert all(c.provenance == [Provenance("enwiki", "Example", 123)] for c in claims)


@pytest.mark.parametrize(
    "response",
    [
        '["a"]',
        '["a", "a"]',
        '["a", "invented"]',
        '{"a": 1}',
        "not JSON",
        '[{}, "b"]',
    ],
)
def test_invalid_llm_order_preserves_all_original_passages(response):
    service = LLMService.__new__(LLMService)
    service._call_llm = Mock(return_value=response)
    claims = [
        Claim("a", text="First.", sources=["r1"]),
        Claim("b", text="Second.", sources=["r2"]),
    ]
    assert service.order_claims(claims, "Example", "lead") == claims


def test_fetch_content_is_pinned_to_recorded_revision():
    client = WikipediaClient()
    info = {
        "query": {
            "pages": {
                "42": {
                    "revisions": [{"revid": 123, "timestamp": "2026-01-01T00:00:00Z"}]
                }
            }
        }
    }
    content = {
        "query": {
            "pages": {
                "42": {"revisions": [{"slots": {"main": {"*": "Pinned content."}}}]}
            }
        }
    }
    client.session.get = Mock(
        side_effect=[Mock(json=lambda: info), Mock(json=lambda: content)]
    )
    article = client.get_article_wikitext("Example", "en")
    params = client.session.get.call_args_list[1].kwargs["params"]
    assert params["revids"] == 123
    assert "pageids" not in params
    assert article["provenance"].rev_id == 123
    assert article["wikitext"] == "Pinned content."


def test_merge_cli_writes_attribution_next_to_ir(tmp_path):
    with patch(
        "wikifuse.merge.ArticleFetcher.fetch_all",
        return_value=fetched_articles("An uncited fact."),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "merge",
                "--qid",
                "Q1",
                "--languages",
                "en",
                "--no-llm",
                "--out",
                str(tmp_path),
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / "wikifuse.ir.json").read_text())
    assert next(iter(data["content"].values()))["provenance"][0]["rev_id"] == 123
    assert "oldid=123" in (tmp_path / "ATTRIBUTION.md").read_text()


def test_citation_before_punctuation_stays_with_its_passage():
    parsed = parse_wikitext(
        "Born in Paris<ref>Birth</ref>. Worked as an engineer<ref>Career</ref>."
    )
    assert [(p.text, p.references) for p in parsed.passages["lead"]] == [
        ("Born in Paris.", ["Birth"]),
        ("Worked as an engineer.", ["Career"]),
    ]


@pytest.mark.parametrize(
    "text", ["<ref>Orphan</ref> A fact.", "An uncited fact.\n\n<ref>Orphan</ref>"]
)
def test_orphan_references_are_not_assigned_to_unrelated_text(text):
    with pytest.raises(ValueError, match="no preceding passage"):
        parse_wikitext(text)


def test_named_reference_inherits_reference_list_group():
    parsed = parse_wikitext(
        'A fact.<ref name="x" group="note"/>\n== Notes ==\n'
        '<references group="note"><ref name="x">Note source</ref></references>'
    )
    assert parsed.passages["lead"][0].references == ["Note source"]
