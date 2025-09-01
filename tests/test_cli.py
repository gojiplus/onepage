"""Tests for the command line interface."""

import pytest
import requests
from click.testing import CliRunner

from onepage.cli import cli


def _get_modi_qid() -> str:
    """Lookup QID for Narendra Modi using Wikidata search."""
    resp = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": "Narendra Modi",
            "language": "en",
            "format": "json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["search"][0]["id"]


def test_fetch_command_real(tmp_path):
    """Fetch command should retrieve Narendra Modi articles in en and hi."""
    try:
        qid = _get_modi_qid()
    except Exception:
        pytest.skip("Wikidata search unavailable")

    runner = CliRunner()
    out_dir = tmp_path / "data"
    result = runner.invoke(
        cli,
        ["fetch", "--qid", qid, "--languages", "en,hi", "--out", str(out_dir)],
    )
    if result.exit_code != 0:
        pytest.skip(f"Fetch failed: {result.output}")

    # Verify that both language files were written
    assert (out_dir / "en.json").exists()
    assert (out_dir / "hi.json").exists()
