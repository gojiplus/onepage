"""Tests for the command line interface."""

from click.testing import CliRunner

from onepage.cli import cli


def test_fetch_command(monkeypatch, tmp_path):
    """Fetch command should invoke ArticleFetcher and output messages."""
    captured = {}

    class DummyFetcher:
        def fetch_all(self, qid, languages, out):
            captured["args"] = (qid, languages, out)

    # Replace ArticleFetcher with dummy implementation
    monkeypatch.setattr("onepage.cli.ArticleFetcher", DummyFetcher)

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
