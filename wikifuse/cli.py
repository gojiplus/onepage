"""Command line interface for wikifuse."""

import json
import os

import click

from .api import ArticleFetcher, select_top_languages
from .diff import compare_articles, generate_diff_html, print_stats
from .merge import merge_article
from .render import HTMLRenderer, WikitextRenderer


@click.group()
@click.version_option()
def cli() -> None:
    """Utilities for working with multilingual Wikipedia pages."""
    pass


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID (e.g., Q1058)")
@click.option(
    "--languages",
    required=False,
    default=None,
    help="Comma-separated language codes (e.g., en,hi). Uses --top-langs if omitted.",
)
@click.option(
    "--top-langs",
    type=int,
    default=None,
    help="Select top N languages by article size (default: 2).",
)
@click.option("--out", required=True, type=click.Path(), help="Output directory")
def fetch(qid: str, languages: str, top_langs: int, out: str) -> None:
    """Fetch Wikipedia pages and metadata for an entity."""
    if languages:
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
    elif top_langs is not None:
        click.echo(f"Selecting top {top_langs} languages by article size...")
        lang_list = select_top_languages(qid, top_n=top_langs)
        click.echo(f"Selected languages: {', '.join(lang_list)}")
    else:
        lang_list = select_top_languages(qid, top_n=2)
        click.echo(f"Auto-selected languages: {', '.join(lang_list)}")

    click.echo(f"Fetching articles for {qid} in languages: {', '.join(lang_list)}")
    fetcher = ArticleFetcher()
    fetcher.fetch_all(qid, lang_list, out)
    click.echo(f"Results written to {out}")


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID (e.g., Q1058)")
@click.option(
    "--languages",
    required=False,
    default=None,
    help="Comma-separated language codes (e.g., en,hi). Uses --top-langs if omitted.",
)
@click.option(
    "--top-langs",
    type=int,
    default=None,
    help="Select top N languages by article size (default: 2).",
)
@click.option("--out", required=True, type=click.Path(), help="Output directory")
@click.option(
    "--use-llm/--no-llm",
    default=True,
    help="Use LLM for intelligent text merging (default: enabled).",
)
@click.option(
    "--llm-model",
    default="gpt-4o-mini",
    help="LLM model to use for merging (default: gpt-4o-mini).",
)
def merge(
    qid: str,
    languages: str,
    top_langs: int,
    out: str,
    use_llm: bool,
    llm_model: str,
) -> None:
    """Merge Wikipedia articles across languages into IR."""
    if languages:
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
    elif top_langs is not None:
        click.echo(f"Selecting top {top_langs} languages by article size...")
        lang_list = select_top_languages(qid, top_n=top_langs)
        click.echo(f"Selected languages: {', '.join(lang_list)}")
    else:
        lang_list = select_top_languages(qid, top_n=2)
        click.echo(f"Auto-selected languages: {', '.join(lang_list)}")

    click.echo(f"Merging articles for {qid} from languages: {', '.join(lang_list)}")

    if use_llm and not os.environ.get("OPENAI_API_KEY"):
        click.echo("Warning: OPENAI_API_KEY not set. Falling back to basic text merge.")
        use_llm = False

    os.makedirs(out, exist_ok=True)
    ir = merge_article(
        qid, lang_list, target_lang="en", use_llm=use_llm, llm_model=llm_model
    )

    ir_path = os.path.join(out, "wikifuse.ir.json")
    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(ir.to_dict(), f, indent=2, ensure_ascii=False)

    click.echo(f"Merged IR written to {ir_path}")


@cli.command()
@click.option("--ir", required=True, type=click.Path(exists=True), help="IR JSON file")
@click.option("--out", required=True, type=click.Path(), help="Output wikitext file")
def render(ir: str, out: str) -> None:
    """Render IR to wikitext."""
    click.echo(f"Rendering {ir} to wikitext")

    with open(ir, encoding="utf-8") as f:
        ir_data = json.load(f)

    from .models import IntermediateRepresentation

    ir_obj = IntermediateRepresentation.from_dict(ir_data)

    renderer = WikitextRenderer("en")
    wikitext = renderer.render(ir_obj)

    with open(out, "w", encoding="utf-8") as f:
        f.write(wikitext)

    click.echo(f"Wikitext written to {out}")


@cli.command()
@click.option("--ir", required=True, type=click.Path(exists=True), help="IR JSON file")
@click.option("--out", required=True, type=click.Path(), help="Output HTML file")
def preview(ir: str, out: str) -> None:
    """Generate HTML preview from IR."""
    click.echo(f"Generating HTML preview from {ir}")

    with open(ir, encoding="utf-8") as f:
        ir_data = json.load(f)

    from .models import IntermediateRepresentation

    ir_obj = IntermediateRepresentation.from_dict(ir_data)

    renderer = HTMLRenderer("en")
    html = renderer.render(ir_obj)

    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    click.echo(f"HTML preview written to {out}")


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID (e.g., Q27182)")
@click.option(
    "--base",
    default="en",
    help="Base language for comparison (default: en).",
)
@click.option(
    "--compare",
    required=True,
    help="Comma-separated languages for merged version (e.g., en,fr).",
)
@click.option("--out", required=True, type=click.Path(), help="Output directory")
@click.option(
    "--use-llm/--no-llm",
    default=True,
    help="Use LLM for intelligent text merging (default: enabled).",
)
@click.option(
    "--llm-model",
    default="gpt-4o-mini",
    help="LLM model to use for merging (default: gpt-4o-mini).",
)
def diff(
    qid: str,
    base: str,
    compare: str,
    out: str,
    use_llm: bool,
    llm_model: str,
) -> None:
    """Compare base-only vs merged article to show cross-lingual value."""
    compare_langs = [lang.strip() for lang in compare.split(",") if lang.strip()]

    if use_llm and not os.environ.get("OPENAI_API_KEY"):
        click.echo("Warning: OPENAI_API_KEY not set. Falling back to basic text merge.")
        use_llm = False

    click.echo(
        f"Comparing {base}-only vs merged ({'+'.join(compare_langs)}) for {qid}..."
    )

    comparison = compare_articles(
        qid=qid,
        base_lang=base,
        compare_langs=compare_langs,
        use_llm=use_llm,
        llm_model=llm_model,
    )

    click.echo("")
    click.echo(print_stats(comparison))

    os.makedirs(out, exist_ok=True)
    html_path = os.path.join(out, "diff.html")
    generate_diff_html(comparison, html_path)
    click.echo("")
    click.echo(f"HTML comparison written to {html_path}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
