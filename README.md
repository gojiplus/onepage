# onepage

**Merge Wikipedia articles across languages into one comprehensive, source‑attributed page.**

Input: a Wikidata **QID**. Output: deterministic **English wikitext** (for now) + a machine‑readable **IR (JSON)**. Provenance is preserved per sentence. Later, the same IR can render to other languages.

---

## Why

Different language Wikipedias describe the same topic independently. Sitelinks and Wikidata connect them, but content isn’t merged. **onepage** builds a single, auditable article by aligning and deduplicating facts and prose across languages.

---

## Core ideas

* **QID‑anchored merge:** Use a Wikidata item to enumerate all article versions (sitelinks).
* **English‑pivot rendering:** Translate non‑English sentences to English for alignment; final output is English wikitext.
* **Provenance first:** Track `wiki`, `title`, `rev_id`, and source refs for every claim.
* **Deterministic emit:** Same IR → same wikitext; no silent heuristics that change across runs.
* **Policy‑aware:** Surface conflicts; don’t synthesize unsourced claims; respect BLP.

---

## What it produces

* **`onepage.en.wikitext`** — MediaWiki wikitext ready for human review/paste.
* **`onepage.ir.json`** — Intermediate Representation with sections, claims, facts, refs, and attribution.
* **`preview.en.html`** — Optional HTML preview.
* **`ATTRIBUTION.md`** — Source language + revision IDs for share‑alike compliance.

---

## Installation & Quickstart

```bash
# 0) Install dependencies
git clone https://github.com/gojiplus/onepage.git
cd onepage
pip install -r requirements.txt

# Verify installation
python scripts/verify_structure.py
python -m onepage.cli.main --help

# 1) Fetch sitelinks and pull article content
python -m onepage.cli.main fetch --qid Q1058 --languages en,hi --out ./out/Q1058

# 2) Build the merged IR (align facts/claims, dedup references)
python -m onepage.cli.main build --qid Q1058 --in ./out/Q1058 --out ./out/Q1058

# 3) Render the final English Wikipedia page (wikitext)
python -m onepage.cli.main render --qid Q1058 --lang en --format wikitext \
  --out ./out/Q1058/onepage.en.wikitext --ir ./out/Q1058/onepage.ir.json

# 4) Optional HTML preview (requires IR from step 2)
python -m onepage.cli.main preview --qid Q1058 --lang en --out ./out/Q1058/preview.en.html --ir ./out/Q1058/onepage.ir.json

# Or run complete pipeline with config
python -m onepage.cli.main run --config onepage.yaml --out ./out/Q1058
```

### Alternative: Manual Preview Generation

If the CLI has issues, you can generate HTML previews directly with Python:

```python
import json
from onepage.render import HTMLRenderer
from onepage.models import IntermediateRepresentation

# Load or create IR data
with open('./out/Q1058/onepage.ir.json', 'r') as f:
    ir_data = json.load(f)

ir = IntermediateRepresentation.from_dict(ir_data)
renderer = HTMLRenderer('en')
html_content = renderer.render(ir)

with open('./out/Q1058/preview.en.html', 'w') as f:
    f.write(html_content)
```

### Known Issues
- ~~JSON serialization error with Provenance objects~~ ✓ Fixed
- ~~PyTorch version issues~~ ✓ Fixed (upgraded to 2.2.2)
- TensorFlow AVX warnings (from sentence-transformers dependency, can be ignored)
- CLI may crash on some systems - use manual Python approach above

**Example** QID: `Q1058` (Narendra Modi). The command above merges English (`enwiki`) and Hindi (`hiwiki`) articles into one English page.

---

## Translation & alignment

**Pivot = English.** All non‑English sentences are translated to English **for clustering/merge only**. The IR stores both the **original sentence** and its **EN translation**, with a quality score (if available) and the citation set.

Alignment pipeline (simplified):

1. **Segmentation:** Headings/paragraphs → sentences; strip boilerplate.
2. **Cross‑lingual matching:** Sentence embeddings + lexical cues cluster semantically similar claims across languages.
3. **Reference canonicalization:** Normalize DOIs/URLs/titles/dates → dedup clusters by source.
4. **Conflict handling:** Prefer well‑sourced, recent, and concordant claims; otherwise retain multiple sourced variants with clear attribution.
5. **Fact layer:** Infobox‑style facts align to Wikidata properties where applicable (dates, identifiers, counts), carrying qualifiers and “as of” dates.

> The final **English** wikitext is composed from the merged IR; future renderers will target other languages using the same IR.

---

## Intermediate Representation (IR)

A compact JSON that round‑trips to wikitext and HTML.

```json
{
  "entity": {"qid": "Q1058", "labels": {"en": "Narendra Modi", "hi": "नरेन्द्र मोदी"}},
  "sections": [
    {"id": "lead", "items": ["c1","f3"]},
    {"id": "early_life", "title": {"en": "Early life"}, "items": ["c7","c8"]}
  ],
  "content": {
    "c1": {
      "type": "claim",
      "lang": "hi",
      "text": "…original Hindi sentence…",
      "text_en": "…English translation used for merge…",
      "sources": ["r12","r19"],
      "provenance": {"wiki": "hiwiki", "title": "नरेन्द्र मोदी", "rev_id": 123456}
    },
    "f3": {
      "type": "fact",
      "property": "P39",
      "value": {"qid": "Q11696"},
      "qualifiers": {"start_time": "2014-05-26"},
      "sources": ["r5"],
      "from": "wikidata"
    }
  },
  "references": {
    "r12": {"doi": "10.xxxx/…", "url": "https://…", "title": "…", "date": "2023-05-02"}
  }
}
```

---

## Rendering to wikitext (English)

Emitter guarantees: stable section order, consistent citation templates, and per‑sentence attribution.

Output scaffold:

1. **Short description / lead**
2. **Infobox** (English template; parameters from facts with citations)
3. **Body sections** with merged claims and inline refs (`<ref>{{Cite …}}</ref>`)
4. **References** (`== References ==` + `{{Reflist}}`)
5. **Categories** (English categories from the IR)

---

## Configuration

Create a YAML config file for batch processing:

```yaml
# onepage.yaml
qid: Q1058
languages: [en, hi]
base_language: en
max_refs_per_claim: 3
emit: [ir, wikitext, html]
```

```bash
python -m onepage.cli.main run --config onepage.yaml --out ./out/Q1058
```

## Dependencies

Core requirements:
- Python 3.8+
- `click` - CLI framework
- `requests` - HTTP requests
- `pyyaml` - YAML configuration
- `wikitextparser` - Parse Wikipedia wikitext
- `sentence-transformers` - Multilingual sentence embeddings
- `numpy` - Numerical computations
- `beautifulsoup4` - HTML parsing

Install all dependencies:
```bash
pip install -r requirements.txt
```

---

## Licensing & attribution

* Wikipedia text is **CC BY‑SA 4.0**; remixes must include attribution and remain share‑alike.
* **ATTRIBUTION.md** includes the per‑sentence source language and revision ID.
* Media files may carry different licenses; verify before reuse.
* Wikidata statements are under compatible open licenses.

---

## Policies & safeguards

* **BLP guardrails:** For living persons, require high‑quality sources; exclude contentious unsourced material.
* **No original research:** The merge aggregates sourced claims; it does not infer new facts.
* **Conflict visibility:** When sources differ, present both with clear citations and qualifiers (dates, scope).

---

## Package Structure

```
onepage/
├── core/           # Data models and configuration  
├── api/            # Wikidata and Wikipedia API clients
├── processing/     # Text processing, alignment, and IR building
├── renderers/      # Output generation (wikitext, HTML, attribution)
└── cli/            # Command-line interface
```

## Testing

Run the verification script to test basic functionality:

```bash
python scripts/verify_structure.py
```

Run the example to test with real data:

```bash
python scripts/example.py
```

Run unit tests:

```bash
python -m pytest tests/
```

---

## Contributing

Issues and PRs welcome. The implementation is complete and functional. Focus areas for improvement:
- Enhanced translation service integration
- Better cross-lingual alignment models
- Template localization for non-English output
- Performance optimization for large articles
