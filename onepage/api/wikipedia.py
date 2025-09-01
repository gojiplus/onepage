"""Wikipedia API client for fetching article content."""

import requests
from typing import Dict, List, Optional, Any
from urllib.parse import quote

from ..core.models import Provenance


class WikipediaClient:
    """Client for fetching Wikipedia article content."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "onepage/0.1.0 (https://github.com/soodoku/onepage)"
        })
    
    def _get_api_url(self, language: str) -> str:
        """Get Wikipedia API URL for a given language."""
        return f"https://{language}.wikipedia.org/w/api.php"
    
    def get_article_wikitext(self, title: str, language: str) -> Dict[str, Any]:
        """
        Fetch the wikitext content of a Wikipedia article.
        
        Args:
            title: Article title
            language: Language code (e.g., "en", "hi")
            
        Returns:
            Dictionary with wikitext content and metadata
        """
        api_url = self._get_api_url(language)
        
        # First, get the page info and current revision ID
        page_params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "info|revisions",
            "rvprop": "ids|timestamp|user|comment",
            "rvlimit": 1,
        }
        
        response = self.session.get(api_url, params=page_params)
        response.raise_for_status()
        data = response.json()
        
        if "query" not in data or "pages" not in data["query"]:
            raise ValueError(f"Could not fetch page info for {title}")
        
        pages = data["query"]["pages"]
        if not pages:
            raise ValueError(f"No pages found for title: {title}")
        
        page_id = list(pages.keys())[0]
        if page_id == "-1":
            raise ValueError(f"Page not found: {title}")
        
        page_info = pages[page_id]
        if "revisions" not in page_info:
            raise ValueError(f"No revisions found for: {title}")
        
        revision = page_info["revisions"][0]
        rev_id = revision["revid"]
        
        # Now fetch the wikitext content
        content_params = {
            "action": "query",
            "format": "json",
            "pageids": page_id,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
        }
        
        response = self.session.get(api_url, params=content_params)
        response.raise_for_status()
        data = response.json()
        
        page_data = data["query"]["pages"][page_id]
        if "revisions" not in page_data:
            raise ValueError(f"Could not fetch content for {title}")
        
        wikitext = page_data["revisions"][0]["slots"]["main"]["*"]
        
        return {
            "title": title,
            "language": language,
            "wikitext": wikitext,
            "page_id": int(page_id),
            "rev_id": rev_id,
            "timestamp": revision["timestamp"],
            "provenance": Provenance(
                wiki=f"{language}wiki",
                title=title,
                rev_id=rev_id,
            ),
        }
    
    def get_article_extract(self, title: str, language: str, 
                          sentences: int = 10) -> Dict[str, Any]:
        """
        Get a plain text extract of an article (useful for quick summaries).
        
        Args:
            title: Article title
            language: Language code
            sentences: Number of sentences to extract
            
        Returns:
            Dictionary with extract and metadata
        """
        api_url = self._get_api_url(language)
        
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts",
            "exsentences": sentences,
            "explaintext": True,
        }
        
        response = self.session.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "query" not in data or "pages" not in data["query"]:
            raise ValueError(f"Could not fetch extract for {title}")
        
        pages = data["query"]["pages"]
        page_id = list(pages.keys())[0]
        
        if page_id == "-1":
            raise ValueError(f"Page not found: {title}")
        
        page_data = pages[page_id]
        extract = page_data.get("extract", "")
        
        return {
            "title": title,
            "language": language,
            "extract": extract,
            "page_id": int(page_id),
        }
    
    def get_article_sections(self, title: str, language: str) -> List[Dict[str, Any]]:
        """
        Get the section structure of a Wikipedia article.
        
        Args:
            title: Article title  
            language: Language code
            
        Returns:
            List of sections with their metadata
        """
        api_url = self._get_api_url(language)
        
        params = {
            "action": "parse",
            "format": "json",
            "page": title,
            "prop": "sections",
        }
        
        response = self.session.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "parse" not in data or "sections" not in data["parse"]:
            raise ValueError(f"Could not fetch sections for {title}")
        
        return data["parse"]["sections"]
    
    def search_articles(self, query: str, language: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for Wikipedia articles.
        
        Args:
            query: Search query
            language: Language code
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        api_url = self._get_api_url(language)
        
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
        }
        
        response = self.session.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "query" not in data or "search" not in data["query"]:
            return []
        
        return data["query"]["search"]