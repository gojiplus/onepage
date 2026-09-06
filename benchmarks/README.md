# Multilingual merger benchmark

Run from the repository checkout after `uv sync --dev`:

```sh
uv run python -m benchmarks.run --out benchmarks/reference-report.json
uv run pytest tests/test_benchmark.py
```

The default run uses captured Wikipedia excerpts and explicit English reference
renderings. It makes no network calls and disables LLM ordering. The production
parser and merger process the original wikitext, including its inline citations.
The report contains the input fixture hash, output IR, and per-case scores.

| Case | English-only facts | Merged facts | Duplicate mentions | Traceable citation links |
| --- | --- | --- | --- | --- |
| Ada Lovelace family | 1/4 | 4/4 | 2 | 2/2 |
| Eiffel Tower visitors and height | 1/4 | 4/4 | 0 | 3/3 |
| Synthetic conflicting dates | 1/2 | 2/2 | 0 | 2/2 |

The synthetic case retains both conflicting dates in distinct passages. It does
not decide which date is true. The Ada case retains one uncited mention of a fact
that other language versions cite; the original French excerpt has no citation.
This is reported by `cited_fact_mentions_missing_citations`, not treated as a
citation lost during merging.

## What the scores mean

- Facts are explicit, manually selected regex labels matched within individual
  output passages. Recall counts labels present at least once. Duplicate mentions
  count additional passages matching the same label.
- Citation traceability checks whether an emitted citation's original wikitext
  belongs to the allowed source citations for facts matched in that passage.
  Missing citations are counted separately. This checks attachment to captured
  source passages; it does not establish that an external source proves a claim.
- Conflict preservation requires the two labeled alternatives in distinct output
  passages. It measures retention of a known conflict, not automatic detection.
- Unmatched passages are reported for inspection. They are not automatically
  classified as hallucinations.

These are two small excerpt cases and a synthetic control, not a representative
accuracy estimate. Reference translations are authored renderings, not independent
bilingual adjudications. They isolate merger behavior and do not measure machine
translation quality. Regex labels may miss valid paraphrases. Full articles,
arbitrary template expansion, heading alignment, and LLM ordering are outside
this benchmark's scope. Inspect the saved IR alongside the scores.

To evaluate a configured LibreTranslate service instead:

```sh
export WIKIFUSE_TRANSLATE_URL=https://your-translator.example/translate
uv run python -m benchmarks.run --live --out /tmp/wikifuse-live-report.json
```

Set `WIKIFUSE_TRANSLATE_API_KEY` if the service requires it. Live results depend
on that service and need manual inspection, especially when wording differs from
the reference labels. A failed translation aborts without writing a report.
See the [official API documentation](https://docs.libretranslate.com/guides/api_usage/).

## Sources and license

The captured text in `cases.json` is excerpted from the Wikipedia revisions below.
The English reference translations adapt those excerpts. Source text and derived
text in the report are available under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
Wikipedia contributors retain attribution; contributor histories are linked below.
The synthetic observatory and its citations are invented test data. Revision zero
in its IR is a synthetic marker and is not a real Wikipedia revision.
Benchmark Python code is covered by the repository's MIT license.

| Article | Pinned source | Contributors |
| --- | --- | --- |
| Ada Lovelace (en) | [1371961179](https://en.wikipedia.org/w/index.php?oldid=1371961179) | [History](https://en.wikipedia.org/w/index.php?title=Ada_Lovelace&action=history) |
| Ada Lovelace (fr) | [238903043](https://fr.wikipedia.org/w/index.php?oldid=238903043) | [History](https://fr.wikipedia.org/w/index.php?title=Ada_Lovelace&action=history) |
| Ada Lovelace (es) | [174452511](https://es.wikipedia.org/w/index.php?oldid=174452511) | [History](https://es.wikipedia.org/w/index.php?title=Ada_Lovelace&action=history) |
| Eiffel Tower (en) | [1367947019](https://en.wikipedia.org/w/index.php?oldid=1367947019) | [History](https://en.wikipedia.org/w/index.php?title=Eiffel_Tower&action=history) |
| Tour Eiffel (fr) | [239220518](https://fr.wikipedia.org/w/index.php?oldid=239220518) | [History](https://fr.wikipedia.org/w/index.php?title=Tour_Eiffel&action=history) |
| Torre Eiffel (es) | [175109131](https://es.wikipedia.org/w/index.php?oldid=175109131) | [History](https://es.wikipedia.org/w/index.php?title=Torre_Eiffel&action=history) |
