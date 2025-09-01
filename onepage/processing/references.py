"""Reference canonicalization and deduplication system."""

import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import hashlib
from datetime import datetime

from ..core.models import Reference


@dataclass
class CanonicalReference:
    """A canonicalized reference with normalized metadata."""
    canonical_id: str
    merged_refs: List[Reference]
    doi: Optional[str] = None
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    authors: List[str] = None
    date: Optional[str] = None
    publisher: Optional[str] = None
    confidence: float = 1.0  # Confidence in the canonicalization
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []


class ReferenceCanonicalizationService:
    """Service for canonicalizing and deduplicating references."""
    
    def __init__(self):
        # DOI patterns
        self.doi_pattern = re.compile(r'10\.\d{4,}/[^\s]+', re.IGNORECASE)
        
        # Common URL normalizations
        self.url_normalizations = {
            r'https?://www\.': 'https://',
            r'https?://m\.': 'https://',
            r'/index\.php': '',
            r'#.*$': '',  # Remove fragments
        }
        
        # Common title cleanups
        self.title_cleanups = [
            r'\s*\|\s*.*$',  # Remove "| Publisher" suffixes
            r'\s*-\s*.*$',   # Remove "- Source" suffixes  
            r'^\s*"([^"]*)".*$',  # Extract quoted titles
        ]
    
    def canonicalize_references(self, references: List[Reference]) -> List[CanonicalReference]:
        """
        Canonicalize and deduplicate a list of references.
        
        Args:
            references: List of references to process
            
        Returns:
            List of canonical references
        """
        # Step 1: Normalize individual references
        normalized_refs = [self._normalize_reference(ref) for ref in references]
        
        # Step 2: Group by similarity
        groups = self._group_similar_references(normalized_refs)
        
        # Step 3: Create canonical references
        canonical_refs = []
        for group in groups:
            canonical = self._create_canonical_reference(group)
            canonical_refs.append(canonical)
        
        return canonical_refs
    
    def _normalize_reference(self, ref: Reference) -> Reference:
        """Normalize a single reference."""
        # Extract DOI if present
        doi = self._extract_doi(ref)
        
        # Normalize URL
        normalized_url = self._normalize_url(ref.url) if ref.url else None
        
        # Clean title
        cleaned_title = self._clean_title(ref.title) if ref.title else None
        
        # Normalize date
        normalized_date = self._normalize_date(ref.date) if ref.date else None
        
        # Clean author
        cleaned_author = self._clean_author(ref.author) if ref.author else None
        
        return Reference(
            id=ref.id,
            doi=doi,
            url=normalized_url,
            title=cleaned_title,
            date=normalized_date,
            author=cleaned_author,
            publisher=ref.publisher,
        )
    
    def _extract_doi(self, ref: Reference) -> Optional[str]:
        """Extract DOI from reference fields."""
        # Check DOI field first
        if ref.doi:
            doi_match = self.doi_pattern.search(ref.doi)
            if doi_match:
                return doi_match.group().lower()
        
        # Check URL for DOI
        if ref.url:
            doi_match = self.doi_pattern.search(ref.url)
            if doi_match:
                return doi_match.group().lower()
        
        # Check title for DOI
        if ref.title:
            doi_match = self.doi_pattern.search(ref.title)
            if doi_match:
                return doi_match.group().lower()
        
        return None
    
    def _normalize_url(self, url: str) -> str:
        """Normalize a URL for comparison."""
        if not url:
            return url
        
        # Apply common normalizations
        normalized = url
        for pattern, replacement in self.url_normalizations.items():
            normalized = re.sub(pattern, replacement, normalized)
        
        # Parse and rebuild URL to normalize format
        try:
            parsed = urlparse(normalized)
            # Remove common tracking parameters
            if parsed.query:
                query_params = parse_qs(parsed.query)
                # Remove common tracking parameters
                tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'}
                filtered_params = {k: v for k, v in query_params.items() if k not in tracking_params}
                
                if filtered_params:
                    query_string = '&'.join(f"{k}={v[0]}" for k, v in filtered_params.items())
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query_string}"
                else:
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            else:
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except:
            # If URL parsing fails, return as-is
            pass
        
        return normalized.lower()
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize a title."""
        cleaned = title
        
        # Apply title cleanups
        for pattern in self.title_cleanups:
            match = re.search(pattern, cleaned)
            if match and len(match.groups()) > 0:
                cleaned = match.group(1)
                break
            else:
                cleaned = re.sub(pattern, '', cleaned)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())
        
        return cleaned
    
    def _normalize_date(self, date: str) -> str:
        """Normalize a date string."""
        if not date:
            return date
        
        # Extract year-month-day pattern
        date_match = re.search(r'(\d{4})-?(\d{1,2})-?(\d{1,2})', date)
        if date_match:
            year, month, day = date_match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Extract just year
        year_match = re.search(r'(\d{4})', date)
        if year_match:
            return year_match.group(1)
        
        return date
    
    def _clean_author(self, author: str) -> str:
        """Clean author names."""
        if not author:
            return author
        
        # Basic author name cleanup
        author = re.sub(r'\s+', ' ', author.strip())
        
        # Remove common prefixes/suffixes
        author = re.sub(r'^(by\s+)', '', author, flags=re.IGNORECASE)
        
        return author
    
    def _group_similar_references(self, references: List[Reference]) -> List[List[Reference]]:
        """Group similar references together."""
        groups = []
        used = set()
        
        for i, ref1 in enumerate(references):
            if i in used:
                continue
            
            group = [ref1]
            used.add(i)
            
            for j, ref2 in enumerate(references[i+1:], i+1):
                if j in used:
                    continue
                
                if self._are_references_similar(ref1, ref2):
                    group.append(ref2)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def _are_references_similar(self, ref1: Reference, ref2: Reference) -> bool:
        """Check if two references are similar enough to merge."""
        # DOI match is strongest signal
        if ref1.doi and ref2.doi and ref1.doi == ref2.doi:
            return True
        
        # URL match
        if ref1.url and ref2.url and ref1.url == ref2.url:
            return True
        
        # Title similarity
        if ref1.title and ref2.title:
            title_similarity = self._calculate_string_similarity(ref1.title, ref2.title)
            if title_similarity >= 0.8:
                return True
        
        # Combined heuristics
        matches = 0
        total_checks = 0
        
        # Check date
        if ref1.date and ref2.date:
            total_checks += 1
            if ref1.date == ref2.date:
                matches += 1
        
        # Check author
        if ref1.author and ref2.author:
            total_checks += 1
            author_similarity = self._calculate_string_similarity(ref1.author, ref2.author)
            if author_similarity >= 0.7:
                matches += 1
        
        # Check publisher
        if ref1.publisher and ref2.publisher:
            total_checks += 1
            if ref1.publisher.lower() == ref2.publisher.lower():
                matches += 1
        
        # Require at least 2 matching fields with high confidence
        return total_checks >= 2 and matches >= 2
    
    def _calculate_string_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings."""
        if not s1 or not s2:
            return 0.0
        
        # Simple Jaccard similarity on words
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _create_canonical_reference(self, group: List[Reference]) -> CanonicalReference:
        """Create a canonical reference from a group of similar references."""
        # Choose the best values from the group
        best_doi = self._choose_best_doi(group)
        best_url = self._choose_best_url(group)
        best_title = self._choose_best_title(group)
        best_date = self._choose_best_date(group)
        best_authors = self._merge_authors(group)
        best_publisher = self._choose_best_publisher(group)
        
        # Generate canonical ID
        canonical_id = self._generate_canonical_id(best_doi, best_url, best_title)
        
        # Calculate confidence
        confidence = self._calculate_canonicalization_confidence(group)
        
        return CanonicalReference(
            canonical_id=canonical_id,
            merged_refs=group,
            doi=best_doi,
            canonical_url=best_url,
            title=best_title,
            authors=best_authors,
            date=best_date,
            publisher=best_publisher,
            confidence=confidence,
        )
    
    def _choose_best_doi(self, group: List[Reference]) -> Optional[str]:
        """Choose the best DOI from a group."""
        dois = [ref.doi for ref in group if ref.doi]
        return dois[0] if dois else None
    
    def _choose_best_url(self, group: List[Reference]) -> Optional[str]:
        """Choose the best URL from a group."""
        urls = [ref.url for ref in group if ref.url]
        if not urls:
            return None
        
        # Prefer HTTPS URLs
        https_urls = [url for url in urls if url.startswith('https://')]
        if https_urls:
            return https_urls[0]
        
        return urls[0]
    
    def _choose_best_title(self, group: List[Reference]) -> Optional[str]:
        """Choose the best title from a group."""
        titles = [ref.title for ref in group if ref.title]
        if not titles:
            return None
        
        # Prefer longer, more descriptive titles
        return max(titles, key=len)
    
    def _choose_best_date(self, group: List[Reference]) -> Optional[str]:
        """Choose the best date from a group."""
        dates = [ref.date for ref in group if ref.date]
        return dates[0] if dates else None
    
    def _merge_authors(self, group: List[Reference]) -> List[str]:
        """Merge author information from a group."""
        all_authors = set()
        for ref in group:
            if ref.author:
                # Split on common author separators
                authors = re.split(r'[;,&]|\sand\s', ref.author)
                for author in authors:
                    author = author.strip()
                    if author:
                        all_authors.add(author)
        
        return sorted(list(all_authors))
    
    def _choose_best_publisher(self, group: List[Reference]) -> Optional[str]:
        """Choose the best publisher from a group."""
        publishers = [ref.publisher for ref in group if ref.publisher]
        return publishers[0] if publishers else None
    
    def _generate_canonical_id(self, doi: Optional[str], url: Optional[str], 
                              title: Optional[str]) -> str:
        """Generate a canonical ID for a reference."""
        # Use DOI if available
        if doi:
            return f"doi_{hashlib.md5(doi.encode()).hexdigest()[:8]}"
        
        # Use URL if available
        if url:
            return f"url_{hashlib.md5(url.encode()).hexdigest()[:8]}"
        
        # Use title if available
        if title:
            return f"title_{hashlib.md5(title.encode()).hexdigest()[:8]}"
        
        # Fallback random ID
        import uuid
        return f"ref_{str(uuid.uuid4())[:8]}"
    
    def _calculate_canonicalization_confidence(self, group: List[Reference]) -> float:
        """Calculate confidence in the canonicalization."""
        if len(group) == 1:
            return 1.0
        
        # Higher confidence if multiple refs have same DOI or URL
        doi_count = len([ref for ref in group if ref.doi])
        url_count = len([ref for ref in group if ref.url])
        
        if doi_count > 1:
            return 0.95
        elif url_count > 1:
            return 0.9
        else:
            return 0.75  # Based on title/author similarity only