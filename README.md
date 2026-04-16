# wikifuse

[![PyPI version](https://badge.fury.io/py/wikifuse.svg)](https://badge.fury.io/py/wikifuse)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/gojiplus/wikifuse/actions/workflows/ci.yml/badge.svg)](https://github.com/gojiplus/wikifuse/actions/workflows/ci.yml)

Merge Wikipedia articles across languages into one comprehensive, source-attributed page.

## The Problem

Wikipedia articles vary dramatically across languages. A politician's English page might have 3 references while the French version has 25. A scientist's Hindi page might cover their early life in detail while English focuses on achievements. **wikifuse** merges these perspectives into a single, richer article with full source attribution.

## Quick Start

```bash
pip install wikifuse

# Compare English-only vs merged English+French for Rachida Dati
wikifuse diff --qid Q27182 --base en --compare en,fr --out ./rachida_dati/ --no-llm
```

Example output:

```
$ wikifuse diff --qid Q27182 --base en --compare en,fr --out ./rachida_dati/ --no-llm

Base (en only):     3,245 words, 12 references
Merged (en+fr):     5,891 words, 47 references
Gain:               +81% words, +292% references
```

See [example diff output](examples/Q27182/diff.html) comparing Rachida Dati's English vs English+French articles.

## Commands

### `diff` - Compare base vs merged article

Shows what you gain by merging across languages:

```bash
wikifuse diff --qid Q27182 --base en --compare en,fr --out ./output/
```

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

1. **Fetch**: Download articles from multiple language Wikipedias using Wikidata QID
2. **Translate**: Non-English text translated to English for alignment
3. **Align**: Sentence embeddings cluster semantically similar claims
4. **Merge**: Deduplicate while preserving unique content and references
5. **Render**: Output wikitext or HTML with full provenance

## Output Files

- `wikifuse.ir.json` - Intermediate Representation with sections, claims, and attribution
- `wikifuse.wikitext` - MediaWiki wikitext ready for review
- `preview.html` - HTML preview
- `diff.html` - Side-by-side comparison (from `diff` command)

## Configuration

```yaml
# wikifuse.yaml
qid: Q1058
languages: [en, hi]
base_language: en
max_refs_per_claim: 3
emit: [ir, wikitext, html]
```

## Installation

```bash
pip install wikifuse
```

For LLM-powered merging (uses OpenAI):

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

Issues and PRs welcome. Focus areas:
- Enhanced translation service integration
- Better cross-lingual alignment models
- Performance optimization for large articles

## License

MIT
