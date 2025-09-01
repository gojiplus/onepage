"""IR builder that merges aligned content with provenance tracking."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import uuid

from ..core.models import (
    Entity, IntermediateRepresentation, Section, Claim, Fact, Reference, Provenance
)
from .text import WikitextProcessor, Sentence
from .translation import TranslationService
from .alignment import SentenceAligner, AlignmentCluster  
from .references import ReferenceCanonicalizationService
from .content_merger import ContentMergerPipeline


@dataclass
class BuildResult:
    """Result of building an IR from fetched content."""
    ir: IntermediateRepresentation
    stats: Dict[str, Any]
    warnings: List[str]


class IRBuilder:
    """Builds Intermediate Representation from fetched Wikipedia content."""
    
    def __init__(self, use_modular_merger: bool = True):
        self.text_processor = WikitextProcessor()
        self.translator = TranslationService()
        self.aligner = SentenceAligner()
        self.ref_canonicalizer = ReferenceCanonicalizationService()
        self.use_modular_merger = use_modular_merger
        if use_modular_merger:
            self.content_merger = ContentMergerPipeline()
    
    def build_ir(self, input_dir: str, qid: str) -> BuildResult:
        """
        Build IR from fetched Wikipedia content.
        
        Args:
            input_dir: Directory containing fetched content
            qid: Wikidata QID
            
        Returns:
            BuildResult with IR and metadata
        """
        input_path = Path(input_dir)
        warnings = []
        
        # Load entity metadata
        entity = self._load_entity(input_path)
        
        if self.use_modular_merger:
            # Use new modular content merger
            merge_result = self.content_merger.merge_content(input_dir)
            ir_data = self.content_merger.convert_to_ir_format(merge_result, entity)
            
            # Build facts from Wikidata claims
            wikidata_facts = self._build_facts_from_wikidata(input_path, qid)
            
            # Add Wikidata facts to content
            for fact in wikidata_facts:
                ir_data['content'][fact.id] = fact
                
            stats = merge_result.stats
            stats.update({
                "wikidata_facts": len(wikidata_facts),
                "total_content_items": len(ir_data['content']),
                "sections": len(ir_data['sections'])
            })
            
        else:
            # Use original pipeline approach
            articles_data = self._load_articles(input_path)
            all_sentences = self._extract_all_sentences(articles_data)
            
            # Convert sentences to claims
            claims = self._sentences_to_claims(all_sentences)
            
            # Translate non-English claims
            translated_claims = self.translator.translate_claims(claims)
            
            # Align claims across languages
            alignment_clusters = self.aligner.align_claims(translated_claims)
            
            # Build sections from aligned content
            sections = self._build_sections(alignment_clusters)
            
            # Extract and canonicalize references
            all_references = self._extract_all_references(articles_data)
            canonical_refs = self.ref_canonicalizer.canonicalize_references(all_references)
            
            # Build facts from Wikidata claims
            facts = self._build_facts_from_wikidata(input_path, qid)
        
        if self.use_modular_merger:
            # Create IR from modular merge result
            ir = IntermediateRepresentation(
                entity=ir_data['entity'],
                sections=ir_data['sections'],
                content=ir_data['content'],
                references=ir_data['references'],
                metadata={
                    "build_timestamp": str(input_path / "fetch_metadata.json"),
                    "merger_type": "modular",
                    "languages_processed": stats.get('languages_processed', 0),
                    "total_content_items": stats.get('total_content_items', 0),
                }
            )
            
        else:
            # Original pipeline approach
            # Combine content
            content = {}
            
            # Add claims from alignment clusters
            for cluster in alignment_clusters:
                claim = cluster.primary_claim
                if claim:
                    content[claim.id] = claim
            
            # Add facts
            for fact in facts:
                content[fact.id] = fact
            
            # Build reference dictionary
            references = {ref.canonical_id: self._canonical_ref_to_reference(ref) 
                         for ref in canonical_refs}
            
            # Create IR
            ir = IntermediateRepresentation(
                entity=entity,
                sections=sections,
                content=content,
                references=references,
                metadata={
                    "build_timestamp": str(input_path / "fetch_metadata.json"),
                    "merger_type": "original",
                    "languages_processed": list(articles_data.keys()),
                    "total_claims": len(claims),
                    "total_clusters": len(alignment_clusters),
                    "total_references": len(canonical_refs),
                }
            )
            
            # Calculate stats for original approach
            stats = {
                "total_sentences": len(all_sentences),
                "total_claims": len(claims),
                "alignment_clusters": len(alignment_clusters),
                "canonical_references": len(canonical_refs),
                "languages_processed": len(articles_data),
                "sections": len(sections),
            }
        
        return BuildResult(ir=ir, stats=stats, warnings=warnings)
    
    def _load_entity(self, input_path: Path) -> Entity:
        """Load entity metadata from input directory."""
        entity_file = input_path / "entity.json"
        with open(entity_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Entity(
            qid=data["qid"],
            labels=data.get("labels", {}),
            descriptions=data.get("descriptions", {}),
            aliases=data.get("aliases", {}),
        )
    
    def _load_articles(self, input_path: Path) -> Dict[str, Dict[str, Any]]:
        """Load all article data from input directory."""
        articles = {}
        
        for article_file in input_path.glob("*.json"):
            if article_file.name in ["entity.json", "claims.json", "fetch_metadata.json"]:
                continue
            
            lang = article_file.stem
            with open(article_file, 'r', encoding='utf-8') as f:
                articles[lang] = json.load(f)
        
        return articles
    
    def _extract_all_sentences(self, articles_data: Dict[str, Dict[str, Any]]) -> List[Sentence]:
        """Extract sentences from all articles."""
        all_sentences = []
        
        for lang, article_data in articles_data.items():
            wikitext = article_data["wikitext"]
            provenance = Provenance(
                wiki=article_data["provenance"]["wiki"],
                title=article_data["provenance"]["title"],
                rev_id=article_data["provenance"]["rev_id"],
            )
            
            sections = self.text_processor.extract_sections(wikitext, lang, provenance)
            
            for section in sections:
                all_sentences.extend(section.content)
        
        return all_sentences
    
    def _sentences_to_claims(self, sentences: List[Sentence]) -> List[Claim]:
        """Convert sentences to claims."""
        claims = []
        
        for sentence in sentences:
            claim = Claim(
                id=f"c_{uuid.uuid4().hex[:8]}",
                lang=sentence.language,
                text=sentence.text,
                sources=sentence.references,
                provenance=sentence.provenance,
            )
            # Add section_id as an attribute for alignment
            claim.section_id = sentence.section_id
            claims.append(claim)
        
        return claims
    
    def _build_sections(self, clusters: List[AlignmentCluster]) -> List[Section]:
        """Build sections from alignment clusters."""
        # Group clusters by section
        sections_dict = {}
        
        for cluster in clusters:
            # Determine section from primary claim
            section_id = getattr(cluster.primary_claim, 'section_id', 'unknown')
            
            if section_id not in sections_dict:
                sections_dict[section_id] = {
                    "items": [],
                    "title": {},
                }
            
            sections_dict[section_id]["items"].append(cluster.primary_claim.id)
        
        # Convert to Section objects
        sections = []
        for section_id, section_data in sections_dict.items():
            # Generate section title (simplified)
            title = {"en": section_id.replace("_", " ").title()}
            if section_id == "lead":
                title = {}
            
            sections.append(Section(
                id=section_id,
                title=title,
                items=section_data["items"],
            ))
        
        return sections
    
    def _extract_all_references(self, articles_data: Dict[str, Dict[str, Any]]) -> List[Reference]:
        """Extract all references from articles."""
        # This is a simplified implementation
        # In a full version, you'd parse citation templates and ref tags properly
        references = []
        
        for i, (lang, article_data) in enumerate(articles_data.items()):
            # Create placeholder references for demonstration
            ref = Reference(
                id=f"r_{i}_{lang}",
                url=f"https://{lang}.wikipedia.org/wiki/{article_data['title']}",
                title=f"Wikipedia article: {article_data['title']}",
                date=article_data.get("timestamp", "")[:10],  # Extract date part
            )
            references.append(ref)
        
        return references
    
    def _build_facts_from_wikidata(self, input_path: Path, qid: str) -> List[Fact]:
        """Build facts from Wikidata claims."""
        claims_file = input_path / "claims.json"
        if not claims_file.exists():
            return []
        
        with open(claims_file, 'r', encoding='utf-8') as f:
            wikidata_claims = json.load(f)
        
        facts = []
        
        for prop_id, claim_list in wikidata_claims.items():
            for i, claim in enumerate(claim_list):
                fact_id = f"f_{prop_id}_{i}"
                
                # Extract main value
                value = self._extract_claim_value(claim)
                
                # Extract qualifiers
                qualifiers = self._extract_qualifiers(claim)
                
                # Extract sources/references
                sources = self._extract_claim_sources(claim)
                
                if value is not None:
                    facts.append(Fact(
                        id=fact_id,
                        property=prop_id,
                        value=value,
                        qualifiers=qualifiers,
                        sources=sources,
                        from_source="wikidata",
                    ))
        
        return facts
    
    def _extract_claim_value(self, claim: Dict[str, Any]) -> Any:
        """Extract the main value from a Wikidata claim."""
        if "mainsnak" not in claim:
            return None
        
        snak = claim["mainsnak"]
        if "datavalue" not in snak:
            return None
        
        datavalue = snak["datavalue"]
        if datavalue["type"] == "wikibase-entityid":
            return {"qid": datavalue["value"]["id"]}
        elif datavalue["type"] == "string":
            return datavalue["value"]
        elif datavalue["type"] == "time":
            return datavalue["value"]["time"]
        elif datavalue["type"] == "quantity":
            return float(datavalue["value"]["amount"])
        else:
            return str(datavalue["value"])
    
    def _extract_qualifiers(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Extract qualifiers from a Wikidata claim."""
        qualifiers = {}
        
        if "qualifiers" in claim:
            for prop_id, qualifier_list in claim["qualifiers"].items():
                qualifier_values = []
                for qualifier in qualifier_list:
                    if "datavalue" in qualifier:
                        value = self._extract_claim_value({"mainsnak": qualifier})
                        if value is not None:
                            qualifier_values.append(value)
                
                if qualifier_values:
                    if len(qualifier_values) == 1:
                        qualifiers[prop_id] = qualifier_values[0]
                    else:
                        qualifiers[prop_id] = qualifier_values
        
        return qualifiers
    
    def _extract_claim_sources(self, claim: Dict[str, Any]) -> List[str]:
        """Extract source references from a Wikidata claim."""
        # Simplified - would need to properly parse Wikidata references
        if "references" in claim and claim["references"]:
            return [f"wd_ref_{i}" for i in range(len(claim["references"]))]
        return []
    
    def _canonical_ref_to_reference(self, canonical_ref) -> Reference:
        """Convert CanonicalReference to Reference model."""
        return Reference(
            id=canonical_ref.canonical_id,
            doi=canonical_ref.doi,
            url=canonical_ref.canonical_url,
            title=canonical_ref.title,
            date=canonical_ref.date,
            author=", ".join(canonical_ref.authors) if canonical_ref.authors else None,
            publisher=canonical_ref.publisher,
        )