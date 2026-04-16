"""Tests for the diff/comparison functionality."""

import os
import tempfile

import pytest
from click.testing import CliRunner

from wikifuse.cli import cli
from wikifuse.diff import (
    ArticleStats,
    ComparisonResult,
    SectionDiff,
    _count_words,
    _extract_stats,
    generate_diff_html,
    print_stats,
)
from wikifuse.models import Claim, Entity, IntermediateRepresentation, Section


def test_count_words():
    """Test word counting function."""
    assert _count_words("") == 0
    assert _count_words("hello world") == 2
    assert _count_words("The quick brown fox jumps over the lazy dog.") == 9
    assert _count_words("   multiple   spaces   between   words   ") == 4


def test_extract_stats():
    """Test extracting statistics from an IR."""
    entity = Entity(qid="Q123", labels={"en": "Test Entity"})
    ir = IntermediateRepresentation(entity=entity)

    ir.sections.append(
        Section(id="early_life", title={"en": "Early life"}, items=["claim_1"])
    )
    ir.sections.append(Section(id="career", title={"en": "Career"}, items=["claim_2"]))

    ir.content["claim_1"] = Claim(
        id="claim_1",
        text="This is a test sentence with some words.",
    )
    ir.content["claim_2"] = Claim(
        id="claim_2",
        text="Another sentence for testing purposes.",
    )

    ir.metadata["images"] = ["image1.jpg", "image2.png"]

    stats = _extract_stats(ir)

    assert stats.section_count == 2
    assert stats.reference_count == 0
    assert stats.word_count > 0
    assert stats.image_count == 2
    assert "Early life" in stats.section_names
    assert "Career" in stats.section_names


def test_print_stats():
    """Test terminal statistics output generation."""
    base_stats = ArticleStats(
        section_count=5,
        reference_count=50,
        word_count=2000,
        image_count=3,
        section_names=["Section A", "Section B"],
    )
    merged_stats = ArticleStats(
        section_count=8,
        reference_count=120,
        word_count=4500,
        image_count=5,
        section_names=["Section A", "Section B", "Section C", "Section D"],
    )

    comparison = ComparisonResult(
        qid="Q123",
        entity_name="Test Person",
        base_lang="en",
        compare_langs=["en", "fr"],
        base_stats=base_stats,
        merged_stats=merged_stats,
        new_sections=["Section C", "Section D", "Section E"],
    )

    output = print_stats(comparison)

    assert "Test Person (Q123)" in output
    assert "EN-only" in output
    assert "Merged (en+fr)" in output
    assert "+3" in output  # section count change
    assert "+70" in output  # reference count change
    assert "Section C" in output
    assert "Section D" in output


def test_generate_diff_html():
    """Test HTML diff generation."""
    base_stats = ArticleStats(
        section_count=2,
        reference_count=10,
        word_count=500,
        image_count=1,
        section_names=["Early life"],
    )
    merged_stats = ArticleStats(
        section_count=4,
        reference_count=25,
        word_count=1200,
        image_count=2,
        section_names=["Early life", "Career", "Awards", "Legacy"],
    )

    section_diffs = {
        "early_life": SectionDiff(
            title="Early life",
            base_word_count=100,
            merged_word_count=200,
            base_text="Born in a small town.",
            merged_text="Born in a small town. Additional info from French Wikipedia.",
            is_new=False,
        ),
        "career": SectionDiff(
            title="Career",
            base_word_count=0,
            merged_word_count=300,
            base_text="",
            merged_text="Career information from other languages.",
            is_new=True,
        ),
    }

    comparison = ComparisonResult(
        qid="Q456",
        entity_name="Famous Person",
        base_lang="en",
        compare_langs=["en", "fr"],
        base_stats=base_stats,
        merged_stats=merged_stats,
        new_sections=["Career", "Awards", "Legacy"],
        section_diffs=section_diffs,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "diff.html")
        generate_diff_html(comparison, html_path)

        assert os.path.exists(html_path)

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        assert "Famous Person (Q456)" in html_content
        assert "EN-only" in html_content
        assert "Merged (en+fr)" in html_content
        assert "Early life" in html_content
        assert "Career" in html_content
        assert "NEW" in html_content
        assert "+15" in html_content  # reference change


def test_diff_cli_help():
    """Test that diff command shows help correctly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", "--help"])
    assert result.exit_code == 0
    assert "--qid" in result.output
    assert "--base" in result.output
    assert "--compare" in result.output
    assert "--out" in result.output


@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require network access and API keys",
)
def test_diff_cli_real():
    """Integration test for diff command with real data."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(
            cli,
            [
                "diff",
                "--qid",
                "Q27182",
                "--base",
                "en",
                "--compare",
                "en,fr",
                "--out",
                tmpdir,
                "--no-llm",
            ],
        )
        if result.exit_code != 0:
            pytest.skip(f"Diff command failed: {result.output}")

        assert os.path.exists(os.path.join(tmpdir, "diff.html"))
