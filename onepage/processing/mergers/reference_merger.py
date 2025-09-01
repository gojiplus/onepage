"""Merge and deduplicate references from multiple Wikipedia language editions."""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import re
from urllib.parse import urlparse

from ..content_classifier import ClassifiedContent, ContentType
from ...core.models import Provenance


@dataclass
class MergedReference:
    """A reference merged from multiple sources."""
    ref_id: str
    content: str
    ref_type: str  # 'ref_tag', 'citation_template'
    url: Optional[str]
    title: Optional[str]
    authors: List[str]
    publication: Optional[str]
    date: Optional[str]
    source_provenances: List[Provenance]
    languages_found: Set[str]


class ReferenceMerger:
    """Merges and deduplicates references from multiple language sources."""
    
    def __init__(self):
        # Common citation template parameters
        self.url_params = {'url', 'website', 'work', 'publisher', 'archiveurl'}
        self.title_params = {'title', 'article'}
        self.author_params = {'author', 'last', 'first', 'author1', 'last1', 'first1'}
        self.date_params = {'date', 'year', 'accessdate', 'access-date'}
        self.publication_params = {'journal', 'newspaper', 'magazine', 'work', 'publisher'}
        
    def merge_references(self, classified_items: List[ClassifiedContent]) -> List[MergedReference]:
        """
        Merge and deduplicate references from multiple sources.
        
        Args:
            classified_items: List of classified content items (reference type only)
            
        Returns:
            List of merged and deduplicated references
        """
        # Filter only reference content
        ref_items = [item for item in classified_items if item.content_type == ContentType.REFERENCE]
        
        if not ref_items:
            return []
            
        # Parse and normalize references
        parsed_refs = []
        for item in ref_items:
            parsed_ref = self._parse_reference(item)
            if parsed_ref:
                parsed_refs.append(parsed_ref)
        
        # Group similar references
        ref_groups = self._group_similar_references(parsed_refs)
        
        # Merge each group
        merged_refs = []
        for group in ref_groups:
            merged_ref = self._merge_reference_group(group)
            if merged_ref:
                merged_refs.append(merged_ref)
                
        return merged_refs
    
    def _parse_reference(self, ref_item: ClassifiedContent) -> Optional[Dict]:
        """Parse a reference item into structured data."""
        ref_data = ref_item.structured_data
        ref_type = ref_data.get('ref_type', 'unknown')
        
        parsed = {
            'original_item': ref_item,
            'ref_type': ref_type,
            'raw_content': ref_item.raw_content,
            'language': ref_item.language,
            'provenance': ref_item.provenance,
            'url': None,
            'title': None,
            'authors': [],
            'publication': None,
            'date': None
        }
        
        if ref_type == 'citation_template':
            # Parse citation template parameters
            template_params = ref_data.get('parameters', {})
            parsed.update(self._extract_citation_fields(template_params))
        elif ref_type == 'ref_tag':
            # Parse ref tag content
            ref_content = ref_data.get('ref_content', '')
            parsed.update(self._extract_ref_tag_fields(ref_content))
            
        return parsed
    
    def _extract_citation_fields(self, params: Dict[str, str]) -> Dict:
        """Extract structured fields from citation template parameters."""
        fields = {
            'url': None,
            'title': None,
            'authors': [],
            'publication': None,
            'date': None
        }
        
        # Extract URL
        for param in self.url_params:
            if param in params and params[param].strip():
                fields['url'] = params[param].strip()
                break
                
        # Extract title
        for param in self.title_params:
            if param in params and params[param].strip():
                fields['title'] = params[param].strip()
                break
                
        # Extract authors
        authors = []
        for param in self.author_params:
            if param in params and params[param].strip():
                authors.append(params[param].strip())
        fields['authors'] = authors
        
        # Extract publication
        for param in self.publication_params:
            if param in params and params[param].strip():
                fields['publication'] = params[param].strip()
                break
                
        # Extract date
        for param in self.date_params:
            if param in params and params[param].strip():
                fields['date'] = params[param].strip()
                break
                
        return fields
    
    def _extract_ref_tag_fields(self, ref_content: str) -> Dict:
        """Extract structured fields from ref tag content."""
        fields = {
            'url': None,
            'title': None,
            'authors': [],
            'publication': None,
            'date': None
        }
        
        # Simple extraction from ref content (can be improved)
        # Look for URLs
        url_match = re.search(r'https?://[^\s\]]+', ref_content)
        if url_match:
            fields['url'] = url_match.group()
            
        # Look for quoted titles
        title_match = re.search(r'"([^"]+)"', ref_content)
        if title_match:
            fields['title'] = title_match.group(1)
            
        # Look for dates (simple patterns)
        date_match = re.search(r'\b(19|20)\d{2}\b', ref_content)
        if date_match:
            fields['date'] = date_match.group()
            
        return fields
    
    def _group_similar_references(self, parsed_refs: List[Dict]) -> List[List[Dict]]:
        """Group similar references for merging."""
        groups = []
        processed = set()
        
        for i, ref1 in enumerate(parsed_refs):
            if i in processed:
                continue
                
            group = [ref1]
            processed.add(i)
            
            for j in range(i + 1, len(parsed_refs)):
                if j in processed:
                    continue
                    
                ref2 = parsed_refs[j]
                if self._are_similar_references(ref1, ref2):
                    group.append(ref2)
                    processed.add(j)
            
            groups.append(group)
            
        return groups
    
    def _are_similar_references(self, ref1: Dict, ref2: Dict) -> bool:
        """Check if two references are similar enough to merge."""
        # Check URL similarity
        if ref1['url'] and ref2['url']:
            url1_domain = self._extract_domain(ref1['url'])
            url2_domain = self._extract_domain(ref2['url'])
            
            # Same domain + similar path/title indicates same source
            if url1_domain == url2_domain:
                if ref1['title'] and ref2['title']:
                    title_sim = self._text_similarity(ref1['title'], ref2['title'])
                    if title_sim > 0.8:
                        return True
                        
        # Check title similarity
        if ref1['title'] and ref2['title']:
            title_sim = self._text_similarity(ref1['title'], ref2['title'])
            if title_sim > 0.9:
                return True
                
        return False
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return ''
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        # Simple word-based similarity
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _merge_reference_group(self, ref_group: List[Dict]) -> Optional[MergedReference]:
        """Merge a group of similar references."""
        if not ref_group:
            return None
            
        if len(ref_group) == 1:
            ref = ref_group[0]
            return self._create_merged_reference(ref)
        
        # Select best values from all references in the group
        best_values = self._select_best_reference_values(ref_group)
        
        # Collect metadata
        languages = {ref['language'] for ref in ref_group}
        provenances = [ref['provenance'] for ref in ref_group]
        
        return MergedReference(
            ref_id=f"merged_ref_{id(ref_group[0])}",
            content=best_values['content'],
            ref_type=best_values['ref_type'],
            url=best_values['url'],
            title=best_values['title'],
            authors=best_values['authors'],
            publication=best_values['publication'],
            date=best_values['date'],
            source_provenances=provenances,
            languages_found=languages
        )
    
    def _create_merged_reference(self, ref: Dict) -> MergedReference:
        """Create a MergedReference from a single reference."""
        return MergedReference(
            ref_id=f"ref_{id(ref)}",
            content=ref['raw_content'],
            ref_type=ref['ref_type'],
            url=ref['url'],
            title=ref['title'],
            authors=ref['authors'],
            publication=ref['publication'],
            date=ref['date'],
            source_provenances=[ref['provenance']],
            languages_found={ref['language']}
        )
    
    def _select_best_reference_values(self, ref_group: List[Dict]) -> Dict:
        """Select the best values from a group of similar references."""
        best = {
            'content': '',
            'ref_type': 'ref_tag',
            'url': None,
            'title': None,
            'authors': [],
            'publication': None,
            'date': None
        }
        
        # Collect all possible values
        all_urls = [ref['url'] for ref in ref_group if ref['url']]
        all_titles = [ref['title'] for ref in ref_group if ref['title']]
        all_authors = []
        all_publications = [ref['publication'] for ref in ref_group if ref['publication']]
        all_dates = [ref['date'] for ref in ref_group if ref['date']]
        
        for ref in ref_group:
            all_authors.extend(ref['authors'])
        
        # Select best values (prefer English, then most complete)
        best['url'] = self._select_best_value(all_urls, ref_group, 'url')
        best['title'] = self._select_best_value(all_titles, ref_group, 'title')
        best['publication'] = self._select_best_value(all_publications, ref_group, 'publication')
        best['date'] = self._select_best_value(all_dates, ref_group, 'date')
        best['authors'] = list(set(all_authors))  # Deduplicate authors
        
        # Use the most complete content
        best['content'] = max((ref['raw_content'] for ref in ref_group), key=len)
        best['ref_type'] = ref_group[0]['ref_type']  # Use first type
        
        return best
    
    def _select_best_value(self, values: List[str], ref_group: List[Dict], field: str) -> Optional[str]:
        """Select the best value from a list, preferring English sources."""
        if not values:
            return None
            
        # Find values from English sources
        english_values = []
        for ref in ref_group:
            if ref['language'] == 'en' and ref[field]:
                english_values.append(ref[field])
                
        if english_values:
            return max(english_values, key=len)  # Longest English value
            
        # Fall back to longest value overall
        return max(values, key=len)