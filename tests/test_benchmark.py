"""Check benchmark execution and sensitivity to damaged output."""

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest

from benchmarks.run import FIXTURE, evaluate, merge_case, score


@pytest.fixture
def cases(monkeypatch):
    monkeypatch.setattr(
        "requests.Session.request",
        Mock(side_effect=AssertionError("Network forbidden")),
    )
    return json.loads(FIXTURE.read_bytes())["cases"]


def test_reference_benchmark_runs_offline_and_matches_saved_report(cases):
    report = evaluate()
    assert report == json.loads(FIXTURE.with_name("reference-report.json").read_bytes())
    assert [row["merged"]["facts_retained"] for row in report["cases"]] == [4, 4, 2]
    assert [row["base"]["facts_retained"] for row in report["cases"]] == [1, 1, 1]
    assert (
        sum(row["merged"]["traceable_citation_links"] for row in report["cases"]) == 7
    )


def test_missing_unique_fact_reduces_recall(cases):
    case = cases[1]
    ir = merge_case(case, ["en", "fr", "es"])
    ir.sections[0].items.remove("claim_2")
    assert score(case, ir)["facts_retained"] == 2


def test_duplicate_output_increases_duplicate_count(cases):
    case = cases[1]
    ir = merge_case(case, ["en", "fr", "es"])
    ir.content["duplicate"] = deepcopy(ir.content["claim_0"])
    ir.content["duplicate"].id = "duplicate"
    ir.sections[0].items.append("duplicate")
    assert score(case, ir)["duplicate_fact_mentions"] == 1


def test_wrong_citation_is_not_traceable(cases):
    case = cases[1]
    ir = merge_case(case, ["en", "fr", "es"])
    ir.content["claim_0"].sources = ir.content["claim_2"].sources.copy()
    result = score(case, ir)
    assert result["citation_links"] == 3
    assert result["traceable_citation_links"] == 2
    assert result["cited_fact_mentions_missing_citations"] == 1


def test_dropped_citation_is_detected(cases):
    case = cases[1]
    ir = merge_case(case, ["en", "fr", "es"])
    ir.content["claim_0"].sources.clear()
    assert score(case, ir)["cited_fact_mentions_missing_citations"] == 1


def test_conflict_requires_both_distinct_passages(cases):
    case = cases[2]
    ir = merge_case(case, ["en", "fr"])
    assert score(case, ir)["conflict_pairs_preserved"] == 1
    ir.sections[0].items.remove("claim_1")
    assert score(case, ir)["conflict_pairs_preserved"] == 0
