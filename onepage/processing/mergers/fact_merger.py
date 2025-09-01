"""Merge infobox facts from multiple Wikipedia language editions."""

from typing import List, Dict, Any, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import re

from ..content_classifier import ClassifiedContent, ContentType
from ...core.models import Provenance


@dataclass
class MergedInfobox:
    """An infobox merged from multiple sources."""
    template_name: str
    parameters: Dict[str, str]
    source_provenances: List[Provenance]
    parameter_sources: Dict[str, Provenance]  # Track which source provided each parameter


class FactMerger:
    """Merges infobox facts from multiple language sources."""
    
    def __init__(self):
        # Parameter mappings between languages (add more as needed)
        self.parameter_mappings = {
            # Common birth-related parameters
            'birth_date': {'जन्म_तारीख', 'जन्म', 'birth_date', 'born', 'birth'},
            'birth_place': {'जन्म_स्थान', 'birth_place', 'birthplace'},
            'death_date': {'मृत्यु_तारीख', 'मृत्यु', 'death_date', 'died', 'death'},
            'death_place': {'मृत्यु_स्थान', 'death_place', 'deathplace'},
            'occupation': {'व्यवसाय', 'profession', 'occupation'},
            'spouse': {'पत्नी', 'spouse', 'partner'},
            'children': {'बच्चे', 'children', 'child'},
            'party': {'राजनीतिक_दल', 'party', 'political_party'},
            'office': {'पद', 'office', 'title'},
            'predecessor': {'पूर्ववर्ती', 'predecessor'},
            'successor': {'उत्तराधिकारी', 'successor'},
            'term_start': {'कार्यकाल_शुरुआत', 'term_start', 'took_office'},
            'term_end': {'कार्यकाल_समाप्ति', 'term_end', 'left_office'},
            'alma_mater': {'शिक्षा', 'alma_mater', 'education'},
            'residence': {'निवास', 'residence', 'home_town'}
        }
        
        # Reverse mapping for lookup
        self.reverse_mappings = {}
        for canonical, variants in self.parameter_mappings.items():
            for variant in variants:
                self.reverse_mappings[variant.lower()] = canonical
    
    def merge_infoboxes(self, classified_items: List[ClassifiedContent]) -> Optional[MergedInfobox]:
        """
        Merge infobox content from multiple sources.
        
        Args:
            classified_items: List of classified content items (infobox type only)
            
        Returns:
            Merged infobox or None if no infoboxes found
        """
        # Filter only infobox content
        infobox_items = [item for item in classified_items if item.content_type == ContentType.INFOBOX]
        
        if not infobox_items:
            return None
            
        # Get the primary template name (prefer English)
        template_name = self._get_primary_template_name(infobox_items)
        
        # Merge parameters from all sources
        merged_params, param_sources = self._merge_parameters(infobox_items)
        
        # Collect all provenances
        provenances = [item.provenance for item in infobox_items]
        
        return MergedInfobox(
            template_name=template_name,
            parameters=merged_params,
            source_provenances=provenances,
            parameter_sources=param_sources
        )
    
    def _get_primary_template_name(self, infobox_items: List[ClassifiedContent]) -> str:
        """Get the primary template name, preferring English."""
        # Prefer English template name
        for item in infobox_items:
            if item.language == 'en':
                template_name = item.structured_data.get('template_name', '')
                if template_name:
                    return template_name
                    
        # Fall back to any available template name
        for item in infobox_items:
            template_name = item.structured_data.get('template_name', '')
            if template_name:
                return template_name
                
        return 'infobox person'
    
    def _merge_parameters(self, infobox_items: List[ClassifiedContent]) -> Tuple[Dict[str, str], Dict[str, Provenance]]:
        """Merge parameters from multiple infoboxes."""
        # Collect all parameters with their sources
        param_candidates = defaultdict(list)  # canonical_param -> [(value, source, language)]
        
        for item in infobox_items:
            parameters = item.structured_data.get('parameters', {})
            for param_name, param_value in parameters.items():
                if not param_value or not param_value.strip():
                    continue
                    
                # Normalize parameter name
                canonical_param = self._normalize_parameter_name(param_name)
                
                param_candidates[canonical_param].append({
                    'value': param_value.strip(),
                    'source': item.provenance,
                    'language': item.language,
                    'original_param': param_name
                })
        
        # Resolve conflicts and select best values
        merged_params = {}
        param_sources = {}
        
        for canonical_param, candidates in param_candidates.items():
            best_value, best_source = self._select_best_parameter_value(canonical_param, candidates)
            if best_value:
                merged_params[canonical_param] = best_value
                param_sources[canonical_param] = best_source
                
        return merged_params, param_sources
    
    def _normalize_parameter_name(self, param_name: str) -> str:
        """Normalize parameter name to canonical form."""
        normalized = param_name.lower().strip()
        
        # Check reverse mappings
        if normalized in self.reverse_mappings:
            return self.reverse_mappings[normalized]
            
        # Clean up common variations
        normalized = re.sub(r'[_\-\s]+', '_', normalized)
        normalized = re.sub(r'^(infobox_)?', '', normalized)  # Remove infobox prefix
        
        return normalized
    
    def _select_best_parameter_value(self, param_name: str, candidates: List[Dict]) -> Tuple[Optional[str], Optional[Provenance]]:
        """Select the best parameter value from multiple candidates."""
        if not candidates:
            return None, None
            
        if len(candidates) == 1:
            return candidates[0]['value'], candidates[0]['source']
        
        # Scoring criteria (higher is better):
        # 1. English content gets +10 points
        # 2. Longer, more detailed content gets +1 point per 10 characters
        # 3. Content with dates/numbers gets +5 points
        # 4. Content without wikitext markup gets +3 points
        
        scored_candidates = []
        
        for candidate in candidates:
            value = candidate['value']
            score = 0
            
            # Prefer English
            if candidate['language'] == 'en':
                score += 10
                
            # Prefer longer, more detailed content
            score += len(value) // 10
            
            # Prefer content with dates/numbers (more factual)
            if re.search(r'\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', value):
                score += 5
                
            # Prefer content without markup
            if not re.search(r'\[\[|\{\{|\]\]|\}\}', value):
                score += 3
                
            scored_candidates.append((score, candidate))
        
        # Sort by score (highest first)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        best_candidate = scored_candidates[0][1]
        return best_candidate['value'], best_candidate['source']
    
    def _calculate_parameter_coverage(self, merged_params: Dict[str, str], all_candidates: Dict[str, List]) -> float:
        """Calculate how well the merge covers available information."""
        total_available = len(all_candidates)
        if total_available == 0:
            return 0.0
        return len(merged_params) / total_available