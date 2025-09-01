"""High-level fetcher that combines Wikidata and Wikipedia APIs."""

import json
import os
from pathlib import Path
from typing import Dict, List, Any

from .wikidata import WikidataClient
from .wikipedia import WikipediaClient
from ..core.models import Entity


class ArticleFetcher:
    """Fetches Wikipedia articles across languages for a given QID."""
    
    def __init__(self):
        self.wikidata = WikidataClient()
        self.wikipedia = WikipediaClient()
    
    def fetch_all(self, qid: str, languages: List[str], output_dir: str) -> Dict[str, Any]:
        """
        Fetch all articles for a QID across specified languages.
        
        Args:
            qid: Wikidata QID
            languages: List of language codes
            output_dir: Directory to save fetched content
            
        Returns:
            Dictionary with fetch results and metadata
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Get entity data and sitelinks
        entity = self.wikidata.get_entity(qid, languages)
        sitelinks = self.wikidata.get_sitelinks(qid, languages)
        
        # Get Wikidata claims for facts
        claims = self.wikidata.get_entity_claims(qid)
        
        # Fetch articles for each available language
        articles = {}
        for lang in languages:
            if lang in sitelinks:
                try:
                    article_data = self.wikipedia.get_article_wikitext(
                        sitelinks[lang], lang
                    )
                    articles[lang] = article_data
                    
                    # Save individual article data
                    article_file = output_path / f"{lang}.json"
                    with open(article_file, 'w', encoding='utf-8') as f:
                        json.dump(article_data, f, indent=2, ensure_ascii=False)
                        
                except Exception as e:
                    print(f"Warning: Could not fetch {lang} article: {e}")
        
        # Save entity metadata
        entity_file = output_path / "entity.json"
        with open(entity_file, 'w', encoding='utf-8') as f:
            json.dump({
                "qid": entity.qid,
                "labels": entity.labels,
                "descriptions": entity.descriptions,
                "aliases": entity.aliases,
                "sitelinks": sitelinks,
            }, f, indent=2, ensure_ascii=False)
        
        # Save Wikidata claims
        claims_file = output_path / "claims.json"
        with open(claims_file, 'w', encoding='utf-8') as f:
            json.dump(claims, f, indent=2, ensure_ascii=False)
        
        result = {
            "qid": qid,
            "entity": entity,
            "sitelinks": sitelinks,
            "articles": articles,
            "claims": claims,
            "languages_fetched": list(articles.keys()),
            "languages_requested": languages,
            "output_dir": str(output_path),
        }
        
        # Save fetch metadata
        fetch_file = output_path / "fetch_metadata.json"
        with open(fetch_file, 'w', encoding='utf-8') as f:
            json.dump({
                "qid": result["qid"],
                "sitelinks": result["sitelinks"],
                "languages_fetched": result["languages_fetched"],
                "languages_requested": result["languages_requested"],
            }, f, indent=2, ensure_ascii=False)
        
        return result