"""Text processing and segmentation for Wikipedia articles."""

import re
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import wikitextparser as wtp
from bs4 import BeautifulSoup

from ..core.models import Provenance


@dataclass
class Sentence:
    """A sentence extracted from Wikipedia content."""
    text: str
    language: str
    section_id: str
    references: List[str]  # Reference IDs found in this sentence
    provenance: Provenance
    raw_wikitext: str  # Original wikitext before processing


@dataclass
class ExtractedSection:
    """A section extracted from a Wikipedia article."""
    id: str
    title: str
    level: int
    content: List[Sentence]
    raw_wikitext: str


class WikitextProcessor:
    """Process Wikipedia wikitext into structured content."""
    
    def __init__(self):
        # Common sentence boundaries for multiple languages
        self.sentence_endings = re.compile(r'[.!?।。]+')
        
    def extract_sections(self, wikitext: str, language: str, 
                        provenance: Provenance) -> List[ExtractedSection]:
        """
        Extract sections from wikitext.
        
        Args:
            wikitext: Raw wikitext content
            language: Language code
            provenance: Source provenance information
            
        Returns:
            List of extracted sections
        """
        parsed = wtp.parse(wikitext)
        sections = []
        
        # Extract lead section (before first heading)
        lead_content = self._extract_lead_section(parsed, language, provenance)
        if lead_content:
            sections.append(ExtractedSection(
                id="lead",
                title="",
                level=0,
                content=lead_content,
                raw_wikitext="",
            ))
        
        # Extract other sections
        current_section = None
        current_content = []
        current_wikitext = ""
        
        for section in parsed.sections:
            if section.title:
                # Save previous section if exists
                if current_section:
                    sections.append(ExtractedSection(
                        id=self._section_title_to_id(current_section),
                        title=current_section,
                        level=section.level,
                        content=current_content,
                        raw_wikitext=current_wikitext,
                    ))
                
                # Start new section
                current_section = str(section.title).strip()
                current_content = []
                current_wikitext = str(section)
            
            # Process section content
            if section.contents:
                sentences = self._extract_sentences_from_section(
                    section, language, provenance, current_section or "lead"
                )
                current_content.extend(sentences)
        
        # Add final section
        if current_section and current_content:
            sections.append(ExtractedSection(
                id=self._section_title_to_id(current_section),
                title=current_section,
                level=2,  # Default level
                content=current_content,
                raw_wikitext=current_wikitext,
            ))
        
        return sections
    
    def _extract_lead_section(self, parsed: wtp.WikiList, language: str, 
                             provenance: Provenance) -> List[Sentence]:
        """Extract sentences from the lead section."""
        # Get content before first section
        lead_content = ""
        for section in parsed.sections:
            if section.title is None:  # Lead section has no title
                lead_content = str(section)
                break
        
        if not lead_content:
            return []
        
        return self._extract_sentences_from_text(
            lead_content, language, provenance, "lead"
        )
    
    def _extract_sentences_from_section(self, section: Any, language: str,
                                       provenance: Provenance, section_id: str) -> List[Sentence]:
        """Extract sentences from a section."""
        section_text = str(section.contents) if hasattr(section, 'contents') else str(section)
        return self._extract_sentences_from_text(section_text, language, provenance, section_id)
    
    def _extract_sentences_from_text(self, wikitext: str, language: str,
                                    provenance: Provenance, section_id: str) -> List[Sentence]:
        """Extract individual sentences from wikitext."""
        # Parse wikitext
        parsed = wtp.parse(wikitext)
        
        # Remove templates, but keep some content
        self._clean_templates(parsed)
        
        # Extract references
        refs = self._extract_references(parsed)
        
        # Convert to plain text
        plain_text = parsed.plain()
        
        # Clean up the text
        plain_text = self._clean_text(plain_text)
        
        # Split into sentences
        sentences = self._split_sentences(plain_text, language)
        
        # Create Sentence objects
        result = []
        for i, sentence_text in enumerate(sentences):
            if sentence_text.strip():
                # Find references that might belong to this sentence
                sentence_refs = self._match_references_to_sentence(sentence_text, refs)
                
                result.append(Sentence(
                    text=sentence_text.strip(),
                    language=language,
                    section_id=section_id,
                    references=sentence_refs,
                    provenance=provenance,
                    raw_wikitext=wikitext,  # Store original for debugging
                ))
        
        return result
    
    def _clean_templates(self, parsed: wtp.WikiList) -> None:
        """Remove or clean templates from parsed wikitext."""
        for template in parsed.templates:
            template_name = str(template.name).strip().lower()
            
            # Remove citation needed, cleanup, and similar maintenance templates
            if any(x in template_name for x in ["citation needed", "cleanup", "unreferenced", "stub"]):
                template.string = ""
            # Keep cite templates but mark them for reference extraction
            elif template_name.startswith("cite"):
                continue
            # Remove most other templates but keep some content
            else:
                # For now, just remove the template but keep any plain text content
                if hasattr(template, 'arguments') and template.arguments:
                    # Try to extract meaningful content from template arguments
                    content = " ".join(str(arg.value) for arg in template.arguments if arg.value)
                    template.string = content
                else:
                    template.string = ""
    
    def _extract_references(self, parsed: wtp.WikiList) -> List[Dict[str, str]]:
        """Extract reference information from wikitext."""
        references = []
        
        # Extract from <ref> tags
        for tag in parsed.get_tags(attrs={"name": "ref"}):
            ref_content = str(tag.contents) if tag.contents else ""
            references.append({
                "type": "ref_tag",
                "content": ref_content,
                "raw": str(tag),
            })
        
        # Extract from citation templates
        for template in parsed.templates:
            template_name = str(template.name).strip().lower()
            if template_name.startswith("cite"):
                references.append({
                    "type": "citation_template",
                    "template": template_name,
                    "content": str(template),
                    "raw": str(template),
                })
        
        return references
    
    def _clean_text(self, text: str) -> str:
        """Clean up extracted plain text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove file/image references
        text = re.sub(r'\[\[File:.*?\]\]', '', text)
        text = re.sub(r'\[\[Image:.*?\]\]', '', text)
        
        # Clean up remaining wikilinks
        text = re.sub(r'\[\[([^|]*?)\]\]', r'\1', text)  # [[Link]] -> Link
        text = re.sub(r'\[\[.*?\|([^]]*?)\]\]', r'\1', text)  # [[Link|Text]] -> Text
        
        # Remove remaining markup
        text = re.sub(r"'{2,}", '', text)  # Remove bold/italic markup
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
        
        return text.strip()
    
    def _split_sentences(self, text: str, language: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - could be improved with language-specific rules
        sentences = []
        
        # Split on sentence endings
        parts = self.sentence_endings.split(text)
        
        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                # Add back the sentence ending if not the last part
                if i < len(parts) - 1:
                    # Find which ending was used
                    remaining_text = text[text.find(part) + len(part):]
                    ending_match = self.sentence_endings.match(remaining_text)
                    if ending_match:
                        part += ending_match.group()
                
                sentences.append(part)
        
        return sentences
    
    def _match_references_to_sentence(self, sentence: str, references: List[Dict[str, str]]) -> List[str]:
        """Match references to a sentence (simplified heuristic)."""
        # This is a simplified implementation
        # In a full implementation, you'd want more sophisticated reference matching
        return [f"r{i}" for i, ref in enumerate(references)]
    
    def _section_title_to_id(self, title: str) -> str:
        """Convert section title to a clean ID."""
        # Remove markup and convert to lowercase with underscores
        clean_title = re.sub(r'[^\w\s]', '', title.lower())
        return re.sub(r'\s+', '_', clean_title.strip())