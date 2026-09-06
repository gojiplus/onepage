"""Comparisons must share a source snapshot and support offline replay."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from wikifuse import diff, merge
from wikifuse.cli import cli
from wikifuse.models import Entity, IntermediateRepresentation, Provenance, Section


def sources():
    return {
        "entity": Entity("Q1", {"en": "Example"}),
        "articles": {
            "en": {
                "wikitext": "Born in Paris.<ref>Birth</ref>\n== Work ==\nWorked as an engineer.",
                "provenance": Provenance("enwiki", "Example", 100),
            },
            "fr": {
                "wikitext": "Born in Paris.<ref>Naissance</ref>\n== Awards ==\nReceived an award.<ref>Award</ref>",
                "provenance": Provenance("frwiki", "Exemple", 200),
            },
        },
    }


@pytest.fixture
def fetch(monkeypatch):
    mocked = Mock(return_value=sources())
    monkeypatch.setattr("wikifuse.api.ArticleFetcher.fetch_all", mocked)
    monkeypatch.setattr(
        "wikifuse.merge.TranslationService.translate",
        lambda self, text, source, target: (text, None),
    )
    return mocked


def test_comparison_fetches_once_and_retains_the_same_source_revision(fetch, tmp_path):
    comparison = diff.compare_articles(
        "Q1", "en", ["fr", "fr"], use_llm=False, output_dir=str(tmp_path)
    )
    fetch.assert_called_once()
    assert fetch.call_args.args == ("Q1", ["en", "fr"])
    assert not Path(fetch.call_args.kwargs["output_dir"]).exists()
    assert comparison.compare_langs == ["en", "fr"]
    base_claim = next(iter(comparison.base_ir.content.values()))
    merged_claim = next(iter(comparison.merged_ir.content.values()))
    assert base_claim.provenance[0] in merged_claim.provenance
    assert base_claim.provenance[0].rev_id == 100
    assert list(comparison.section_diffs) == ["lead", "Work", "Awards"]
    assert (
        json.loads((tmp_path / "sources.json").read_text())["articles"]["en"][
            "provenance"
        ]["rev_id"]
        == 100
    )
    assert (
        json.loads((tmp_path / "base.ir.json").read_text())
        == comparison.base_ir.to_dict()
    )
    assert (
        json.loads((tmp_path / "merged.ir.json").read_text())
        == comparison.merged_ir.to_dict()
    )
    assert "oldid=200" in (tmp_path / "ATTRIBUTION.md").read_text()


def test_saved_comparison_replays_identically_without_network(
    fetch, monkeypatch, tmp_path
):
    original = diff.compare_articles(
        "Q1", "en", ["en", "fr"], use_llm=False, output_dir=str(tmp_path)
    )
    first = tmp_path / "first.html"
    diff.generate_diff_html(original, str(first))
    monkeypatch.setattr(
        "requests.Session.request",
        Mock(side_effect=AssertionError("Network forbidden during replay")),
    )
    replay = tmp_path / "replayed.html"
    result = CliRunner().invoke(
        cli,
        [
            "diff-preview",
            "--comparison",
            str(tmp_path / "comparison.json"),
            "--out",
            str(replay),
        ],
    )
    assert result.exit_code == 0, result.output
    assert replay.read_bytes() == first.read_bytes()
    fetch.assert_called_once()


def test_failed_comparison_does_not_replace_snapshot_or_outputs(fetch, tmp_path):
    prior = tmp_path / "sources.json"
    prior.write_text("previous snapshot")
    fetch.return_value["articles"].pop("fr")
    with pytest.raises(ValueError, match="Missing requested source articles: fr"):
        diff.compare_articles(
            "Q1", "en", ["fr"], use_llm=False, output_dir=str(tmp_path)
        )
    assert prior.read_text() == "previous snapshot"
    assert not (tmp_path / "comparison.json").exists()


def test_empty_comparison_fails_before_fetching(fetch):
    with pytest.raises(ValueError, match="comparison language"):
        diff.compare_articles("Q1", "en", [], use_llm=False)
    fetch.assert_not_called()


def test_merge_article_uses_an_isolated_temporary_directory(
    fetch, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    merge.merge_article("Q1", ["en"], use_llm=False)
    output_dir = fetch.call_args.kwargs["output_dir"]
    assert output_dir != "./tmp"
    assert not Path(output_dir).exists()
    assert not (tmp_path / "tmp").exists()


def test_mismatched_entities_are_rejected():
    with pytest.raises(ValueError, match="same QID"):
        diff.compare_irs(
            IntermediateRepresentation(Entity("Q1")),
            IntermediateRepresentation(Entity("Q2")),
            "en",
            ["en"],
        )


def test_section_order_uses_base_order_then_new_sections():
    base = IntermediateRepresentation(
        Entity("Q1"), sections=[Section("z"), Section("a")]
    )
    merged = IntermediateRepresentation(
        Entity("Q1"), sections=[Section("new"), Section("a"), Section("z")]
    )
    result = diff.compare_irs(base, merged, "en", ["en"])
    assert list(result.section_diffs) == ["z", "a", "new"]


def test_diff_cli_saves_replay_artifacts(fetch, tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "diff",
            "--qid",
            "Q1",
            "--compare",
            "en,fr",
            "--out",
            str(tmp_path),
            "--no-llm",
        ],
    )
    assert result.exit_code == 0, result.output
    assert {p.name for p in tmp_path.iterdir()} == {
        "sources.json",
        "base.ir.json",
        "merged.ir.json",
        "comparison.json",
        "ATTRIBUTION.md",
        "diff.html",
    }
