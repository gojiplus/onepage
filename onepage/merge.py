"""Utilities for merging parsed Wikipedia articles."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence

from .api import ArticleFetcher
from .models import Claim, Entity, IntermediateRepresentation, Section
from .parse import ParsedArticle, parse_wikitext


class ImageMerger:
    """Simple merger that unions images from multiple articles."""

    @staticmethod
    def merge(image_lists: Sequence[List[str]]) -> List[str]:
        merged: List[str] = []
        for images in image_lists:
            for image in images:
                if image not in merged:
                    merged.append(image)
        return merged


class InfoboxMerger:
    """Merge infobox dictionaries by unioning parameter values."""

    @staticmethod
    def merge(boxes: Sequence[Dict[str, str]]) -> Dict[str, List[str]]:
        merged: Dict[str, List[str]] = {}
        for box in boxes:
            for key, value in box.items():
                merged.setdefault(key, [])
                if value not in merged[key]:
                    merged[key].append(value)
        return merged


class TextMerger:
    """Merge article sections at the sentence level."""

    @staticmethod
    def merge(sections_list: Sequence[Dict[str, str]]) -> Dict[str, str]:
        grouped: Dict[str, List[str]] = defaultdict(list)
        for sections in sections_list:
            for heading, text in sections.items():
                sentences = [s.strip() for s in text.split('. ') if s.strip()]
                for sentence in sentences:
                    if sentence not in grouped[heading]:
                        grouped[heading].append(sentence)
        return {h: '. '.join(sents) for h, sents in grouped.items()}


def merge_article(qid: str, languages: List[str], target_lang: str = "en") -> IntermediateRepresentation:
    """High level pipeline: fetch, parse and merge article versions.

    Parameters
    ----------
    qid:
        Wikidata QID of the entity to merge.
    languages:
        Languages to retrieve.
    target_lang:
        Language used for the merged text.
    """

    fetcher = ArticleFetcher()
    fetched = fetcher.fetch_all(qid, languages, output_dir="./tmp")

    entity: Entity = fetched["entity"]

    parsed_articles: List[ParsedArticle] = []
    for article in fetched["articles"].values():
        parsed_articles.append(parse_wikitext(article["wikitext"]))

    images = ImageMerger.merge([p.images for p in parsed_articles])
    infobox = InfoboxMerger.merge([p.infobox for p in parsed_articles])
    sections_merged = TextMerger.merge([p.sections for p in parsed_articles])

    # Build a minimal IntermediateRepresentation
    ir = IntermediateRepresentation(entity=entity)

    for heading, text in sections_merged.items():
        section_id = heading.lower().replace(' ', '_')
        claim_id = f"{section_id}_0"
        claim = Claim(id=claim_id, lang=target_lang, text=text, text_en=text, sources=[])
        ir.content[claim_id] = claim
        ir.sections.append(
            Section(id=section_id, title={target_lang: heading}, items=[claim_id], level=2)
        )

    ir.metadata["images"] = images
    ir.metadata["infobox"] = infobox

    return ir
