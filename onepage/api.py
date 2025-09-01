"""API clients for fetching Wikipedia and Wikidata content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .models import Entity, Provenance


class WikidataClient:
    """Client for interacting with the Wikidata API."""

    def __init__(self, base_url: str = "https://www.wikidata.org/w/api.php"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "onepage/0.1.0 (https://github.com/soodoku/onepage)"}
        )

    def get_entity(self, qid: str, languages: Optional[List[str]] = None) -> Entity:
        """Fetch entity data from Wikidata."""
        if languages is None:
            languages = ["en"]

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

        labels: Dict[str, str] = {}
        for lang, label_data in entity_data.get("labels", {}).items():
            labels[lang] = label_data["value"]

        descriptions: Dict[str, str] = {}
        for lang, desc_data in entity_data.get("descriptions", {}).items():
            descriptions[lang] = desc_data["value"]

        aliases: Dict[str, List[str]] = {}
        for lang, alias_list in entity_data.get("aliases", {}).items():
            aliases[lang] = [alias["value"] for alias in alias_list]

        return Entity(qid=qid, labels=labels, descriptions=descriptions, aliases=aliases)

    def get_sitelinks(self, qid: str, languages: Optional[List[str]] = None) -> Dict[str, str]:
        """Get sitelinks (Wikipedia article titles) for an entity."""
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
        sitelinks: Dict[str, str] = {}
        for site, sitelink_data in entity_data.get("sitelinks", {}).items():
            if site.endswith("wiki"):
                lang = site[:-4]
                if not languages or lang in languages:
                    sitelinks[lang] = sitelink_data["title"]
        return sitelinks

    def get_entity_claims(self, qid: str, properties: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get claims (statements) for a Wikidata entity."""
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
        claims: Dict[str, List[Dict[str, Any]]] = {}
        for prop_id, claim_list in entity_data.get("claims", {}).items():
            if not properties or prop_id in properties:
                claims[prop_id] = claim_list
        return claims


class WikipediaClient:
    """Client for fetching Wikipedia article content."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "onepage/0.1.0 (https://github.com/soodoku/onepage)"}
        )

    def _get_api_url(self, language: str) -> str:
        return f"https://{language}.wikipedia.org/w/api.php"

    def get_article_wikitext(self, title: str, language: str) -> Dict[str, Any]:
        api_url = self._get_api_url(language)
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
            "provenance": Provenance(wiki=f"{language}wiki", title=title, rev_id=rev_id),
        }

    def get_article_extract(self, title: str, language: str, sentences: int = 10) -> Dict[str, Any]:
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
        return {"title": title, "language": language, "extract": extract, "page_id": int(page_id)}

    def get_article_sections(self, title: str, language: str) -> List[Dict[str, Any]]:
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


class ArticleFetcher:
    """Fetch Wikipedia articles across languages for a given QID."""

    def __init__(self) -> None:
        self.wikidata = WikidataClient()
        self.wikipedia = WikipediaClient()

    def fetch_all(self, qid: str, languages: List[str], output_dir: str) -> Dict[str, Any]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        entity = self.wikidata.get_entity(qid, languages)
        sitelinks = self.wikidata.get_sitelinks(qid, languages)
        claims = self.wikidata.get_entity_claims(qid)

        articles: Dict[str, Any] = {}
        for lang in languages:
            if lang in sitelinks:
                try:
                    article_data = self.wikipedia.get_article_wikitext(sitelinks[lang], lang)
                    articles[lang] = article_data
                    article_file = output_path / f"{lang}.json"
                    with open(article_file, "w", encoding="utf-8") as f:
                        serializable = {**article_data}
                        if "provenance" in serializable:
                            serializable["provenance"] = article_data["provenance"].to_dict()
                        json.dump(serializable, f, indent=2, ensure_ascii=False)
                except Exception as e:  # pragma: no cover - network errors
                    print(f"Warning: Could not fetch {lang} article: {e}")

        entity_file = output_path / "entity.json"
        with open(entity_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "qid": entity.qid,
                    "labels": entity.labels,
                    "descriptions": entity.descriptions,
                    "aliases": entity.aliases,
                    "sitelinks": sitelinks,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        claims_file = output_path / "claims.json"
        with open(claims_file, "w", encoding="utf-8") as f:
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

        fetch_file = output_path / "fetch_metadata.json"
        with open(fetch_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "qid": result["qid"],
                    "sitelinks": result["sitelinks"],
                    "languages_fetched": result["languages_fetched"],
                    "languages_requested": result["languages_requested"],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        return result
