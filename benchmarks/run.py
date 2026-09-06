"""Evaluate pinned excerpts with reference or live translations."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from wikifuse.merge import merge_fetched
from wikifuse.models import Claim, Entity, Provenance
from wikifuse.translate import TranslationService

FIXTURE = Path(__file__).with_name("cases.json")


class ReferenceTranslator:
    """Use explicit reference renderings; reject unrecognized parser output."""

    def __init__(self, articles):
        self.translations = {
            (article["language"], article["reference_text"], "en"): article[
                "translation"
            ]
            for article in articles
            if article["translation"] is not None
        }

    def translate(self, text, source, target):
        return self.translations[source, text, target], None


def merge_case(case, languages, live=False):
    """Run the production parser and merger on captured source excerpts."""
    fetched = {
        "entity": Entity(case["qid"], {"en": case["label"]}),
        "articles": {
            article["language"]: {
                "wikitext": article["wikitext"],
                "provenance": Provenance(
                    article["language"] + "wiki",
                    article["title"],
                    article["revision"],
                ),
            }
            for article in case["articles"]
        },
    }
    translator = TranslationService() if live else ReferenceTranslator(case["articles"])
    return merge_fetched(fetched, languages, use_llm=False, translator=translator)


def score(case, ir):
    """Count labeled facts and trace citations at the output passage level."""
    claims = {
        item_id: ir.content[item_id]
        for section in ir.sections
        for item_id in section.items
        if isinstance(ir.content[item_id], Claim)
    }
    matches = {
        fact["id"]: {
            key
            for key, claim in claims.items()
            if re.search(fact["pattern"], claim.text, re.IGNORECASE)
        }
        for fact in case["facts"]
    }
    citation_links = 0
    verified_links = 0
    missing_links = 0
    unmatched_passages = 0
    for key, claim in claims.items():
        facts = [fact for fact in case["facts"] if key in matches[fact["id"]]]
        unmatched_passages += not facts
        allowed = {raw for fact in facts for raw in fact["allowed_citations"]}
        actual = {
            ir.references[ref].wikitext if ref in ir.references else None
            for ref in claim.sources
        }
        citation_links += len(claim.sources)
        verified_links += sum(
            ref in ir.references and ir.references[ref].wikitext in allowed
            for ref in claim.sources
        )
        missing_links += sum(
            bool(fact["allowed_citations"])
            and not actual.intersection(fact["allowed_citations"])
            for fact in facts
        )
    return {
        "facts_total": len(matches),
        "facts_retained": sum(bool(ids) for ids in matches.values()),
        "duplicate_fact_mentions": sum(
            max(0, len(ids) - 1) for ids in matches.values()
        ),
        "citation_links": citation_links,
        "traceable_citation_links": verified_links,
        "cited_fact_mentions_missing_citations": missing_links,
        "unmatched_passages": unmatched_passages,
        "conflict_pairs_total": len(case["conflicts"]),
        "conflict_pairs_preserved": sum(
            any(a != b for a in matches[left] for b in matches[right])
            for left, right in case["conflicts"]
        ),
        "fact_passages": {key: sorted(ids) for key, ids in matches.items()},
    }


def evaluate(live=False):
    """Return metrics and inspectable outputs for every fixture case."""
    raw = FIXTURE.read_bytes()
    cases = json.loads(raw)["cases"]
    results = []
    for case in cases:
        base = merge_case(case, ["en"], live=live)
        merged = merge_case(
            case, [article["language"] for article in case["articles"]], live=live
        )
        results.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "base": score(case, base),
                "merged": score(case, merged),
                "base_ir": base.to_dict(),
                "merged_ir": merged.to_dict(),
            }
        )
    return {
        "schema_version": 1,
        "translation_mode": "live" if live else "reference",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": results,
    }


def main():
    """Write an evaluation report without modifying the captured inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    report = evaluate(live=args.live)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for result in report["cases"]:
        print(result["id"], json.dumps(result["merged"], sort_keys=True))


if __name__ == "__main__":
    main()
