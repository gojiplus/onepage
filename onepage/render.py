"""Wikitext renderer from IR to MediaWiki format."""

from typing import List, Dict, Any, Optional
import re
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
    """Renders IntermediateRepresentation to simple HTML."""

    def __init__(self, language: str = "en") -> None:
        self.language = language
        # Containers for references when rendering
        self._ref_counter = 0
        self._ref_map: Dict[str, int] = {}
        self._references: List[str] = []

    def render(self, ir: IntermediateRepresentation) -> str:
        """Render the IR to high-quality HTML with full Wikipedia styling."""
        title = ir.entity.labels.get(self.language, ir.entity.qid)
        # Reset reference containers for each render call
        self._ref_counter = 0
        self._ref_map = {}
        self._references = []
        
        parts = [
            "<!DOCTYPE html>",
            "<html lang=\"en\" class=\"client-nojs vector-feature-language-in-header-enabled vector-feature-language-in-main-page-header-disabled vector-feature-sticky-header-disabled vector-feature-page-tools-pinned-disabled vector-feature-toc-pinned-clientpref-1 vector-feature-main-menu-pinned-disabled vector-feature-limited-width-clientpref-1 vector-feature-limited-width-content-enabled vector-feature-custom-font-size-clientpref-1 vector-feature-appearance-pinned-clientpref-1 vector-feature-night-mode-enabled skin-theme-clientpref-day vector-toc-available\">",
            "<head>",
            "<meta charset=\"utf-8\"/>",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"/>",
            f"<title>{title} - Wikipedia</title>",
            "<link rel=\"stylesheet\" href=\"https://en.wikipedia.org/w/load.php?modules=skins.vector.styles.legacy|skins.vector.icons|ext.cite.styles|ext.uls.interlanguage|ext.wikimediaBadges&only=styles&skin=vector\"/>",
            "<link rel=\"stylesheet\" href=\"https://en.wikipedia.org/w/load.php?modules=site.styles&only=styles&skin=vector\"/>",
            "<style>",
            ".infobox { float: right; clear: right; width: 300px; margin: 0 0 1em 1em; padding: 0; border: 1px solid #a2a9b1; background: #f8f9fa; color: black; font-size: 88%; line-height: 1.5em; }",
            ".infobox th, .infobox td { padding: 0.35em 0.5em; }",
            ".infobox th { background: #eaecf0; text-align: left; font-weight: bold; }",
            ".infobox td { text-align: left; }",
            ".references { font-size: 90%; }",
            ".reference { margin: 0.5em 0; }",
            "sup.reference { font-size: 75%; line-height: 1; }",
            "a.external { background: url(//upload.wikimedia.org/wikipedia/commons/6/64/Icon_External_Link.png) no-repeat right; padding-right: 13px; }",
            "</style>",
            "</head>",
            "<body class=\"mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject mw-editable page-" + title.replace(' ', '_') + " rootpage-" + title.replace(' ', '_') + " skin-vector action-view\">",
            "<div class=\"mw-page-container\">",
            "<div class=\"mw-page-container-inner\">",
            "<div class=\"vector-sitenotice-container\">",
            "</div>",
            "<header class=\"mw-header vector-header vector-header-vector-2022 vector-header-logged-out\">",
            "</header>",
            "<div class=\"mw-page-container\">",
            "<div class=\"vector-main\">",
            "<div id=\"content\" class=\"mw-body\" role=\"main\">",
            "<header class=\"mw-body-header vector-page-titlebar\">",
            f"<h1 id=\"firstHeading\" class=\"firstHeading mw-first-heading\">{title}</h1>",
            "</header>",
            "<div class=\"vector-body\" id=\"bodyContent\">",
            "<div id=\"mw-content-text\" class=\"mw-body-content mw-content-ltr\" lang=\"en\" dir=\"ltr\">",
            "<div class=\"mw-parser-output\">",
        ]

        infobox_html = self._render_infobox(ir)
        if infobox_html:
            parts.append(infobox_html)
        
        # Add images after infobox
        images_html = self._render_images(ir)
        if images_html:
            parts.append(images_html)

        lead = self._find_section_by_id(ir.sections, "lead")
        if lead:
            lead_content = self._render_section_content(lead, ir)
            if lead_content:
                parts.append(lead_content)

        for section in ir.sections:
            if section.id != "lead":
                section_html = self._render_section(section, ir)
                if section_html:
                    parts.append(section_html)

        # Render ALL references from IR, not just the ones linked to content
        if ir.references:
            parts.append("<h2>References</h2>")
            parts.append("<ol class=\"references\">")
            for i, (ref_id, ref) in enumerate(ir.references.items(), 1):
                formatted_ref = self._format_reference(ref)
                parts.append(f"<li id=\"cite_note-{i}\">{formatted_ref}</li>")
            parts.append("</ol>")

        parts.extend([
            "</div>",  # mw-parser-output
            "</div>",  # mw-content-text
            "</div>",  # vector-body
            "</div>",  # content
            "</div>",  # vector-main
            "</div>",  # mw-page-container inner
            "</div>",  # mw-page-container outer
            "</div>",  # mw-page-container
            "</body>",
            "</html>"
        ])
        return "\n".join(parts)

    def _render_section(self, section: Section, ir: IntermediateRepresentation) -> str:
        parts = []
        title = section.title.get(self.language)
        if title:
            level = max(2, section.level)
            heading_tag = f"h{level}"
            parts.append(f"<{heading_tag}>{title}</{heading_tag}>")

        content = self._render_section_content(section, ir)
        if content:
            parts.append(content)

        return "\n".join(parts)

    def _render_section_content(self, section: Section, ir: IntermediateRepresentation) -> str:
        sentences = []
        for item_id in section.items:
            item = ir.content.get(item_id)
            if isinstance(item, Claim):
                sentences.append(self._render_claim(item, ir))

        if sentences:
            return "<p>" + " ".join(sentences) + "</p>"
        return ""

    def _find_section_by_id(self, sections: List[Section], section_id: str) -> Optional[Section]:
        for section in sections:
            if section.id == section_id:
                return section
        return None

    def _render_infobox(self, ir: IntermediateRepresentation) -> str:
        box = ir.metadata.get("infobox")
        if not box:
            return ""
        rows = []
        for key, values in box.items():
            rows.append(f"<tr><th>{key}</th><td>{', '.join(values)}</td></tr>")
        return "<table class=\"infobox\">" + "".join(rows) + "</table>"

    # ------------------------------------------------------------------
    # Reference handling helpers
    # ------------------------------------------------------------------

    def _render_claim(self, claim: Claim, ir: IntermediateRepresentation) -> str:
        """Render claim text with inline reference markers."""
        text = claim.text
        if claim.sources:
            markers = []
            for source_id in claim.sources:
                ref = ir.references.get(source_id)
                if ref is None:
                    continue
                idx = self._register_reference(ref)
                markers.append(
                    f"<sup id=\"cite_ref-{idx}\"><a href=\"#cite_note-{idx}\">[{idx}]</a></sup>"
                )
            if markers:
                text += "".join(markers)
        return text

    def _register_reference(self, ref: Reference) -> int:
        """Assign an index to a reference and store its formatted HTML."""
        key = f"{ref.title}|{ref.url}|{ref.doi}"
        if key in self._ref_map:
            return self._ref_map[key]

        self._ref_counter += 1
        idx = self._ref_counter
        self._ref_map[key] = idx
        formatted = self._format_reference(ref)
        self._references.append(f"<li id=\"cite_note-{idx}\">{formatted}</li>")
        return idx

    def _format_reference(self, ref: Reference) -> str:
        """Format a reference for display in HTML."""
        parts = []
        title = ref.title or ref.url or "Reference"
        if ref.url:
            parts.append(f"<cite class=\"citation\"><a href=\"{ref.url}\" class=\"external\">{title}</a>")
        else:
            parts.append(f"<cite class=\"citation\">{title}")

        details = []
        if ref.author:
            details.append(ref.author)
        if ref.publisher:
            details.append(ref.publisher)
        if ref.date:
            details.append(ref.date)
        if ref.doi:
            details.append(f"doi:{ref.doi}")
        if details:
            parts.append(". ".join(["", ", ".join(details)]))

        parts.append("</cite>")
        return "".join(parts)
    
    def _render_images(self, ir: IntermediateRepresentation) -> str:
        """Render images from metadata."""
        images = ir.metadata.get("images", [])
        if not images:
            return ""
        
        parts = ["<div class=\"gallery mw-gallery-traditional\">"]
        
        for i, image in enumerate(images[:6]):  # Limit to first 6 images
            # Clean image filename
            image_name = image.replace("File:", "").replace("Image:", "")
            image_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{image_name}?width=300"
            
            parts.append(f"""
            <div class="gallerybox" style="width: 155px;">
                <div class="thumb" style="width: 150px; height: 150px;">
                    <div style="margin:0px auto;">
                        <a href="https://commons.wikimedia.org/wiki/File:{image_name}" class="image">
                            <img alt="{image_name}" src="{image_url}" style="max-width: 150px; max-height: 150px;"/>
                        </a>
                    </div>
                </div>
                <div class="gallerytext">
                    <p>{image_name[:50]}...</p>
                </div>
            </div>
            """)
        
        parts.append("</div>")
        return "\n".join(parts)
