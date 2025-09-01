"""Merge text content from multiple Wikipedia language editions."""

import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..content_classifier import ClassifiedContent, ContentType
from ...core.models import Provenance


@dataclass
class MergedTextSection:
    """A text section merged from multiple sources."""
    section_id: str
    title: str
    merged_text: str
    source_provenances: List[Provenance]
    confidence_score: float


class TextMerger:
    """Merges text content using semantic similarity."""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
    def merge_text_content(self, classified_items: List[ClassifiedContent]) -> List[MergedTextSection]:
        """
        Merge text content from multiple sources using semantic alignment.
        
        Args:
            classified_items: List of classified content items (text type only)
            
        Returns:
            List of merged text sections
        """
        # Filter only text content
        text_items = [item for item in classified_items if item.content_type == ContentType.TEXT]
        
        if not text_items:
            return []
            
        # Group by section ID
        sections_by_id = self._group_by_section(text_items)
        
        merged_sections = []
        for section_id, items in sections_by_id.items():
            merged_section = self._merge_section_content(section_id, items)
            if merged_section:
                merged_sections.append(merged_section)
                
        return merged_sections
    
    def _group_by_section(self, text_items: List[ClassifiedContent]) -> Dict[str, List[ClassifiedContent]]:
        """Group text items by section ID with fuzzy matching."""
        sections = {}
        
        for item in text_items:
            section_id = item.section_id
            
            # Try to find similar existing section
            best_match = self._find_similar_section(section_id, list(sections.keys()))
            
            if best_match:
                sections[best_match].append(item)
            else:
                sections[section_id] = [item]
                
        return sections
    
    def _find_similar_section(self, section_id: str, existing_sections: List[str]) -> Optional[str]:
        """Find similar section using string similarity."""
        if not existing_sections:
            return None
            
        # Normalize section IDs for comparison
        normalized_id = self._normalize_section_id(section_id)
        
        for existing_id in existing_sections:
            normalized_existing = self._normalize_section_id(existing_id)
            
            # Check for exact match after normalization
            if normalized_id == normalized_existing:
                return existing_id
                
            # Check for partial matches (e.g., "early_life" matches "early_life_and_education")
            if (normalized_id in normalized_existing or 
                normalized_existing in normalized_id):
                return existing_id
                
        return None
    
    def _normalize_section_id(self, section_id: str) -> str:
        """Normalize section ID for comparison."""
        # Remove common variations
        normalized = section_id.lower()
        normalized = re.sub(r'[_\-\s]+', '_', normalized)
        normalized = re.sub(r'_and_', '_', normalized)
        normalized = re.sub(r'_the_', '_', normalized)
        return normalized.strip('_')
    
    def _merge_section_content(self, section_id: str, items: List[ClassifiedContent]) -> Optional[MergedTextSection]:
        """Merge content within a section using semantic similarity."""
        if not items:
            return None
            
        # Get the section title (prefer English)
        section_title = self._get_best_section_title(items)
        
        # Extract sentences from all items
        all_sentences = []
        sentence_metadata = []
        
        for item in items:
            clean_text = item.structured_data.get('clean_text', '')
            if not clean_text:
                continue
                
            sentences = self._split_into_sentences(clean_text)
            for sentence in sentences:
                if len(sentence.strip()) > 20:  # Only substantial sentences
                    all_sentences.append(sentence.strip())
                    sentence_metadata.append({
                        'source_item': item,
                        'language': item.language,
                        'provenance': item.provenance
                    })
        
        if not all_sentences:
            return None
            
        # Deduplicate and merge similar sentences
        merged_sentences, provenances = self._deduplicate_sentences(
            all_sentences, sentence_metadata
        )
        
        # Combine into final text
        merged_text = ' '.join(merged_sentences)
        
        return MergedTextSection(
            section_id=section_id,
            title=section_title,
            merged_text=merged_text,
            source_provenances=provenances,
            confidence_score=self._calculate_confidence(len(merged_sentences), len(all_sentences))
        )
    
    def _get_best_section_title(self, items: List[ClassifiedContent]) -> str:
        """Get the best section title, preferring English."""
        # Prefer English titles
        for item in items:
            if item.language == 'en':
                title = item.structured_data.get('section_title', '')
                if title:
                    return title
                    
        # Fall back to any available title
        for item in items:
            title = item.structured_data.get('section_title', '')
            if title:
                return title
                
        return "Untitled Section"
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting (could be improved)
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _deduplicate_sentences(self, sentences: List[str], metadata: List[Dict]) -> Tuple[List[str], List[Provenance]]:
        """Remove duplicate and highly similar sentences."""
        if not sentences:
            return [], []
            
        # Encode sentences for similarity comparison
        embeddings = self.encoder.encode(sentences)
        
        # Track which sentences to keep
        keep_indices = []
        similarity_matrix = cosine_similarity(embeddings)
        processed = set()
        
        for i, sentence in enumerate(sentences):
            if i in processed:
                continue
                
            keep_indices.append(i)
            processed.add(i)
            
            # Find similar sentences
            for j in range(i + 1, len(sentences)):
                if j in processed:
                    continue
                    
                similarity = similarity_matrix[i][j]
                if similarity > self.similarity_threshold:
                    # Prefer English content
                    if (metadata[j]['language'] == 'en' and 
                        metadata[i]['language'] != 'en'):
                        # Replace with English version
                        keep_indices[-1] = j
                    processed.add(j)
        
        # Build final sentences and provenance
        final_sentences = []
        final_provenances = []
        
        for idx in keep_indices:
            final_sentences.append(sentences[idx])
            final_provenances.append(metadata[idx]['provenance'])
            
        return final_sentences, final_provenances
    
    def _calculate_confidence(self, merged_count: int, original_count: int) -> float:
        """Calculate confidence score for the merge."""
        if original_count == 0:
            return 0.0
        return min(1.0, merged_count / original_count)