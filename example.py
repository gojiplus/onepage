#!/usr/bin/env python3
"""Example usage of onepage library."""

import asyncio
from pathlib import Path

from onepage.api.fetcher import ArticleFetcher
from onepage.processing.builder import IRBuilder
from onepage.renderers.wikitext import WikitextRenderer
from onepage.renderers.html import HTMLRenderer
from onepage.renderers.attribution import AttributionGenerator


def main():
    """Run example merge of Wikipedia articles."""
    
    print("onepage Example: Merging Wikipedia articles for Q1058 (Narendra Modi)")
    print("=" * 70)
    
    qid = "Q1058"
    languages = ["en", "hi"]
    output_dir = "./example_output"
    
    try:
        # Step 1: Fetch articles
        print("\n1. Fetching articles...")
        fetcher = ArticleFetcher()
        fetch_result = fetcher.fetch_all(qid, languages, output_dir)
        
        print(f"   ✓ Fetched {len(fetch_result['articles'])} articles")
        print(f"   ✓ Languages: {', '.join(fetch_result['languages_fetched'])}")
        
        # Step 2: Build IR
        print("\n2. Building Intermediate Representation...")
        builder = IRBuilder()
        build_result = builder.build_ir(output_dir, qid)
        
        print(f"   ✓ Processed {build_result.stats['total_claims']} claims")
        print(f"   ✓ Created {build_result.stats['alignment_clusters']} alignment clusters")
        print(f"   ✓ Canonicalized {build_result.stats['canonical_references']} references")
        
        # Save IR
        ir_file = Path(output_dir) / "onepage.ir.json"
        with open(ir_file, 'w', encoding='utf-8') as f:
            f.write(build_result.ir.to_json())
        print(f"   ✓ IR saved to: {ir_file}")
        
        # Step 3: Render wikitext
        print("\n3. Rendering wikitext...")
        wikitext_renderer = WikitextRenderer("en")
        wikitext = wikitext_renderer.render(build_result.ir)
        
        wikitext_file = Path(output_dir) / "onepage.en.wikitext"
        with open(wikitext_file, 'w', encoding='utf-8') as f:
            f.write(wikitext)
        print(f"   ✓ Wikitext saved to: {wikitext_file}")
        
        # Step 4: Generate HTML preview
        print("\n4. Generating HTML preview...")
        html_renderer = HTMLRenderer("en")
        html_content = html_renderer.render(build_result.ir)
        
        html_file = Path(output_dir) / "preview.en.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"   ✓ HTML preview saved to: {html_file}")
        
        # Step 5: Generate attribution
        print("\n5. Generating attribution files...")
        attribution_gen = AttributionGenerator()
        
        attribution_md = attribution_gen.generate_attribution_markdown(build_result.ir)
        attribution_file = Path(output_dir) / "ATTRIBUTION.md"
        with open(attribution_file, 'w', encoding='utf-8') as f:
            f.write(attribution_md)
        
        attribution_json = attribution_gen.generate_attribution_json(build_result.ir)
        attribution_json_file = Path(output_dir) / "attribution.json"
        with open(attribution_json_file, 'w', encoding='utf-8') as f:
            f.write(attribution_json)
        
        print(f"   ✓ Attribution files saved to: {Path(output_dir)}")
        
        print("\n" + "=" * 70)
        print("✓ Example completed successfully!")
        print(f"\nOutput files:")
        print(f"  - IR: {ir_file}")
        print(f"  - Wikitext: {wikitext_file}")
        print(f"  - HTML: {html_file}")
        print(f"  - Attribution: {attribution_file}")
        
        # Show some stats
        stats = attribution_gen.generate_contribution_stats(build_result.ir)
        print(f"\nStats:")
        print(f"  - Total content items: {stats['total_content_items']}")
        print(f"  - Languages processed: {list(stats['by_language'].keys())}")
        print(f"  - Sections: {list(stats['by_section'].keys())}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()