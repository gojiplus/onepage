"""Content merger pipeline orchestrator using modular mergers."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .content_classifier import ContentClassifier, ClassifiedContent
from .mergers.text_merger import TextMerger, MergedTextSection
from .mergers.fact_merger import FactMerger, MergedInfobox
from .mergers.media_merger import MediaMerger, MergedMediaItem
from .mergers.reference_merger import ReferenceMerger, MergedReference
from .translation import TranslationService
from ..core.models import Provenance, Claim, Section, Reference, Fact
import uuid


@dataclass
class ContentMergeResult:
    """Result of content merging operation."""
    text_sections: List[MergedTextSection]
    infobox: Optional[MergedInfobox]
    media_items: List[MergedMediaItem]
    references: List[MergedReference]
    stats: Dict[str, Any]


class ContentMergerPipeline:
    """Orchestrates content-type-aware merging using specialized mergers."""
    
    def __init__(self):
        self.classifier = ContentClassifier()
        self.text_merger = TextMerger()
        self.fact_merger = FactMerger()
        self.media_merger = MediaMerger()
        self.reference_merger = ReferenceMerger()
        self.translator = TranslationService()
        
    def merge_content(self, input_dir: str) -> ContentMergeResult:
        """
        Perform content-type-aware merging of Wikipedia articles.
        
        Args:
            input_dir: Directory containing fetched Wikipedia content
            
        Returns:
            ContentMergeResult with merged content by type
        """
        input_path = Path(input_dir)
        
        # Load and classify all content
        all_classified_content = self._load_and_classify_content(input_path)
        
        # Translate non-English content
        translated_content = self._translate_classified_content(all_classified_content)
        
        # Merge by content type
        text_sections = self.text_merger.merge_text_content(translated_content)
        infobox = self.fact_merger.merge_infoboxes(translated_content)
        media_items = self.media_merger.merge_media_content(translated_content)
        references = self.reference_merger.merge_references(translated_content)
        
        # Deduplicate media
        media_items = self.media_merger.deduplicate_media(media_items)
        
        # Calculate statistics
        stats = {
            'total_classified_items': len(all_classified_content),
            'translated_items': len([c for c in translated_content if hasattr(c, 'text_en')]),
            'text_sections': len(text_sections),
            'infobox_parameters': len(infobox.parameters) if infobox else 0,
            'media_items': len(media_items),
            'references': len(references),
            'languages_processed': len(set(c.language for c in all_classified_content))
        }
        
        return ContentMergeResult(
            text_sections=text_sections,
            infobox=infobox,
            media_items=media_items,
            references=references,
            stats=stats
        )
    
    def _load_and_classify_content(self, input_path: Path) -> List[ClassifiedContent]:
        """Load articles and classify all content by type."""
        all_classified = []
        
        # Load all article files
        for article_file in input_path.glob("*.json"):
            if article_file.name in ["entity.json", "claims.json", "fetch_metadata.json"]:
                continue
                
            lang = article_file.stem
            
            with open(article_file, 'r', encoding='utf-8') as f:
                article_data = json.load(f)
            
            wikitext = article_data["wikitext"]
            provenance = Provenance(
                wiki=article_data["provenance"]["wiki"],
                title=article_data["provenance"]["title"],
                rev_id=article_data["provenance"]["rev_id"]
            )
            
            # Classify content in this article
            classified_items = self.classifier.classify_article(wikitext, lang, provenance)
            all_classified.extend(classified_items)
            
        return all_classified
    
    def _translate_classified_content(self, classified_content: List[ClassifiedContent]) -> List[ClassifiedContent]:
        """Translate non-English classified content."""
        translated_content = []
        
        for item in classified_content:
            if item.language != 'en':
                # Translate text content
                if item.content_type.value == 'text':
                    clean_text = item.structured_data.get('clean_text', '')
                    if clean_text:
                        translated_text = self.translator.translate_text(clean_text, item.language, 'en')
                        item.structured_data['clean_text_en'] = translated_text
                        
                # Translate section titles
                section_title = item.structured_data.get('section_title', '')
                if section_title:
                    translated_title = self.translator.translate_text(section_title, item.language, 'en')
                    item.structured_data['section_title_en'] = translated_title
                    
                # Translate infobox parameters
                if item.content_type.value == 'infobox':
                    parameters = item.structured_data.get('parameters', {})
                    translated_params = {}
                    for key, value in parameters.items():
                        if value and len(value.strip()) > 3:  # Only translate substantial values
                            try:
                                translated_value = self.translator.translate_text(value, item.language, 'en')
                                translated_params[key] = translated_value
                            except:
                                translated_params[key] = value  # Keep original if translation fails
                        else:
                            translated_params[key] = value
                    item.structured_data['parameters_en'] = translated_params
                    
                # Translate media captions
                if item.content_type.value == 'image':
                    caption = item.structured_data.get('caption', '')
                    if caption:
                        translated_caption = self.translator.translate_text(caption, item.language, 'en')
                        item.structured_data['caption_en'] = translated_caption
                        
            translated_content.append(item)
            
        return translated_content
    
    def convert_to_ir_format(self, merge_result: ContentMergeResult, entity: Any) -> Dict[str, Any]:
        """Convert merged content to IR format compatible with existing pipeline."""
        # Convert text sections to claims
        claims = {}
        sections = []
        
        for text_section in merge_result.text_sections:
            # Create section
            section_id = text_section.section_id
            section = Section(
                id=section_id,
                title={'en': text_section.title},
                items=[]
            )
            
            # Create claim from merged text
            claim_id = f"c_{uuid.uuid4().hex[:8]}"
            claim = Claim(
                id=claim_id,
                lang='en',
                text=text_section.merged_text,
                sources=[],
                provenance=text_section.source_provenances[0] if text_section.source_provenances else None
            )
            
            claims[claim_id] = claim
            section.items.append(claim_id)
            sections.append(section)
        
        # Convert infobox to facts
        facts = {}
        if merge_result.infobox:
            for param_name, param_value in merge_result.infobox.parameters.items():
                fact_id = f"f_infobox_{param_name}"
                fact = Fact(
                    id=fact_id,
                    property=param_name,
                    value=param_value,
                    qualifiers={},
                    sources=[],
                    from_source="wikipedia_infobox"
                )
                facts[fact_id] = fact
        
        # Convert references
        references = {}
        for merged_ref in merge_result.references:
            ref = Reference(
                id=merged_ref.ref_id,
                url=merged_ref.url,
                title=merged_ref.title,
                date=merged_ref.date,
                author=", ".join(merged_ref.authors) if merged_ref.authors else None,
                publisher=merged_ref.publication
            )
            references[merged_ref.ref_id] = ref
        
        # Combine content
        content = {}
        content.update(claims)
        content.update(facts)
        
        return {
            'entity': entity,
            'sections': sections,
            'content': content,
            'references': references,
            'media_items': merge_result.media_items,
            'stats': merge_result.stats
        }