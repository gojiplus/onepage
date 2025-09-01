"""Wikidata API client for fetching entity information and sitelinks."""

import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

from ..core.models import Entity


class WikidataClient:
    """Client for interacting with the Wikidata API."""
    
    def __init__(self, base_url: str = "https://www.wikidata.org/w/api.php"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "onepage/0.1.0 (https://github.com/soodoku/onepage)"
        })
    
    def get_entity(self, qid: str, languages: Optional[List[str]] = None) -> Entity:
        """
        Fetch entity data from Wikidata.
        
        Args:
            qid: Wikidata QID (e.g., "Q1058")
            languages: List of language codes to fetch labels/descriptions for
            
        Returns:
            Entity object with labels, descriptions, and sitelinks
        """
        if languages is None:
            languages = ["en"]
        
        # Fetch entity data
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "props": "labels|descriptions|aliases|sitelinks",
            "languages": "|".join(languages),
            "sitefilter": "|".join([f"{lang}wiki" for lang in languages]),
        }
        
        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "entities" not in data or qid not in data["entities"]:
            raise ValueError(f"Entity {qid} not found in Wikidata")
        
        entity_data = data["entities"][qid]
        
        # Extract labels
        labels = {}
        if "labels" in entity_data:
            for lang, label_data in entity_data["labels"].items():
                labels[lang] = label_data["value"]
        
        # Extract descriptions
        descriptions = {}
        if "descriptions" in entity_data:
            for lang, desc_data in entity_data["descriptions"].items():
                descriptions[lang] = desc_data["value"]
        
        # Extract aliases
        aliases = {}
        if "aliases" in entity_data:
            for lang, alias_list in entity_data["aliases"].items():
                aliases[lang] = [alias["value"] for alias in alias_list]
        
        return Entity(
            qid=qid,
            labels=labels,
            descriptions=descriptions,
            aliases=aliases,
        )
    
    def get_sitelinks(self, qid: str, languages: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Get sitelinks (Wikipedia article titles) for an entity.
        
        Args:
            qid: Wikidata QID
            languages: List of language codes to get sitelinks for
            
        Returns:
            Dictionary mapping language codes to article titles
        """
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "props": "sitelinks",
        }
        
        if languages:
            params["sitefilter"] = "|".join([f"{lang}wiki" for lang in languages])
        
        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "entities" not in data or qid not in data["entities"]:
            raise ValueError(f"Entity {qid} not found in Wikidata")
        
        entity_data = data["entities"][qid]
        sitelinks = {}
        
        if "sitelinks" in entity_data:
            for site, sitelink_data in entity_data["sitelinks"].items():
                if site.endswith("wiki"):
                    lang = site[:-4]  # Remove "wiki" suffix
                    if not languages or lang in languages:
                        sitelinks[lang] = sitelink_data["title"]
        
        return sitelinks
    
    def get_entity_claims(self, qid: str, properties: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get claims (statements) for a Wikidata entity.
        
        Args:
            qid: Wikidata QID
            properties: Optional list of property IDs to filter by
            
        Returns:
            Dictionary of property ID to list of claims
        """
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "props": "claims",
        }
        
        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "entities" not in data or qid not in data["entities"]:
            raise ValueError(f"Entity {qid} not found in Wikidata")
        
        entity_data = data["entities"][qid]
        claims = {}
        
        if "claims" in entity_data:
            for prop_id, claim_list in entity_data["claims"].items():
                if not properties or prop_id in properties:
                    claims[prop_id] = claim_list
        
        return claims