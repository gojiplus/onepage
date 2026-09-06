# wikifuse

[![PyPI version](https://badge.fury.io/py/wikifuse.svg)](https://badge.fury.io/py/wikifuse)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/gojiplus/wikifuse/actions/workflows/ci.yml/badge.svg)](https://github.com/gojiplus/wikifuse/actions/workflows/ci.yml)

Combine Wikipedia passages across languages while preserving their citations and source revisions.

## The Problem

Wikipedia articles vary dramatically across languages. A politician's English page might have 3 references while the French version has 25. A scientist's Hindi page might cover their early life in detail while English focuses on achievements. **wikifuse** merges these perspectives into a single, richer article with full source attribution.

## Quick Start

Cross-language commands need a LibreTranslate service. The default hosted endpoint requires an API key; you can also configure your own server below.

```bash
pip install wikifuse
export WIKIFUSE_TRANSLATE_API_KEY=your-key

# Compare English-only vs merged English+French for Rachida Dati
wikifuse diff --qid Q27182 --base en --compare en,fr --out ./rachida_dati/ --no-llm
```

## Commands

### `diff` - Compare base vs merged article

Shows what you gain by merging across languages:

```bash
wikifuse diff --qid Q27182 --base en --compare en,fr --out ./output/
```

A comparison captures each requested source article once and includes the base language in both versions. It writes `sources.json`, `base.ir.json`, `merged.ir.json`, `comparison.json`, and `ATTRIBUTION.md` alongside the HTML. These files preserve the source revisions, output text, and merge settings used in that run. Missing requested articles stop the comparison.

Recreate the HTML from its saved result without fetching articles, translating, or calling an LLM:

```bash
wikifuse diff-preview --comparison ./output/comparison.json --out ./output/replayed.html
```

Word and reference counts describe output size; they do not establish factual accuracy or translation quality.


### `fetch` - Download articles

```bash
wikifuse fetch --qid Q1058 --languages en,hi --out ./out/Q1058
```

### `merge` - Combine across languages

```bash
wikifuse merge --qid Q1058 --languages en,hi --out ./out/Q1058
```

### `render` - Output wikitext

```bash
wikifuse render --ir ./out/Q1058/wikifuse.ir.json --out ./out/Q1058/wikifuse.wikitext
```

### `preview` - HTML preview

```bash
wikifuse preview --ir ./out/Q1058/wikifuse.ir.json --out ./out/Q1058/preview.html
```

## How It Works

1. **Fetch**: Download articles from multiple language Wikipedias at recorded revision IDs.
2. **Parse**: Keep source passages attached to their inline references, including named references reused within an article.
3. **Translate**: Translate non-English passages to English.
4. **Merge**: Combine identical passages within a section, retaining their references and source revisions. With an API key, the LLM orders passages without rewriting them. Invalid ordering responses leave the original order intact.
5. **Render**: Output wikitext or HTML with citations linked to the passages that supplied them.

A passage ends at an inline citation or paragraph break; it can contain several sentences. The parser preserves those citation boundaries without deciding whether a reference supports every statement in the passage. Undefined or conflicting named references, and references without preceding text in their paragraph, raise an error.

Each claim's `provenance` field is a list of source records containing `wiki`, `title`, and `rev_id`. Regenerate older IR files that stored a single provenance object. Reference records retain their original citation wikitext.

## Output Files

- `wikifuse.ir.json` - Intermediate Representation with sections, claims, references, and source revisions
- `ATTRIBUTION.md` - Source revision and contributor-history links, written by `merge`
- `wikifuse.wikitext` - MediaWiki wikitext ready for review
- `preview.html` - HTML preview
- `diff.html` - Side-by-side comparison (from `diff` command)

## Translation Configuration

The default endpoint is `https://libretranslate.com/translate`. Set `WIKIFUSE_TRANSLATE_API_KEY` to your service key, or point `WIKIFUSE_TRANSLATE_URL` to your own LibreTranslate `/translate` endpoint:

```bash
export WIKIFUSE_TRANSLATE_URL=http://localhost:5000/translate
wikifuse merge --qid Q1058 --languages en,hi --out ./output/ --no-llm
```

Set the API key only if your server requires one. `--no-llm` disables OpenAI passage ordering; translation still uses the configured service.

Translation sends the full input in chunks of at most 500 characters, splitting at whitespace where possible. Requests time out after 15 seconds of inactivity. Transient network failures and HTTP 429/500/502/503/504 responses get at most three attempts per chunk, with retry waits capped at 30 seconds. Permanent HTTP errors and malformed responses fail immediately.

If any chunk fails, the Python API raises `TranslationError`. The CLI reports the source and target languages, failed chunk, and error, then exits unsuccessfully without replacing the merged IR or diff output. Failed translations are not cached. Successful translations return no confidence estimate (`None`); same-language inputs return their original text with `1.0`.

See the [LibreTranslate API documentation](https://docs.libretranslate.com/api/operations/translate/) for endpoint and key configuration.

## Installation

```bash
pip install wikifuse
```

For LLM ordering of source passages (uses OpenAI):

```bash
pip install wikifuse
export OPENAI_API_KEY=your-key
wikifuse merge --qid Q1058 --languages en,hi --out ./output/
```

Without LLM (basic text merge):

```bash
wikifuse merge --qid Q1058 --languages en,hi --out ./output/ --no-llm
```

## Licensing & Attribution

- Wikipedia text is **CC BY-SA 4.0**; remixes must include attribution
- Generated `ATTRIBUTION.md` includes source language and revision IDs
- Wikidata statements are under compatible open licenses

## Contributing

The base installation includes Click, Requests, wikitextparser, and the OpenAI client. It does not install Torch, Transformers, or an embedding model.

Run the same checks used in CI:

```bash
uv sync --locked --group docs
uv run ruff check wikifuse/ tests/
uv run ruff format --check wikifuse/ tests/
uv run vulture wikifuse/ --min-confidence 80
uv run deptry wikifuse/
uv run pydoclint wikifuse/
uv run pytest tests/ -v
uv run sphinx-build docs docs/_build -b html -W
uv build
```

Issues and PRs welcome. Focus areas:
- Enhanced translation service integration
- Better cross-lingual alignment models
- Performance optimization for large articles

## License

MIT
