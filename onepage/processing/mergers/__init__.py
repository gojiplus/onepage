"""Content-type-aware merging modules for Wikipedia articles."""

from .text_merger import TextMerger
from .fact_merger import FactMerger  
from .media_merger import MediaMerger
from .reference_merger import ReferenceMerger

__all__ = ['TextMerger', 'FactMerger', 'MediaMerger', 'ReferenceMerger']