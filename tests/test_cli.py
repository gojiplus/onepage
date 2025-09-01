"""Tests for the command line interface."""

from click.testing import CliRunner

from onepage.cli import cli
from onepage.api import ArticleFetcher


def test_fetch_command(monkeypatch, tmp_path):
    """Fetch command should invoke ArticleFetcher and output messages."""
    captured = {}

    def mock_fetch_all(self, qid, languages, out):
        captured["args"] = (qid, languages, out)
        captured["self"] = self

    # Patch ArticleFetcher.fetch_all to avoid network calls but keep real class
    monkeypatch.setattr("onepage.cli.ArticleFetcher.fetch_all", mock_fetch_all)

    runner = CliRunner()
    out_dir = tmp_path / "data"
    result = runner.invoke(
        cli,
        ["fetch", "--qid", "Q1", "--languages", "en,hi", "--out", str(out_dir)],
    )

    assert result.exit_code == 0
    assert "Fetching articles for Q1 in languages: en, hi" in result.output
    assert "Results written to" in result.output
    assert captured["args"] == ("Q1", ["en", "hi"], str(out_dir))
    assert isinstance(captured["self"], ArticleFetcher)
