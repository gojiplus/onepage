"""Classify Wikipedia content into different types for specialized merging."""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import wikitextparser as wtp

from ..core.models import Provenance


class ContentType(Enum):
    """Types of Wikipedia content requiring different merge strategies."""
    TEXT = "text"           # Regular prose text
    INFOBOX = "infobox"     # Structured infobox data  
    IMAGE = "image"         # Images and media files
    REFERENCE = "reference" # Citations and references
    CATEGORY = "category"   # Article categories
    TEMPLATE = "template"   # Templates (navboxes, etc.)
    TABLE = "table"         # Data tables
    LIST = "list"           # Bulleted/numbered lists


@dataclass 
class ClassifiedContent:
    """A piece of content with its classification."""
    content_type: ContentType
    raw_content: str
    structured_data: Dict[str, Any]
    section_id: str
    language: str
    provenance: Provenance


class ContentClassifier:
    """Classifies Wikipedia content by type for specialized processing."""
    
    def __init__(self):
        self.infobox_templates = {
            'infobox', 'geobox', 'taxobox', 'chembox', 'drugbox', 
            'company infobox', 'person infobox', 'officeholder'
        }
        
    def classify_article(self, wikitext: str, language: str, 
                        provenance: Provenance) -> List[ClassifiedContent]:
        """
        Classify all content in a Wikipedia article by type.
        
        Args:
            wikitext: Raw wikitext content
            language: Language code
            provenance: Source provenance
            
        Returns:
            List of classified content items
        """
        parsed = wtp.parse(wikitext)
        classified_items = []
        
        # 1. Extract and classify infoboxes
        infoboxes = self._extract_infoboxes(parsed, language, provenance)
        classified_items.extend(infoboxes)
        
        # 2. Extract and classify images
        images = self._extract_images(parsed, language, provenance)
        classified_items.extend(images)
        
        # 3. Extract and classify categories
        categories = self._extract_categories(parsed, language, provenance)
        classified_items.extend(categories)
        
        # 4. Extract and classify references
        references = self._extract_references(parsed, language, provenance)
        classified_items.extend(references)
        
        # 5. Extract and classify text content by section
        text_content = self._extract_text_content(parsed, language, provenance)
        classified_items.extend(text_content)
        
        return classified_items
    
    def _extract_infoboxes(self, parsed: wtp.WikiList, language: str, 
                          provenance: Provenance) -> List[ClassifiedContent]:
        """Extract infobox content."""
        infoboxes = []
        
        for template in parsed.templates:
            template_name = str(template.name).strip().lower()
            
            if any(infobox_type in template_name for infobox_type in self.infobox_templates):
                # Parse infobox parameters
                params = {}
                for arg in template.arguments:
                    if arg.name and arg.value:
                        key = str(arg.name).strip()
                        value = str(arg.value).strip()
                        if key and value:
                            params[key] = value
                
                infoboxes.append(ClassifiedContent(
                    content_type=ContentType.INFOBOX,
                    raw_content=str(template),
                    structured_data={
                        'template_name': template_name,
                        'parameters': params
                    },
                    section_id='infobox',
                    language=language,
                    provenance=provenance
                ))
        
        return infoboxes
    
    def _extract_images(self, parsed: wtp.WikiList, language: str,
                       provenance: Provenance) -> List[ClassifiedContent]:
        """Extract image/media content."""
        images = []
        
        # Find File: and Image: links
        for wikilink in parsed.wikilinks:
            target = str(wikilink.target).strip()
            if target.lower().startswith(('file:', 'image:')):
                
                # Extract image metadata
                metadata = {
                    'filename': target,
                    'caption': str(wikilink.text) if wikilink.text else '',
                    'parameters': []
                }
                
                # Parse image parameters (thumb, right, 200px, etc.)
                if '|' in str(wikilink):
                    parts = str(wikilink).split('|')[1:]  # Skip filename
                    metadata['parameters'] = [p.strip() for p in parts if p.strip()]
                
                images.append(ClassifiedContent(
                    content_type=ContentType.IMAGE,
                    raw_content=str(wikilink),
                    structured_data=metadata,
                    section_id='media',
                    language=language,
                    provenance=provenance
                ))
        
        return images
    
    def _extract_categories(self, parsed: wtp.WikiList, language: str,
                           provenance: Provenance) -> List[ClassifiedContent]:
        """Extract category information."""
        categories = []
        
        for wikilink in parsed.wikilinks:
            target = str(wikilink.target).strip()
            if target.lower().startswith('category:'):
                category_name = target[9:]  # Remove 'Category:' prefix
                
                categories.append(ClassifiedContent(
                    content_type=ContentType.CATEGORY,
                    raw_content=str(wikilink),
                    structured_data={'category': category_name},
                    section_id='categories',
                    language=language,
                    provenance=provenance
                ))
        
        return categories
    
    def _extract_references(self, parsed: wtp.WikiList, language: str,
                           provenance: Provenance) -> List[ClassifiedContent]:
        """Extract reference/citation content."""
        references = []
        
        # Extract ref tags
        for tag in parsed.get_tags("ref"):
            ref_content = str(tag.contents) if tag.contents else ""
            
            references.append(ClassifiedContent(
                content_type=ContentType.REFERENCE,
                raw_content=str(tag),
                structured_data={
                    'ref_content': ref_content,
                    'ref_type': 'ref_tag'
                },
                section_id='references',
                language=language,
                provenance=provenance
            ))
        
        # Extract citation templates
        for template in parsed.templates:
            template_name = str(template.name).strip().lower()
            if template_name.startswith('cite'):
                # Parse citation parameters
                params = {}
                for arg in template.arguments:
                    if arg.name and arg.value:
                        key = str(arg.name).strip()
                        value = str(arg.value).strip()
                        if key and value:
                            params[key] = value
                
                references.append(ClassifiedContent(
                    content_type=ContentType.REFERENCE,
                    raw_content=str(template),
                    structured_data={
                        'template_name': template_name,
                        'parameters': params,
                        'ref_type': 'citation_template'
                    },
                    section_id='references',
                    language=language,
                    provenance=provenance
                ))
        
        return references
    
    def _extract_text_content(self, parsed: wtp.WikiList, language: str,
                             provenance: Provenance) -> List[ClassifiedContent]:
        """Extract text content by section."""
        text_items = []
        
        # Process sections
        sections = parsed.get_sections(include_lead=True)
        
        for i, section in enumerate(sections):
            section_title = str(section.title).strip() if section.title else ""
            section_id = self._section_title_to_id(section_title) if section_title else "lead"
            
            # Get section content without templates/infoboxes/images
            content_copy = wtp.parse(str(section))
            
            # Remove non-text elements
            for template in content_copy.templates:
                # Keep only text from templates, remove markup
                if hasattr(template, 'arguments') and template.arguments:
                    text_content = " ".join(str(arg.value) for arg in template.arguments if arg.value)
                    template.string = text_content
                else:
                    template.string = ""
            
            # Remove image links
            for wikilink in content_copy.wikilinks:
                target = str(wikilink.target).lower()
                if target.startswith(('file:', 'image:', 'category:')):
                    wikilink.string = ""
            
            # Remove ref tags (references handled separately)
            for tag in content_copy.get_tags("ref"):
                tag.string = ""
            
            # Get clean text
            clean_text = content_copy.plain_text()
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            if clean_text and len(clean_text) > 50:  # Only include substantial text
                text_items.append(ClassifiedContent(
                    content_type=ContentType.TEXT,
                    raw_content=str(section),
                    structured_data={
                        'section_title': section_title,
                        'clean_text': clean_text,
                        'section_level': getattr(section, 'level', 2)
                    },
                    section_id=section_id,
                    language=language,
                    provenance=provenance
                ))
        
        return text_items
    
    def _section_title_to_id(self, title: str) -> str:
        """Convert section title to a clean ID."""
        clean_title = re.sub(r'[^\w\s]', '', title.lower())
        return re.sub(r'\s+', '_', clean_title.strip())