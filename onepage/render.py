"""Rendering utilities for converting the IR into textual formats."""

from typing import List, Dict, Any, Optional
import re
import subprocess
import shutil
from datetime import datetime

from .models import IntermediateRepresentation, Section, Claim, Fact, Reference


class WikitextRenderer:
    """Renders IR to MediaWiki wikitext format."""
    
    def __init__(self, language: str = "en"):
        self.language = language
        
        # Wikidata property mappings for infobox
        self.infobox_mappings = {
            "P18": "image",         # image
            "P569": "birth_date",   # date of birth
            "P19": "birth_place",   # place of birth
            "P570": "death_date",   # date of death
            "P20": "death_place",   # place of death  
            "P39": "office",        # position held
            "P102": "party",        # political party
            "P27": "nationality",   # country of citizenship
            "P106": "occupation",   # occupation
        }
    
    def render(self, ir: IntermediateRepresentation) -> str:
        """
        Render complete IR to wikitext.
        
        Args:
            ir: Intermediate Representation to render
            
        Returns:
            Complete wikitext string
        """
        parts = []
        
        # 1. Short description
        parts.append(self._render_short_description(ir))
        
        # 2. Infobox
        infobox = self._render_infobox(ir)
        if infobox:
            parts.append(infobox)
        
        # 3. Lead section
        lead_section = self._find_section_by_id(ir.sections, "lead")
        if lead_section:
            lead_content = self._render_section_content(lead_section, ir)
            parts.append(lead_content)
        
        # 4. Body sections
        for section in ir.sections:
            if section.id != "lead":
                section_wikitext = self._render_section(section, ir)
                parts.append(section_wikitext)
        
        # 5. References section
        parts.append(self._render_references_section())
        
        # 6. Categories (simplified)
        categories = self._render_categories(ir)
        if categories:
            parts.append(categories)
        
        return "\n\n".join(parts)
    
    def _render_short_description(self, ir: IntermediateRepresentation) -> str:
        """Render short description for the article."""
        # Use entity description if available
        if self.language in ir.entity.descriptions:
            desc = ir.entity.descriptions[self.language]
            return f"{{{{Short description|{desc}}}}}"
        
        # Fallback to a generic description
        return f"{{{{Short description|{ir.entity.labels.get(self.language, 'Article')}}}}}"
    
    def _render_infobox(self, ir: IntermediateRepresentation) -> Optional[str]:
        """Render infobox from facts."""
        # Find facts that should go in infobox
        infobox_facts = []
        for content_id, content in ir.content.items():
            if isinstance(content, Fact) and content.property in self.infobox_mappings:
                infobox_facts.append(content)
        
        if not infobox_facts:
            return None
        
        # Determine infobox type (simplified)
        infobox_type = "person"  # Default, could be smarter
        
        lines = [f"{{{{Infobox {infobox_type}"]
        
        # Add name
        if self.language in ir.entity.labels:
            lines.append(f"| name = {ir.entity.labels[self.language]}")
        
        # Add facts
        for fact in infobox_facts:
            param_name = self.infobox_mappings.get(fact.property, fact.property)
            value_str = self._format_fact_value(fact, ir)
            
            if value_str:
                lines.append(f"| {param_name} = {value_str}")
        
        lines.append("}}")
        
        return "\n".join(lines)
    
    def _format_fact_value(self, fact: Fact, ir: IntermediateRepresentation) -> str:
        """Format a fact value for display in infobox."""
        value = fact.value
        
        if isinstance(value, dict) and "qid" in value:
            # Wikidata entity reference
            qid = value["qid"]
            # Try to get label, fallback to QID
            # In a full implementation, you'd resolve this
            return f"[[{qid}]]"
        
        elif isinstance(value, str):
            # Handle dates
            if fact.property in ["P569", "P570"]:  # Birth/death dates
                # Parse ISO date format
                date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', value)
                if date_match:
                    year, month, day = date_match.groups()
                    return f"{{{{birth date|{year}|{month}|{day}}}}}"
            
            return value
        
        return str(value)
    
    def _render_section(self, section: Section, ir: IntermediateRepresentation) -> str:
        """Render a complete section."""
        parts = []
        
        # Section heading
        if section.title and self.language in section.title:
            heading_level = "=" * (section.level or 2)
            title = section.title[self.language]
            parts.append(f"{heading_level} {title} {heading_level}")
        
        # Section content
        content = self._render_section_content(section, ir)
        if content:
            parts.append(content)
        
        return "\n\n".join(parts)
    
    def _render_section_content(self, section: Section, ir: IntermediateRepresentation) -> str:
        """Render content of a section."""
        paragraphs = []
        current_paragraph = []
        
        for item_id in section.items:
            if item_id not in ir.content:
                continue
            
            content_item = ir.content[item_id]
            
            if isinstance(content_item, Claim):
                # Render claim as sentence with references
                sentence = self._render_claim(content_item, ir)
                current_paragraph.append(sentence)
            
            elif isinstance(content_item, Fact):
                # Facts typically go in infobox, but could be rendered as text
                fact_text = self._render_fact_as_text(content_item, ir)
                if fact_text:
                    current_paragraph.append(fact_text)
        
        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))
        
        return "\n\n".join(paragraphs)
    
    def _render_claim(self, claim: Claim, ir: IntermediateRepresentation) -> str:
        """Render a claim as wikitext with references."""
        text = claim.text
        
        # Add inline references
        if claim.sources:
            ref_tags = []
            for source_id in claim.sources:
                if source_id in ir.references:
                    ref = ir.references[source_id]
                    ref_content = self._format_reference(ref)
                    ref_tags.append(f"<ref>{ref_content}</ref>")
            
            if ref_tags:
                text += "".join(ref_tags)
        
        return text
    
    def _render_fact_as_text(self, fact: Fact, ir: IntermediateRepresentation) -> Optional[str]:
        """Render a fact as readable text (for facts not in infobox)."""
        # This could be expanded to convert facts to natural language
        return None

    def _format_reference(self, ref: Reference) -> str:
        """Format a reference for citation."""
        if ref.doi:
            # Use Cite journal template for DOI
            parts = [f"{{{{Cite journal"]
            if ref.title:
                parts.append(f"| title = {ref.title}")
            if ref.author:
                parts.append(f"| author = {ref.author}")
            if ref.date:
                parts.append(f"| date = {ref.date}")
            parts.append(f"| doi = {ref.doi}")
            parts.append("}}")
            return "".join(parts)
        
        elif ref.url:
            # Use Cite web template
            parts = [f"{{{{Cite web"]
            if ref.title:
                parts.append(f"| title = {ref.title}")
            if ref.author:
                parts.append(f"| author = {ref.author}")
            if ref.date:
                parts.append(f"| date = {ref.date}")
            if ref.publisher:
                parts.append(f"| publisher = {ref.publisher}")
            parts.append(f"| url = {ref.url}")
            parts.append("}}")
            return "".join(parts)
        
        else:
            # Generic citation
            return ref.title or "Reference"
    
    def _render_references_section(self) -> str:
        """Render the references section."""
        return "== References ==\n{{Reflist}}"
    
    def _render_categories(self, ir: IntermediateRepresentation) -> Optional[str]:
        """Render categories (simplified)."""
        # This would need to be more sophisticated in a real implementation
        # For now, just add a basic category based on entity type
        categories = []
        
        # Try to infer category from Wikidata facts
        for content_id, content in ir.content.items():
            if isinstance(content, Fact):
                if content.property == "P31":  # instance of
                    # Could map instance types to categories
                    pass
        
        # Add a generic category
        entity_name = ir.entity.labels.get(self.language, ir.entity.qid)
        categories.append(f"[[Category:{entity_name}]]")
        
        return "\n".join(categories) if categories else None
    
    def _find_section_by_id(self, sections: List[Section], section_id: str) -> Optional[Section]:
        """Find a section by its ID."""
        for section in sections:
            if section.id == section_id:
                return section
        return None


class HTMLRenderer:
    """Render the :class:`IntermediateRepresentation` to HTML.

    This renderer converts the IR to wikitext using :class:`WikitextRenderer`
    and then invokes ``pandoc`` to translate the wikitext into HTML. ``pandoc``
    must be available on the ``PATH``; if it is not installed a helpful
    ``RuntimeError`` is raised.
    """

    def __init__(self, language: str = "en") -> None:
        self.language = language
        self._wikitext = WikitextRenderer(language=language)

    def render(self, ir: IntermediateRepresentation) -> str:
        """Render the IR to an HTML string."""
        if not shutil.which("pandoc"):
            raise RuntimeError("pandoc is required for HTML rendering but was not found")

        wikitext = self._wikitext.render(ir)
        proc = subprocess.run(
            ["pandoc", "-s", "-f", "mediawiki", "-t", "html"],
            input=wikitext.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return proc.stdout.decode("utf-8")
