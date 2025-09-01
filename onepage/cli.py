"""Command line interface for onepage."""

import click
import json
import os

from .api import ArticleFetcher
from .merge import merge_article
from .render import WikitextRenderer, HTMLRenderer


@click.group()
@click.version_option()
def cli() -> None:
    """Utilities for working with multilingual Wikipedia pages."""
    pass


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID (e.g., Q1058)")
@click.option(
    "--languages", required=True, help="Comma-separated language codes (e.g., en,hi)"
)
@click.option("--out", required=True, type=click.Path(), help="Output directory")
def fetch(qid: str, languages: str, out: str) -> None:
    """Fetch Wikipedia pages and metadata for an entity."""
    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
    click.echo(f"Fetching articles for {qid} in languages: {', '.join(lang_list)}")
    fetcher = ArticleFetcher()
    fetcher.fetch_all(qid, lang_list, out)
    click.echo(f"Results written to {out}")


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID (e.g., Q1058)")
@click.option(
    "--languages", required=True, help="Comma-separated language codes (e.g., en,hi)"
)
@click.option("--out", required=True, type=click.Path(), help="Output directory")
def merge(qid: str, languages: str, out: str) -> None:
    """Merge Wikipedia articles across languages into IR."""
    lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
    click.echo(f"Merging articles for {qid} from languages: {', '.join(lang_list)}")
    
    os.makedirs(out, exist_ok=True)
    ir = merge_article(qid, lang_list, target_lang="en")
    
    ir_path = os.path.join(out, "onepage.ir.json")
    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(ir.to_dict(), f, indent=2, ensure_ascii=False)
    
    click.echo(f"Merged IR written to {ir_path}")


@cli.command()
@click.option("--ir", required=True, type=click.Path(exists=True), help="IR JSON file")
@click.option("--out", required=True, type=click.Path(), help="Output wikitext file")
def render(ir: str, out: str) -> None:
    """Render IR to wikitext."""
    click.echo(f"Rendering {ir} to wikitext")
    
    with open(ir, "r", encoding="utf-8") as f:
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
    
    with open(ir, "r", encoding="utf-8") as f:
        ir_data = json.load(f)
    
    from .models import IntermediateRepresentation
    ir_obj = IntermediateRepresentation.from_dict(ir_data)
    
    renderer = HTMLRenderer("en")
    html = renderer.render(ir_obj)
    
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    
    click.echo(f"HTML preview written to {out}")


if __name__ == "__main__":  # pragma: no cover
    cli()
