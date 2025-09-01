"""Main CLI interface for onepage."""

import json
import os
from pathlib import Path
from typing import List, Optional

import click
import yaml

from ..core.config import Config
from ..api.fetcher import ArticleFetcher
from ..processing.builder import IRBuilder
from ..renderers.wikitext import WikitextRenderer
from ..renderers.html import HTMLRenderer
from ..renderers.attribution import AttributionGenerator


@click.group()
@click.version_option()
def cli() -> None:
    """Merge Wikipedia articles across languages into one comprehensive page."""
    pass


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID (e.g., Q1058)")
@click.option("--languages", required=True, help="Comma-separated language codes (e.g., en,hi,fr)")
@click.option("--out", required=True, type=click.Path(), help="Output directory")
def fetch(qid: str, languages: str, out: str) -> None:
    """Fetch sitelinks and pull article content from Wikipedia."""
    lang_list = [lang.strip() for lang in languages.split(",")]
    
    click.echo(f"Fetching articles for {qid} in languages: {', '.join(lang_list)}")
    
    fetcher = ArticleFetcher()
    try:
        result = fetcher.fetch_all(qid, lang_list, out)
        
        click.echo(f"✓ Fetched {len(result['articles'])} articles")
        click.echo(f"✓ Languages: {', '.join(result['languages_fetched'])}")
        click.echo(f"✓ Output saved to: {out}")
        
        if result['languages_requested'] != result['languages_fetched']:
            missing = set(result['languages_requested']) - set(result['languages_fetched'])
            click.echo(f"⚠ Could not fetch: {', '.join(missing)}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID")
@click.option("--in", "input_dir", required=True, type=click.Path(exists=True), help="Input directory")
@click.option("--out", required=True, type=click.Path(), help="Output directory") 
def build(qid: str, input_dir: str, out: str) -> None:
    """Build the merged IR (align facts/claims, dedup references)."""
    click.echo(f"Building merged IR for {qid}")
    
    # Ensure output directory exists
    output_path = Path(out)
    output_path.mkdir(parents=True, exist_ok=True)
    
    builder = IRBuilder()
    try:
        result = builder.build_ir(input_dir, qid)
        
        # Save IR to file
        ir_file = output_path / "onepage.ir.json"
        with open(ir_file, 'w', encoding='utf-8') as f:
            f.write(result.ir.to_json())
        
        click.echo(f"✓ Built IR with {result.stats['total_claims']} claims")
        click.echo(f"✓ {result.stats['alignment_clusters']} alignment clusters")
        click.echo(f"✓ {result.stats['canonical_references']} canonical references")
        click.echo(f"✓ IR saved to: {ir_file}")
        
        if result.warnings:
            for warning in result.warnings:
                click.echo(f"⚠ {warning}")
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID")
@click.option("--lang", default="en", help="Target language for rendering")
@click.option("--format", "output_format", default="wikitext", 
              type=click.Choice(["wikitext", "html"]), help="Output format")
@click.option("--out", required=True, type=click.Path(), help="Output file path")
@click.option("--ir", "ir_file", help="IR file path (default: find in qid directory)")
def render(qid: str, lang: str, output_format: str, out: str, ir_file: Optional[str]) -> None:
    """Render the final Wikipedia page from IR."""
    
    # Find IR file if not specified
    if not ir_file:
        # Look for IR file in common locations
        possible_paths = [
            f"./out/{qid}/onepage.ir.json",
            f"./{qid}/onepage.ir.json", 
            "./onepage.ir.json",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                ir_file = path
                break
        
        if not ir_file:
            click.echo("Error: Could not find IR file. Specify with --ir option.", err=True)
            raise click.Abort()
    
    # Load IR
    try:
        with open(ir_file, 'r', encoding='utf-8') as f:
            ir_data = json.load(f)
        
        ir = IntermediateRepresentation.from_dict(ir_data)
        
    except Exception as e:
        click.echo(f"Error loading IR: {e}", err=True)
        raise click.Abort()
    
    # Render to specified format
    try:
        if output_format == "wikitext":
            renderer = WikitextRenderer(lang)
            content = renderer.render(ir)
        else:  # html
            renderer = HTMLRenderer(lang)
            content = renderer.render(ir)
        
        # Write output
        output_path = Path(out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        click.echo(f"✓ Rendered {output_format} for {qid} in {lang}")
        click.echo(f"✓ Output saved to: {out}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--qid", required=True, help="Wikidata QID")
@click.option("--lang", default="en", help="Language for preview")
@click.option("--out", required=True, type=click.Path(), help="Output HTML file")
@click.option("--ir", "ir_file", help="IR file path (default: find in qid directory)")
def preview(qid: str, lang: str, out: str, ir_file: Optional[str]) -> None:
    """Generate HTML preview of the merged article."""
    
    # This is essentially the same as render with format=html
    # But also generates attribution files
    
    # Find IR file if not specified
    if not ir_file:
        possible_paths = [
            f"./out/{qid}/onepage.ir.json",
            f"./{qid}/onepage.ir.json",
            "./onepage.ir.json",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                ir_file = path
                break
        
        if not ir_file:
            click.echo("Error: Could not find IR file. Specify with --ir option.", err=True)
            raise click.Abort()
    
    # Load IR
    try:
        with open(ir_file, 'r', encoding='utf-8') as f:
            ir_data = json.load(f)
        
        ir = IntermediateRepresentation.from_dict(ir_data)
        
    except Exception as e:
        click.echo(f"Error loading IR: {e}", err=True)
        raise click.Abort()
    
    try:
        # Generate HTML preview
        html_renderer = HTMLRenderer(lang)
        html_content = html_renderer.render(ir)
        
        # Write HTML
        output_path = Path(out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Generate attribution files
        attribution_gen = AttributionGenerator()
        
        # Attribution markdown
        attribution_md = attribution_gen.generate_attribution_markdown(ir)
        attribution_path = output_path.parent / "ATTRIBUTION.md"
        with open(attribution_path, 'w', encoding='utf-8') as f:
            f.write(attribution_md)
        
        # Attribution JSON
        attribution_json = attribution_gen.generate_attribution_json(ir)
        attribution_json_path = output_path.parent / "attribution.json"
        with open(attribution_json_path, 'w', encoding='utf-8') as f:
            f.write(attribution_json)
        
        click.echo(f"✓ Generated HTML preview for {qid} in {lang}")
        click.echo(f"✓ Preview: {out}")
        click.echo(f"✓ Attribution: {attribution_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--config", required=True, type=click.Path(exists=True), help="Configuration YAML file")
@click.option("--out", required=True, type=click.Path(), help="Output directory")
def run(config: str, out: str) -> None:
    """Run the complete pipeline using a configuration file."""
    try:
        config_obj = Config.from_file(Path(config))
        
        click.echo(f"Running complete pipeline with config: {config}")
        click.echo(f"QID: {config_obj.qid}")
        click.echo(f"Languages: {', '.join(config_obj.languages)}")
        
        output_path = Path(out)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Fetch
        click.echo("Step 1: Fetching articles...")
        fetcher = ArticleFetcher()
        fetch_result = fetcher.fetch_all(config_obj.qid, config_obj.languages, str(output_path))
        click.echo(f"✓ Fetched {len(fetch_result['articles'])} articles")
        
        # Step 2: Build IR
        click.echo("Step 2: Building merged IR...")
        builder = IRBuilder()
        build_result = builder.build_ir(str(output_path), config_obj.qid)
        
        # Save IR
        ir_file = output_path / "onepage.ir.json"
        with open(ir_file, 'w', encoding='utf-8') as f:
            f.write(build_result.ir.to_json())
        click.echo(f"✓ Built IR with {build_result.stats['total_claims']} claims")
        
        # Step 3: Render outputs
        click.echo("Step 3: Rendering outputs...")
        
        if "wikitext" in config_obj.emit:
            wikitext_renderer = WikitextRenderer(config_obj.base_language)
            wikitext = wikitext_renderer.render(build_result.ir)
            
            wikitext_file = output_path / f"onepage.{config_obj.base_language}.wikitext"
            with open(wikitext_file, 'w', encoding='utf-8') as f:
                f.write(wikitext)
            click.echo(f"✓ Wikitext: {wikitext_file}")
        
        if "html" in config_obj.emit:
            html_renderer = HTMLRenderer(config_obj.base_language)
            html_content = html_renderer.render(build_result.ir)
            
            html_file = output_path / f"preview.{config_obj.base_language}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            click.echo(f"✓ HTML preview: {html_file}")
        
        # Step 4: Generate attribution
        click.echo("Step 4: Generating attribution...")
        attribution_gen = AttributionGenerator()
        
        attribution_md = attribution_gen.generate_attribution_markdown(build_result.ir)
        attribution_file = output_path / "ATTRIBUTION.md"
        with open(attribution_file, 'w', encoding='utf-8') as f:
            f.write(attribution_md)
        
        click.echo(f"✓ Complete pipeline finished!")
        click.echo(f"✓ Output directory: {output_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()