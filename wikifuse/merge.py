"""Utilities for merging parsed Wikipedia articles."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .api import ArticleFetcher
from .models import Claim, Entity, IntermediateRepresentation, Reference, Section
from .parse import ParsedArticle, parse_wikitext
from .translate import TextCleaner, TranslationService


class ImageMerger:
    """Simple merger that unions images from multiple articles."""

    @staticmethod
    def merge(image_lists: Sequence[list[str]]) -> list[str]:
        merged: list[str] = []
        for images in image_lists:
            for image in images:
                if image not in merged:
                    merged.append(image)
        return merged


class InfoboxMerger:
    """Merge infobox dictionaries by unioning parameter values."""

    @staticmethod
    def merge(boxes: Sequence[dict[str, str]]) -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}
        for box in boxes:
            for key, value in box.items():
                merged.setdefault(key, [])
                if value not in merged[key]:
                    merged[key].append(value)
        return merged


class TextMerger:
    """Merge article sections using LLM for intelligent merging.

    When LLM is available and enabled, uses LLM to intelligently merge
    sections from multiple language versions. Falls back to sentence-level
    merging when LLM is not available.

    Args:
        llm_service: Optional LLMService or MockLLMService instance.
        entity_name: Name of the entity being merged.
    """

    def __init__(self, llm_service: Any | None = None, entity_name: str = ""):
        self.llm = llm_service
        self.entity_name = entity_name
        self.translator = TranslationService()

    def merge(
        self,
        sections_list: Sequence[tuple[str, dict[str, str]]],
        target_lang: str = "en",
    ) -> dict[str, str]:
        """Merge sections from multiple language versions.

        Args:
            sections_list: Sequence of (language, sections) tuples.
            target_lang: Target language for the merged output.

        Returns:
            Dictionary mapping section headings to merged text.
        """
        if self.llm is not None:
            return self._merge_with_llm(sections_list, target_lang)
        return self._merge_fallback(sections_list, target_lang)

    def _merge_with_llm(
        self,
        sections_list: Sequence[tuple[str, dict[str, str]]],
        target_lang: str,
    ) -> dict[str, str]:
        """Merge sections using LLM."""
        grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

        for lang, sections in sections_list:
            for heading, text in sections.items():
                clean_text = TextCleaner.extract_plain_text(text)
                if not clean_text or len(clean_text.strip()) < 10:
                    continue

                heading_norm = self._normalize_heading(heading, lang, target_lang)

                if lang != target_lang:
                    translated, _ = self.translator.translate(
                        clean_text, lang, target_lang
                    )
                    clean_text = translated

                wiki = f"{lang}wiki"
                grouped[heading_norm].append((wiki, lang, clean_text))

        merged: dict[str, str] = {}
        for heading, section_list in grouped.items():
            merged_text = self.llm.merge_sections(
                section_list, self.entity_name, heading
            )
            if merged_text:
                merged[heading] = merged_text

        return merged

    def _merge_fallback(
        self,
        sections_list: Sequence[tuple[str, dict[str, str]]],
        target_lang: str,
    ) -> dict[str, str]:
        """Fallback merge using sentence-level deduplication."""
        grouped: dict[str, list[str]] = defaultdict(list)

        english_sections = []
        non_english_sections = []

        for lang, sections in sections_list:
            if lang == target_lang:
                english_sections.append((lang, sections))
            else:
                non_english_sections.append((lang, sections))

        for _lang, sections in english_sections:
            for heading, text in sections.items():
                clean_text = TextCleaner.extract_plain_text(text)
                if not clean_text or len(clean_text.strip()) < 10:
                    continue

                heading_norm = heading.strip()

                sentences = [
                    TextCleaner.clean_sentence(s)
                    for s in re.split(r"(?<=[.!?]) +", clean_text)
                    if s.strip() and len(s.strip()) > 5
                ]

                for sentence in sentences:
                    if sentence and sentence not in grouped[heading_norm]:
                        grouped[heading_norm].append(sentence)

        for lang, sections in non_english_sections:
            for heading, text in sections.items():
                clean_text = TextCleaner.extract_plain_text(text)
                if not clean_text or len(clean_text.strip()) < 10:
                    continue

                heading_norm = self._normalize_heading(heading, lang, target_lang)

                sentences = [
                    TextCleaner.clean_sentence(s)
                    for s in re.split(r"(?<=[.!?]) +", clean_text)
                    if s.strip() and len(s.strip()) > 5
                ]

                if lang != target_lang:
                    translations = self.translator.batch_translate(
                        sentences, lang, target_lang
                    )
                    for _original, (translated, _confidence) in zip(
                        sentences, translations, strict=False
                    ):
                        if translated not in grouped[heading_norm]:
                            grouped[heading_norm].append(translated)
                else:
                    for sentence in sentences:
                        if sentence not in grouped[heading_norm]:
                            grouped[heading_norm].append(sentence)

        return {h: " ".join(sents) for h, sents in grouped.items() if sents}

    def _normalize_heading(self, heading: str, lang: str, target_lang: str) -> str:
        """Normalize a section heading to the target language."""
        heading_norm = heading.strip()
        if heading_norm == "lead":
            return "lead"

        if lang != target_lang:
            translated_heading, _ = self.translator.translate(
                heading, lang, target_lang
            )
            heading_norm = translated_heading.strip()

        return heading_norm

    @staticmethod
    def merge_static(
        sections_list: Sequence[tuple[str, dict[str, str]]],
        target_lang: str = "en",
    ) -> dict[str, str]:
        """Static method for backward compatibility."""
        merger = TextMerger()
        return merger.merge(sections_list, target_lang)


def merge_article(
    qid: str,
    languages: list[str],
    target_lang: str = "en",
    use_llm: bool = True,
    llm_api_key: str | None = None,
    llm_model: str = "gpt-4o-mini",
) -> IntermediateRepresentation:
    """High level pipeline: fetch, parse and merge article versions.

    Parameters
    ----------
    qid:
        Wikidata QID of the entity to merge.
    languages:
        Languages to retrieve.
    target_lang:
        Language used for the merged text.
    use_llm:
        Whether to use LLM to order source passages.
    llm_api_key:
        OpenAI API key. If None, reads from OPENAI_API_KEY env var.
    llm_model:
        LLM model to use for merging.
    """
    fetcher = ArticleFetcher()
    fetched = fetcher.fetch_all(qid, languages, output_dir="./tmp")

    entity: Entity = fetched["entity"]
    entity_name = entity.labels.get(target_lang, entity.labels.get("en", qid))

    parsed_articles: list[ParsedArticle] = []
    languages_fetched = []
    for lang in languages:
        if lang in fetched["articles"]:
            parsed_articles.append(
                parse_wikitext(fetched["articles"][lang]["wikitext"])
            )
            languages_fetched.append(lang)

    images = ImageMerger.merge([p.images for p in parsed_articles])
    infobox = InfoboxMerger.merge([p.infobox for p in parsed_articles])

    llm_service = None
    if use_llm:
        api_key = llm_api_key or os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                from .llm import LLMService

                llm_service = LLMService(api_key=api_key, model=llm_model)
            except (ImportError, ValueError):
                pass

    text_merger = TextMerger(entity_name=entity_name)
    ir = IntermediateRepresentation(entity=entity)
    reference_ids: dict[str, str] = {}
    grouped: dict[str, list[Claim]] = {}
    for lang, parsed in zip(languages_fetched, parsed_articles, strict=True):
        source = fetched["articles"][lang]["provenance"]
        for heading, passages in parsed.passages.items():
            normalized = text_merger._normalize_heading(heading, lang, target_lang)
            claims = grouped.setdefault(normalized, [])
            for passage in passages:
                text = TextCleaner.extract_plain_text(passage.text)
                if not text:
                    continue
                if lang != target_lang:
                    text, _ = text_merger.translator.translate(text, lang, target_lang)
                sources = []
                for raw in passage.references:
                    if raw not in reference_ids:
                        ref_id = f"ref_{len(reference_ids)}"
                        reference_ids[raw] = ref_id
                        ir.references[ref_id] = Reference(
                            id=ref_id,
                            title=_extract_title_from_ref(raw) or raw[:100],
                            url=_extract_url_from_ref(raw),
                            publisher=_extract_publisher_from_ref(raw),
                            doi=_extract_doi_from_ref(raw),
                            wikitext=raw,
                        )
                    sources.append(reference_ids[raw])
                existing = next((claim for claim in claims if claim.text == text), None)
                if existing is not None:
                    existing.sources.extend(
                        ref for ref in sources if ref not in existing.sources
                    )
                    if source not in existing.provenance:
                        existing.provenance.append(source)
                else:
                    claim = Claim(
                        id=f"claim_{len(ir.content)}",
                        lang=target_lang,
                        text=text,
                        text_en=text if target_lang == "en" else None,
                        sources=sources,
                        provenance=[source],
                    )
                    claims.append(claim)
                    ir.content[claim.id] = claim

    for heading, claims in grouped.items():
        if not claims:
            continue
        if llm_service is not None:
            claims = llm_service.order_claims(claims, entity_name, heading)
        section_id = heading
        ir.sections.append(
            Section(
                id=section_id,
                title={target_lang: heading},
                items=[claim.id for claim in claims],
                level=2,
            )
        )

    ir.metadata["source_articles"] = [
        fetched["articles"][lang]["provenance"].to_dict() for lang in languages_fetched
    ]
    ir.metadata["images"] = images
    ir.metadata["infobox"] = infobox

    return ir


def _extract_url_from_ref(ref_content: str) -> str | None:
    """Extract URL from reference content."""
    url_match = re.search(r"url\s*=\s*([^\s|}\]]+)", ref_content)
    if url_match:
        url = url_match.group(1).strip()
        url = re.sub(r'^["\']|["\']$', "", url)
        return url

    url_match = re.search(r"https?://[^\s|}\]]+", ref_content)
    if url_match:
        return url_match.group(0).strip()

    return None


def _extract_title_from_ref(ref_content: str) -> str | None:
    """Extract title from reference content."""
    title_match = re.search(r"title\s*=\s*([^|}\]]+)", ref_content)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'^["\']|["\']$', "", title)
        title = re.sub(r"\[\[([^|\]]+)(\|[^\]]+)?\]\]", r"\1", title)
        return title[:100]
    return None


def _extract_publisher_from_ref(ref_content: str) -> str | None:
    """Extract publisher from reference content."""
    pub_match = re.search(r"(?:publisher|website)\s*=\s*([^|}\]]+)", ref_content)
    if pub_match:
        pub = pub_match.group(1).strip()
        pub = re.sub(r'^["\']|["\']$', "", pub)
        pub = re.sub(r"\[\[([^|\]]+)(\|[^\]]+)?\]\]", r"\1", pub)
        return pub[:50]
    return None


def _extract_doi_from_ref(ref_content: str) -> str | None:
    """Extract DOI from reference content."""
    doi_match = re.search(r"doi\s*=\s*([^\s|}\]]+)", ref_content)
    if doi_match:
        return doi_match.group(1).strip()
    return None
