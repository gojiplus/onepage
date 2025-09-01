"""Merge media content from multiple Wikipedia language editions."""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import re

from ..content_classifier import ClassifiedContent, ContentType
from ...core.models import Provenance


@dataclass
class MergedMediaItem:
    """A media item merged from multiple sources."""
    filename: str
    best_caption: str
    all_captions: Dict[str, str]  # language -> caption
    parameters: List[str]
    source_provenances: List[Provenance]
    media_type: str  # 'image', 'file', etc.


class MediaMerger:
    """Merges media content from multiple language sources."""
    
    def __init__(self):
        self.image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', 
            '.tiff', '.bmp', '.ico'
        }
        
    def merge_media_content(self, classified_items: List[ClassifiedContent]) -> List[MergedMediaItem]:
        """
        Merge media content from multiple sources.
        
        Args:
            classified_items: List of classified content items (image type only)
            
        Returns:
            List of merged media items
        """
        # Filter only media content
        media_items = [item for item in classified_items if item.content_type == ContentType.IMAGE]
        
        if not media_items:
            return []
            
        # Group by filename (normalize Commons filenames)
        grouped_media = self._group_by_filename(media_items)
        
        merged_items = []
        for filename, items in grouped_media.items():
            merged_item = self._merge_media_group(filename, items)
            if merged_item:
                merged_items.append(merged_item)
                
        return merged_items
    
    def _group_by_filename(self, media_items: List[ClassifiedContent]) -> Dict[str, List[ClassifiedContent]]:
        """Group media items by normalized filename."""
        groups = defaultdict(list)
        
        for item in media_items:
            filename = item.structured_data.get('filename', '')
            normalized_filename = self._normalize_filename(filename)
            
            if normalized_filename:
                groups[normalized_filename].append(item)
                
        return dict(groups)
    
    def _normalize_filename(self, filename: str) -> str:
        """Normalize filename for grouping."""
        if not filename:
            return ''
            
        # Remove namespace prefixes (File:, Image:)
        normalized = re.sub(r'^(file|image):', '', filename.lower())
        
        # Handle Commons filename variations
        normalized = normalized.strip()
        
        return normalized
    
    def _merge_media_group(self, filename: str, items: List[ClassifiedContent]) -> Optional[MergedMediaItem]:
        """Merge multiple instances of the same media file."""
        if not items:
            return None
            
        # Collect all captions by language
        captions_by_lang = {}
        all_parameters = set()
        provenances = []
        
        for item in items:
            metadata = item.structured_data
            
            # Collect caption
            caption = metadata.get('caption', '').strip()
            if caption:
                captions_by_lang[item.language] = caption
                
            # Collect parameters (thumb, right, 200px, etc.)
            params = metadata.get('parameters', [])
            all_parameters.update(params)
            
            # Collect provenance
            provenances.append(item.provenance)
        
        # Select best caption (prefer English, then longest)
        best_caption = self._select_best_caption(captions_by_lang)
        
        # Determine media type
        media_type = self._determine_media_type(filename)
        
        return MergedMediaItem(
            filename=filename,
            best_caption=best_caption,
            all_captions=captions_by_lang,
            parameters=list(all_parameters),
            source_provenances=provenances,
            media_type=media_type
        )
    
    def _select_best_caption(self, captions_by_lang: Dict[str, str]) -> str:
        """Select the best caption from available options."""
        if not captions_by_lang:
            return ''
            
        # Prefer English caption
        if 'en' in captions_by_lang and captions_by_lang['en'].strip():
            return captions_by_lang['en'].strip()
            
        # Fall back to longest caption
        if captions_by_lang:
            best_caption = max(captions_by_lang.values(), key=len)
            return best_caption.strip()
            
        return ''
    
    def _determine_media_type(self, filename: str) -> str:
        """Determine the type of media file."""
        filename_lower = filename.lower()
        
        # Check for common image extensions
        for ext in self.image_extensions:
            if filename_lower.endswith(ext):
                return 'image'
                
        # Check for other media types
        if any(filename_lower.endswith(ext) for ext in ['.mp4', '.webm', '.ogv']):
            return 'video'
        elif any(filename_lower.endswith(ext) for ext in ['.mp3', '.ogg', '.wav']):
            return 'audio'
        elif any(filename_lower.endswith(ext) for ext in ['.pdf', '.djvu']):
            return 'document'
        else:
            return 'file'
    
    def deduplicate_media(self, merged_items: List[MergedMediaItem]) -> List[MergedMediaItem]:
        """Remove duplicate media items based on filename similarity."""
        if len(merged_items) <= 1:
            return merged_items
            
        # Group by similar filenames
        groups = []
        processed = set()
        
        for i, item in enumerate(merged_items):
            if i in processed:
                continue
                
            group = [item]
            processed.add(i)
            
            for j in range(i + 1, len(merged_items)):
                if j in processed:
                    continue
                    
                if self._are_similar_filenames(item.filename, merged_items[j].filename):
                    group.append(merged_items[j])
                    processed.add(j)
            
            groups.append(group)
        
        # Select best item from each group
        deduplicated = []
        for group in groups:
            best_item = self._select_best_media_item(group)
            deduplicated.append(best_item)
            
        return deduplicated
    
    def _are_similar_filenames(self, filename1: str, filename2: str) -> bool:
        """Check if two filenames refer to the same media."""
        # Simple similarity check - can be improved
        base1 = re.sub(r'\.[^.]+$', '', filename1.lower())
        base2 = re.sub(r'\.[^.]+$', '', filename2.lower())
        
        # Remove common prefixes/suffixes
        base1 = re.sub(r'[-_\s]+', '', base1)
        base2 = re.sub(r'[-_\s]+', '', base2)
        
        return base1 == base2
    
    def _select_best_media_item(self, media_group: List[MergedMediaItem]) -> MergedMediaItem:
        """Select the best media item from a group of similar items."""
        if len(media_group) == 1:
            return media_group[0]
            
        # Score each item
        scored_items = []
        
        for item in media_group:
            score = 0
            
            # Prefer items with captions
            if item.best_caption:
                score += 10
                
            # Prefer items with more caption variations
            score += len(item.all_captions) * 2
            
            # Prefer items with formatting parameters
            score += len(item.parameters)
            
            # Prefer images over other file types
            if item.media_type == 'image':
                score += 5
                
            scored_items.append((score, item))
        
        # Return highest scored item
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return scored_items[0][1]