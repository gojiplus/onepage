"""Configuration management for onepage."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml


@dataclass
class Config:
    """Configuration for onepage operations."""
    
    qid: str
    languages: List[str]
    base_language: str = "en"
    max_refs_per_claim: int = 3
    emit: List[str] = None
    
    def __post_init__(self) -> None:
        if self.emit is None:
            self.emit = ["ir", "wikitext", "html"]
    
    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """Load configuration from a YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "qid": self.qid,
            "languages": self.languages,
            "base_language": self.base_language,
            "max_refs_per_claim": self.max_refs_per_claim,
            "emit": self.emit,
        }