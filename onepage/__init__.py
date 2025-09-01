"""onepage: Merge Wikipedia articles across languages into one comprehensive page."""

from .api import ArticleFetcher, WikidataClient, WikipediaClient
from .merge import (
    ImageMerger,
    InfoboxMerger,
    TextMerger,
    merge_article,
)
from .models import (
    Claim,
    Entity,
    Fact,
    IntermediateRepresentation,
    Provenance,
    Reference,
    Section,
)
from .parse import ParsedArticle, parse_wikitext

__all__ = [
    "ArticleFetcher",
    "WikidataClient",
    "WikipediaClient",
    "ImageMerger",
    "InfoboxMerger",
    "TextMerger",
    "merge_article",
    "parse_wikitext",
    "ParsedArticle",
    "Claim",
    "Entity",
    "Fact",
    "IntermediateRepresentation",
    "Provenance",
    "Reference",
    "Section",
]

__version__ = "0.1.0"