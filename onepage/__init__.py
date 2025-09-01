"""onepage: Merge Wikipedia articles across languages into one comprehensive page."""

from .api import ArticleFetcher, WikidataClient, WikipediaClient
from .models import (
    Claim,
    Entity,
    Fact,
    IntermediateRepresentation,
    Provenance,
    Reference,
    Section,
)

__all__ = [
    "ArticleFetcher",
    "WikidataClient",
    "WikipediaClient",
    "Claim",
    "Entity",
    "Fact",
    "IntermediateRepresentation",
    "Provenance",
    "Reference",
    "Section",
]

__version__ = "0.1.0"