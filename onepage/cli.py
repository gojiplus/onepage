"""Command line interface for onepage."""

import click

from .api import ArticleFetcher


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


if __name__ == "__main__":  # pragma: no cover
    cli()
