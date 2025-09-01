"""Utilities for merging parsed Wikipedia articles."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple, Optional
import re

from .api import ArticleFetcher
from .models import Claim, Entity, IntermediateRepresentation, Section, Reference
from .parse import ParsedArticle, parse_wikitext
from .translate import TranslationService, TextCleaner


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
    """Merge article sections at the sentence level.

    Parameters
    ----------
    sections_list:
        Sequence of ``(language, sections)`` tuples where ``sections`` is a
        mapping of headings to raw wikitext content from that language.
    target_lang:
        Language code of the final merged article. Headings from other
        languages are translated to this language.
    """

    @staticmethod
    def merge(
        sections_list: Sequence[Tuple[str, Dict[str, str]]],
        target_lang: str = "en",
    ) -> Dict[str, str]:
        translator = TranslationService()
        grouped: Dict[str, List[str]] = defaultdict(list)

        # Process English articles first to establish base content
        english_sections = []
        non_english_sections = []
        
        for lang, sections in sections_list:
            if lang == target_lang:
                english_sections.append((lang, sections))
            else:
                non_english_sections.append((lang, sections))

        # Process English content first
        for lang, sections in english_sections:
            for heading, text in sections.items():
                clean_text = TextCleaner.extract_plain_text(text)
                if not clean_text or len(clean_text.strip()) < 10:
                    continue

                # Normalize heading
                heading_norm = heading.strip()
                
                sentences = [
                    TextCleaner.clean_sentence(s)
                    for s in re.split(r"(?<=[.!?]) +", clean_text)
                    if s.strip() and len(s.strip()) > 5
                ]

                for sentence in sentences:
                    if sentence and sentence not in grouped[heading_norm]:
                        grouped[heading_norm].append(sentence)

        # Then process non-English content, but only add if substantially different
        for lang, sections in non_english_sections:
            for heading, text in sections.items():
                clean_text = TextCleaner.extract_plain_text(text)
                if not clean_text or len(clean_text.strip()) < 10:
                    continue

                # Try to translate heading and skip if translation fails
                heading_norm = heading.strip()
                if lang != target_lang:
                    translated_heading, _ = translator.translate_to_english(heading, lang)
                    if translated_heading.startswith("[TRANSLATION UNAVAILABLE"):
                        # Skip untranslatable Hindi sections
                        continue
                    heading_norm = translated_heading.strip()

                # Normalize heading to ASCII if possible
                heading_ascii = heading_norm.encode("ascii", "ignore").decode().strip()
                if heading_ascii and len(heading_ascii) > 2:
                    heading_norm = heading_ascii
                elif lang != target_lang:
                    # Skip non-ASCII headings from non-English sources
                    continue

                sentences = [
                    TextCleaner.clean_sentence(s)
                    for s in re.split(r"(?<=[.!?]) +", clean_text)
                    if s.strip() and len(s.strip()) > 5
                ]

                # Only add non-English content if we don't have much English content
                if len(grouped.get(heading_norm, [])) < 2:
                    if lang != target_lang:
                        translations = translator.batch_translate(sentences, lang)
                        for original_sentence, (translated, confidence) in zip(sentences, translations):
                            if not translated.startswith("[TRANSLATION UNAVAILABLE"):
                                if translated not in grouped[heading_norm]:
                                    grouped[heading_norm].append(translated)
                            else:
                                # Skip untranslated content rather than include it
                                pass
                    else:
                        for sentence in sentences:
                            if sentence not in grouped[heading_norm]:
                                grouped[heading_norm].append(sentence)

        return {h: " ".join(sents) for h, sents in grouped.items() if sents}


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
    sections_merged = TextMerger.merge(
        [(lang, p.sections) for lang, p in zip(languages, parsed_articles)],
        target_lang=target_lang,
    )

    # Collect all references from parsed articles
    all_references = []
    for p in parsed_articles:
        all_references.extend(p.references)

    # Build a minimal IntermediateRepresentation
    ir = IntermediateRepresentation(entity=entity)

    # Add references to IR with better parsing
    for i, ref_content in enumerate(all_references):
        ref_id = f"ref_{i}"
        # Parse reference content to extract structured data
        ref = Reference(
            id=ref_id,
            title=_extract_title_from_ref(ref_content) or ref_content[:100],
            url=_extract_url_from_ref(ref_content),
            author=None,  # Could extract this too
            date=None,    # Could extract this too
            publisher=_extract_publisher_from_ref(ref_content),
            doi=_extract_doi_from_ref(ref_content)
        )
        ir.references[ref_id] = ref

    ref_ids = list(ir.references.keys())
    ref_per_section = max(1, len(ref_ids) // len(sections_merged)) if sections_merged else 0
    
    for i, (heading, text) in enumerate(sections_merged.items()):
        section_id = heading.lower().replace(' ', '_')
        claim_id = f"{section_id}_0"
        
        # Distribute references across sections more evenly
        start_idx = i * ref_per_section
        end_idx = min(start_idx + ref_per_section + 2, len(ref_ids))
        claim_sources = ref_ids[start_idx:end_idx] if ref_ids else []
        
        claim = Claim(id=claim_id, lang=target_lang, text=text, text_en=text, sources=claim_sources)
        ir.content[claim_id] = claim
        ir.sections.append(
            Section(id=section_id, title={target_lang: heading}, items=[claim_id], level=2)
        )

    ir.metadata["images"] = images
    ir.metadata["infobox"] = infobox

    return ir


def _extract_url_from_ref(ref_content: str) -> Optional[str]:
    """Extract URL from reference content."""
    import re
    # Look for url= parameter in citation templates
    url_match = re.search(r'url\s*=\s*([^\s|}\]]+)', ref_content)
    if url_match:
        url = url_match.group(1).strip()
        # Clean URL
        url = re.sub(r'^["\']|["\']$', '', url)  # Remove quotes
        return url
    
    # Look for raw URLs
    url_match = re.search(r'https?://[^\s|}\]]+', ref_content)
    if url_match:
        return url_match.group(0).strip()
    
    return None


def _extract_title_from_ref(ref_content: str) -> Optional[str]:
    """Extract title from reference content."""
    import re
    # Look for title= parameter
    title_match = re.search(r'title\s*=\s*([^|}\]]+)', ref_content)
    if title_match:
        title = title_match.group(1).strip()
        # Clean title
        title = re.sub(r'^["\']|["\']$', '', title)  # Remove quotes
        title = re.sub(r'\[\[([^|\]]+)(\|[^\]]+)?\]\]', r'\1', title)  # Remove wikilinks
        return title[:100]  # Limit length
    return None


def _extract_publisher_from_ref(ref_content: str) -> Optional[str]:
    """Extract publisher from reference content."""
    import re
    # Look for publisher= or website= parameter
    pub_match = re.search(r'(?:publisher|website)\s*=\s*([^|}\]]+)', ref_content)
    if pub_match:
        pub = pub_match.group(1).strip()
        pub = re.sub(r'^["\']|["\']$', '', pub)  # Remove quotes
        pub = re.sub(r'\[\[([^|\]]+)(\|[^\]]+)?\]\]', r'\1', pub)  # Remove wikilinks
        return pub[:50]
    return None


def _extract_doi_from_ref(ref_content: str) -> Optional[str]:
    """Extract DOI from reference content."""
    import re
    doi_match = re.search(r'doi\s*=\s*([^\s|}\]]+)', ref_content)
    if doi_match:
        return doi_match.group(1).strip()
    return None
