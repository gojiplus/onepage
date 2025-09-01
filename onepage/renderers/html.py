"""HTML renderer for preview generation."""

from typing import Dict, List, Any, Optional
import html
import re
from datetime import datetime

from ..core.models import IntermediateRepresentation, Section, Claim, Fact, Reference


class HTMLRenderer:
    """Renders IR to HTML format for preview."""
    
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
        Render complete IR to HTML.
        
        Args:
            ir: Intermediate Representation to render
            
        Returns:
            Complete HTML string
        """
        title = ir.entity.labels.get(self.language, ir.entity.qid)
        
        html_parts = [
            self._render_html_header(title),
            self._render_article_header(ir),
            self._render_infobox(ir),
            self._render_body_content(ir),
            self._render_references_section(ir),
            self._render_html_footer(),
        ]
        
        # Filter out None values before joining
        return "\n".join(part for part in html_parts if part is not None)
    
    def _render_html_header(self, title: str) -> str:
        """Render HTML document header."""
        return f"""<!DOCTYPE html>
<html lang="{self.language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} - onepage preview</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
        }}
        .article-header {{
            border-bottom: 3px solid #a2a9b1;
            margin-bottom: 20px;
            padding-bottom: 10px;
        }}
        .article-title {{
            font-size: 2.5em;
            font-weight: normal;
            margin: 0;
            color: #000;
        }}
        .infobox {{
            float: right;
            width: 300px;
            margin: 0 0 20px 20px;
            border: 1px solid #a2a9b1;
            background-color: #f8f9fa;
            padding: 10px;
            font-size: 0.9em;
        }}
        .infobox-title {{
            font-weight: bold;
            text-align: center;
            margin-bottom: 10px;
            border-bottom: 1px solid #a2a9b1;
            padding-bottom: 5px;
        }}
        .infobox-row {{
            margin: 5px 0;
        }}
        .infobox-label {{
            font-weight: bold;
            display: inline-block;
            width: 40%;
            vertical-align: top;
        }}
        .infobox-value {{
            display: inline-block;
            width: 55%;
        }}
        .section-heading {{
            border-bottom: 1px solid #a2a9b1;
            margin-top: 30px;
            margin-bottom: 15px;
            font-weight: bold;
        }}
        .references {{
            font-size: 0.9em;
        }}
        .reference {{
            margin: 5px 0;
        }}
        .provenance {{
            font-size: 0.8em;
            color: #666;
            font-style: italic;
            margin-left: 10px;
        }}
        .attribution {{
            background-color: #f0f8ff;
            border-left: 4px solid #0066cc;
            padding: 10px;
            margin: 20px 0;
            font-size: 0.9em;
        }}
        sup {{
            font-size: 0.8em;
        }}
    </style>
</head>
<body>"""
    
    def _render_html_footer(self) -> str:
        """Render HTML document footer."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return f"""
    <div class="attribution">
        <strong>Attribution:</strong> This merged article was generated from multiple Wikipedia language editions using onepage. 
        Original content is available under CC BY-SA 4.0. Generated on {timestamp}.
        <br><br>
        <strong>Sources:</strong> Content merged from Wikipedia articles in multiple languages. 
        See individual citations for specific attribution.
    </div>
</body>
</html>"""
    
    def _render_article_header(self, ir: IntermediateRepresentation) -> str:
        """Render article header with title."""
        title = ir.entity.labels.get(self.language, ir.entity.qid)
        
        return f"""    <div class="article-header">
        <h1 class="article-title">{html.escape(title)}</h1>
    </div>"""
    
    def _render_infobox(self, ir: IntermediateRepresentation) -> Optional[str]:
        """Render infobox from facts."""
        # Find facts for infobox
        infobox_facts = []
        for content_id, content in ir.content.items():
            if isinstance(content, Fact) and content.property in self.infobox_mappings:
                infobox_facts.append(content)
        
        if not infobox_facts:
            return None
        
        title = ir.entity.labels.get(self.language, ir.entity.qid)
        
        lines = [
            '    <div class="infobox">',
            f'        <div class="infobox-title">{html.escape(title)}</div>',
        ]
        
        for fact in infobox_facts:
            label = self.infobox_mappings.get(fact.property, fact.property)
            value = self._format_fact_value_html(fact, ir)
            
            lines.append('        <div class="infobox-row">')
            lines.append(f'            <span class="infobox-label">{html.escape(label.replace("_", " ").title())}:</span>')
            lines.append(f'            <span class="infobox-value">{value}</span>')
            lines.append('        </div>')
        
        lines.append('    </div>')
        
        return "\n".join(lines)
    
    def _format_fact_value_html(self, fact: Fact, ir: IntermediateRepresentation) -> str:
        """Format fact value for HTML display."""
        value = fact.value
        
        if isinstance(value, dict) and "qid" in value:
            qid = value["qid"]
            return f'<a href="https://www.wikidata.org/wiki/{qid}">{html.escape(qid)}</a>'
        
        elif isinstance(value, str):
            # Format dates nicely
            if fact.property in ["P569", "P570"]:
                date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', value)
                if date_match:
                    year, month, day = date_match.groups()
                    return f"{year}-{month}-{day}"
            
            return html.escape(value)
        
        return html.escape(str(value))
    
    def _render_body_content(self, ir: IntermediateRepresentation) -> str:
        """Render main body content."""
        parts = []
        
        for section in ir.sections:
            if section.id != "lead":
                section_html = self._render_section_html(section, ir)
                parts.append(section_html)
        
        return "\n\n".join(parts)
    
    def _render_section_html(self, section: Section, ir: IntermediateRepresentation) -> str:
        """Render a section as HTML."""
        parts = []
        
        # Section heading
        if section.title and self.language in section.title:
            level = section.level or 2
            heading_tag = f"h{min(level, 6)}"
            title = section.title[self.language]
            parts.append(f'    <{heading_tag} class="section-heading">{html.escape(title)}</{heading_tag}>')
        
        # Section content
        content_html = self._render_section_content_html(section, ir)
        if content_html:
            parts.append(content_html)
        
        return "\n".join(parts)
    
    def _render_section_content_html(self, section: Section, ir: IntermediateRepresentation) -> str:
        """Render section content as HTML."""
        paragraphs = []
        current_paragraph = []
        
        for item_id in section.items:
            if item_id not in ir.content:
                continue
            
            content_item = ir.content[item_id]
            
            if isinstance(content_item, Claim):
                sentence_html = self._render_claim_html(content_item, ir)
                current_paragraph.append(sentence_html)
        
        if current_paragraph:
            paragraph_html = " ".join(current_paragraph)
            paragraphs.append(f"    <p>{paragraph_html}</p>")
        
        return "\n".join(paragraphs)
    
    def _render_claim_html(self, claim: Claim, ir: IntermediateRepresentation) -> str:
        """Render a claim as HTML with references."""
        text = html.escape(claim.text)
        
        # Add reference links
        if claim.sources:
            ref_links = []
            for i, source_id in enumerate(claim.sources, 1):
                ref_links.append(f'<sup><a href="#ref-{source_id}">[{i}]</a></sup>')
            
            if ref_links:
                text += "".join(ref_links)
        
        # Add provenance information
        if claim.provenance:
            provenance_html = (
                f'<span class="provenance">'
                f'(from {claim.provenance.wiki}: {html.escape(claim.provenance.title)})'
                f'</span>'
            )
            text += provenance_html
        
        return text
    
    def _render_references_section(self, ir: IntermediateRepresentation) -> str:
        """Render references section as HTML."""
        parts = [
            '    <h2 class="section-heading">References</h2>',
            '    <div class="references">',
        ]
        
        for i, (ref_id, ref) in enumerate(ir.references.items(), 1):
            ref_html = self._render_reference_html(ref, ref_id)
            parts.append(f'        <div class="reference" id="ref-{ref_id}">')
            parts.append(f'            {i}. {ref_html}')
            parts.append('        </div>')
        
        parts.append('    </div>')
        
        return "\n".join(parts)
    
    def _render_reference_html(self, ref: Reference, ref_id: str) -> str:
        """Render a single reference as HTML."""
        parts = []
        
        if ref.author:
            parts.append(f"<strong>{html.escape(ref.author)}</strong>")
        
        if ref.title:
            if ref.url:
                parts.append(f'<a href="{html.escape(ref.url)}">{html.escape(ref.title)}</a>')
            else:
                parts.append(f'"{html.escape(ref.title)}"')
        
        if ref.publisher:
            parts.append(f"<em>{html.escape(ref.publisher)}</em>")
        
        if ref.date:
            parts.append(f"({html.escape(ref.date)})")
        
        if ref.doi:
            parts.append(f'DOI: <a href="https://doi.org/{ref.doi}">{html.escape(ref.doi)}</a>')
        elif ref.url and not ref.title:
            parts.append(f'<a href="{html.escape(ref.url)}">{html.escape(ref.url)}</a>')
        
        return ". ".join(parts) if parts else f"Reference {ref_id}"
    
    def _find_section_by_id(self, sections: List[Section], section_id: str) -> Optional[Section]:
        """Find a section by its ID."""
        for section in sections:
            if section.id == section_id:
                return section
        return None