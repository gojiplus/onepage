"""Utilities for comparing base-only vs merged Wikipedia articles."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .merge import merge_article
from .models import IntermediateRepresentation


@dataclass
class ArticleStats:
    """Statistics about an article version."""

    section_count: int = 0
    reference_count: int = 0
    word_count: int = 0
    image_count: int = 0
    section_names: list[str] = field(default_factory=list)


@dataclass
class SectionDiff:
    """Diff information for a single section."""

    title: str
    base_word_count: int = 0
    merged_word_count: int = 0
    base_text: str = ""
    merged_text: str = ""
    is_new: bool = False


@dataclass
class ComparisonResult:
    """Result of comparing base-only vs merged articles."""

    qid: str
    entity_name: str
    base_lang: str
    compare_langs: list[str]
    base_stats: ArticleStats
    merged_stats: ArticleStats
    new_sections: list[str] = field(default_factory=list)
    section_diffs: dict[str, SectionDiff] = field(default_factory=dict)


def _count_words(text: str) -> int:
    """Count words in a text string."""
    if not text:
        return 0
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def _extract_stats(ir: IntermediateRepresentation) -> ArticleStats:
    """Extract statistics from an IR."""
    section_names = []
    total_word_count = 0

    for section in ir.sections:
        title = section.title.get(
            "en", list(section.title.values())[0] if section.title else section.id
        )
        section_names.append(title)

        for item_id in section.items:
            if item_id in ir.content:
                content = ir.content[item_id]
                text = getattr(content, "text", "")
                total_word_count += _count_words(text)

    images = ir.metadata.get("images", [])

    return ArticleStats(
        section_count=len(ir.sections),
        reference_count=len(ir.references),
        word_count=total_word_count,
        image_count=len(images) if images else 0,
        section_names=section_names,
    )


def _extract_section_text(ir: IntermediateRepresentation, section_id: str) -> str:
    """Extract text content for a section."""
    for section in ir.sections:
        if section.id == section_id:
            texts = []
            for item_id in section.items:
                if item_id in ir.content:
                    content = ir.content[item_id]
                    text = getattr(content, "text", "")
                    if text:
                        texts.append(text)
            return " ".join(texts)
    return ""


def compare_articles(
    qid: str,
    base_lang: str,
    compare_langs: list[str],
    use_llm: bool = True,
    llm_model: str = "gpt-4o-mini",
) -> ComparisonResult:
    """Generate both base-only and merged versions and compute differences.

    Args:
        qid: Wikidata QID of the entity.
        base_lang: Base language (typically "en").
        compare_langs: Languages to include in the merged version.
        use_llm: Whether to use LLM for intelligent text merging.
        llm_model: LLM model to use.

    Returns:
        ComparisonResult with statistics and diffs.
    """
    if use_llm and not os.environ.get("OPENAI_API_KEY"):
        use_llm = False

    base_ir = merge_article(
        qid,
        [base_lang],
        target_lang=base_lang,
        use_llm=use_llm,
        llm_model=llm_model,
    )

    merged_ir = merge_article(
        qid,
        compare_langs,
        target_lang=base_lang,
        use_llm=use_llm,
        llm_model=llm_model,
    )

    base_stats = _extract_stats(base_ir)
    merged_stats = _extract_stats(merged_ir)

    entity_name = base_ir.entity.labels.get(
        base_lang, base_ir.entity.labels.get("en", qid)
    )

    base_section_ids = {s.id for s in base_ir.sections}
    new_sections = []
    for section in merged_ir.sections:
        if section.id not in base_section_ids:
            title = section.title.get(
                base_lang,
                list(section.title.values())[0] if section.title else section.id,
            )
            new_sections.append(title)

    section_diffs: dict[str, SectionDiff] = {}
    all_section_ids = {s.id for s in base_ir.sections} | {
        s.id for s in merged_ir.sections
    }

    for section_id in all_section_ids:
        base_section = next((s for s in base_ir.sections if s.id == section_id), None)
        merged_section = next(
            (s for s in merged_ir.sections if s.id == section_id), None
        )

        if merged_section:
            title = merged_section.title.get(
                base_lang,
                (
                    list(merged_section.title.values())[0]
                    if merged_section.title
                    else section_id
                ),
            )
        elif base_section:
            title = base_section.title.get(
                base_lang,
                (
                    list(base_section.title.values())[0]
                    if base_section.title
                    else section_id
                ),
            )
        else:
            title = section_id

        base_text = _extract_section_text(base_ir, section_id) if base_section else ""
        merged_text = (
            _extract_section_text(merged_ir, section_id) if merged_section else ""
        )

        section_diffs[section_id] = SectionDiff(
            title=title,
            base_word_count=_count_words(base_text),
            merged_word_count=_count_words(merged_text),
            base_text=base_text,
            merged_text=merged_text,
            is_new=section_id not in base_section_ids,
        )

    return ComparisonResult(
        qid=qid,
        entity_name=entity_name,
        base_lang=base_lang,
        compare_langs=compare_langs,
        base_stats=base_stats,
        merged_stats=merged_stats,
        new_sections=new_sections,
        section_diffs=section_diffs,
    )


def print_stats(comparison: ComparisonResult) -> str:
    """Generate terminal-friendly statistics output.

    Args:
        comparison: ComparisonResult from compare_articles().

    Returns:
        Formatted string for terminal display.
    """
    base = comparison.base_stats
    merged = comparison.merged_stats

    def format_change(base_val: int, merged_val: int) -> str:
        diff = merged_val - base_val
        if diff > 0:
            return f"+{diff}"
        elif diff < 0:
            return str(diff)
        return "0"

    langs_str = "+".join(comparison.compare_langs)
    base_col = f"{comparison.base_lang.upper()}-only"
    merged_col = f"Merged ({langs_str})"
    header = f"{'':20} {base_col:<14} {merged_col:<20} Change"

    sec_chg = format_change(base.section_count, merged.section_count)
    ref_chg = format_change(base.reference_count, merged.reference_count)
    wrd_chg = format_change(base.word_count, merged.word_count)
    img_chg = format_change(base.image_count, merged.image_count)

    def row(
        label: str, base_val: int, mrgd_val: int, chg: str, prefix: str = ""
    ) -> str:
        b = f"{prefix}{base_val}"
        m = f"{prefix}{mrgd_val}"
        return f"{label:<20} {b:<14} {m:<20} {chg}"

    lines = [
        f"{comparison.entity_name} ({comparison.qid}) - Cross-lingual comparison",
        "",
        header,
        "-" * 70,
        row("Sections:", base.section_count, merged.section_count, sec_chg),
        row("References:", base.reference_count, merged.reference_count, ref_chg),
        row("Word count:", base.word_count, merged.word_count, wrd_chg, "~"),
        row("Images:", base.image_count, merged.image_count, img_chg),
    ]

    if comparison.new_sections:
        lines.append("")
        lines.append("New sections from other languages:")
        for section in comparison.new_sections[:10]:
            lines.append(f"  + {section}")
        if len(comparison.new_sections) > 10:
            lines.append(f"  ... and {len(comparison.new_sections) - 10} more")

    return "\n".join(lines)


def _build_new_sections_html(new_sections: list[str]) -> str:
    """Build HTML for new sections list."""
    if not new_sections:
        return ""
    items = "".join(f"<li>{s}</li>" for s in new_sections)
    return (
        '<div class="new-sections">'
        "<h2>New Sections from Other Languages</h2>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def generate_diff_html(comparison: ComparisonResult, output_path: str) -> None:
    """Generate side-by-side HTML comparison.

    Args:
        comparison: ComparisonResult from compare_articles().
        output_path: Path to write the HTML file.
    """
    base = comparison.base_stats
    merged = comparison.merged_stats
    langs_str = "+".join(comparison.compare_langs)

    def format_change(base_val: int, merged_val: int) -> str:
        diff = merged_val - base_val
        if diff > 0:
            return f'<span class="positive">+{diff}</span>'
        elif diff < 0:
            return f'<span class="negative">{diff}</span>'
        return "0"

    sections_html = []
    for _, diff in comparison.section_diffs.items():
        new_badge = '<span class="new-badge">NEW</span>' if diff.is_new else ""
        word_change = diff.merged_word_count - diff.base_word_count
        word_change_class = (
            "positive" if word_change > 0 else ("negative" if word_change < 0 else "")
        )
        word_change_str = f"+{word_change}" if word_change > 0 else str(word_change)

        sections_html.append(
            f"""
        <div class="section {"new-section" if diff.is_new else ""}">
            <div class="section-header">
                <h3>{diff.title} {new_badge}</h3>
                <span class="word-count">
                    {diff.base_word_count} words &rarr; {diff.merged_word_count} words
                    (<span class="{word_change_class}">{word_change_str}</span>)
                </span>
            </div>
            <details>
                <summary>Show content</summary>
                <div class="content-comparison">
                    <div class="base-content">
                        <h4>{comparison.base_lang.upper()}-only</h4>
                        <p>{diff.base_text or "<em>No content</em>"}</p>
                    </div>
                    <div class="merged-content">
                        <h4>Merged</h4>
                        <p>{diff.merged_text or "<em>No content</em>"}</p>
                    </div>
                </div>
            </details>
        </div>
        """
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comparison: {comparison.entity_name} ({comparison.qid})</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        .stats-table {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .positive {{
            color: #28a745;
            font-weight: bold;
        }}
        .negative {{
            color: #dc3545;
            font-weight: bold;
        }}
        .section {{
            background: white;
            border-radius: 8px;
            padding: 15px 20px;
            margin-bottom: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .new-section {{
            border-left: 4px solid #28a745;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .section-header h3 {{
            margin: 0;
            font-size: 1.1em;
        }}
        .new-badge {{
            background: #28a745;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 8px;
        }}
        .word-count {{
            color: #666;
            font-size: 0.9em;
        }}
        details {{
            margin-top: 10px;
        }}
        summary {{
            cursor: pointer;
            color: #007bff;
            font-size: 0.9em;
        }}
        .content-comparison {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 15px;
        }}
        .base-content, .merged-content {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
        }}
        .base-content h4, .merged-content h4 {{
            margin: 0 0 10px 0;
            font-size: 0.9em;
            color: #666;
        }}
        .merged-content {{
            background: #e8f5e9;
        }}
        .new-sections {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .new-sections ul {{
            margin: 10px 0 0 0;
            padding-left: 20px;
        }}
        .new-sections li {{
            color: #28a745;
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <h1>{comparison.entity_name} ({comparison.qid})</h1>
    <p>Comparing: {comparison.base_lang.upper()}-only vs Merged ({langs_str})</p>

    <div class="stats-table">
        <h2>Summary Statistics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>{comparison.base_lang.upper()}-only</th>
                <th>Merged ({"+".join(comparison.compare_langs)})</th>
                <th>Change</th>
            </tr>
            <tr>
                <td>Sections</td>
                <td>{base.section_count}</td>
                <td>{merged.section_count}</td>
                <td>{format_change(base.section_count, merged.section_count)}</td>
            </tr>
            <tr>
                <td>References</td>
                <td>{base.reference_count}</td>
                <td>{merged.reference_count}</td>
                <td>{format_change(base.reference_count, merged.reference_count)}</td>
            </tr>
            <tr>
                <td>Word count</td>
                <td>~{base.word_count}</td>
                <td>~{merged.word_count}</td>
                <td>{format_change(base.word_count, merged.word_count)}</td>
            </tr>
            <tr>
                <td>Images</td>
                <td>{base.image_count}</td>
                <td>{merged.image_count}</td>
                <td>{format_change(base.image_count, merged.image_count)}</td>
            </tr>
        </table>
    </div>

    {_build_new_sections_html(comparison.new_sections)}

    <h2>Section-by-Section Comparison</h2>
    {"".join(sections_html)}
</body>
</html>
"""

    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
