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
                if heading_norm is None:
                    continue

                if lang != target_lang:
                    translated, _ = self.translator.translate_to_english(
                        clean_text, lang
                    )
                    if translated.startswith("[TRANSLATION UNAVAILABLE"):
                        continue
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
                if heading_norm is None:
                    continue

                sentences = [
                    TextCleaner.clean_sentence(s)
                    for s in re.split(r"(?<=[.!?]) +", clean_text)
                    if s.strip() and len(s.strip()) > 5
                ]

                if lang != target_lang:
                    translations = self.translator.batch_translate(sentences, lang)
                    for _original, (translated, _confidence) in zip(
                        sentences, translations, strict=False
                    ):
                        if (
                            not translated.startswith("[TRANSLATION UNAVAILABLE")
                            and translated not in grouped[heading_norm]
                        ):
                            grouped[heading_norm].append(translated)
                else:
                    for sentence in sentences:
                        if sentence not in grouped[heading_norm]:
                            grouped[heading_norm].append(sentence)

        return {h: " ".join(sents) for h, sents in grouped.items() if sents}

    def _normalize_heading(
        self, heading: str, lang: str, target_lang: str
    ) -> str | None:
        """Normalize a section heading to the target language."""
        heading_norm = heading.strip()

        if lang != target_lang:
            translated_heading, _ = self.translator.translate_to_english(heading, lang)
            if translated_heading.startswith("[TRANSLATION UNAVAILABLE"):
                return None
            heading_norm = translated_heading.strip()

        heading_ascii = heading_norm.encode("ascii", "ignore").decode().strip()
        if heading_ascii and len(heading_ascii) > 2:
            heading_norm = heading_ascii
        elif lang != target_lang:
            return None

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
        Whether to use LLM for intelligent text merging.
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

    text_merger = TextMerger(llm_service=llm_service, entity_name=entity_name)
    sections_merged = text_merger.merge(
        [
            (lang, p.sections)
            for lang, p in zip(languages_fetched, parsed_articles, strict=False)
        ],
        target_lang=target_lang,
    )

    all_references = []
    for p in parsed_articles:
        all_references.extend(p.references)

    ir = IntermediateRepresentation(entity=entity)

    for i, ref_content in enumerate(all_references):
        ref_id = f"ref_{i}"
        ref = Reference(
            id=ref_id,
            title=_extract_title_from_ref(ref_content) or ref_content[:100],
            url=_extract_url_from_ref(ref_content),
            author=None,
            date=None,
            publisher=_extract_publisher_from_ref(ref_content),
            doi=_extract_doi_from_ref(ref_content),
        )
        ir.references[ref_id] = ref

    ref_ids = list(ir.references.keys())
    ref_per_section = (
        max(1, len(ref_ids) // len(sections_merged)) if sections_merged else 0
    )

    for i, (heading, text) in enumerate(sections_merged.items()):
        section_id = heading.lower().replace(" ", "_")
        claim_id = f"{section_id}_0"

        start_idx = i * ref_per_section
        end_idx = min(start_idx + ref_per_section + 2, len(ref_ids))
        claim_sources = ref_ids[start_idx:end_idx] if ref_ids else []

        claim = Claim(
            id=claim_id,
            lang=target_lang,
            text=text,
            text_en=text,
            sources=claim_sources,
        )
        ir.content[claim_id] = claim
        ir.sections.append(
            Section(
                id=section_id, title={target_lang: heading}, items=[claim_id], level=2
            )
        )

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
