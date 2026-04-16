"""Configuration management for wikifuse."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LLMConfig:
    """Configuration for LLM-based merging."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    enabled: bool = True


@dataclass
class Config:
    """Configuration for wikifuse operations."""

    qid: str
    languages: list[str]
    base_language: str = "en"
    max_refs_per_claim: int = 3
    emit: list[str] | None = None
    top_languages: int = 2
    llm: LLMConfig = field(default_factory=LLMConfig)

    def __post_init__(self) -> None:
        if self.emit is None:
            self.emit = ["ir", "wikitext", "html"]
        if isinstance(self.llm, dict):
            self.llm = LLMConfig(**self.llm)

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """Load configuration from a YAML file."""
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "qid": self.qid,
            "languages": self.languages,
            "base_language": self.base_language,
            "max_refs_per_claim": self.max_refs_per_claim,
            "emit": self.emit,
            "top_languages": self.top_languages,
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key_env": self.llm.api_key_env,
                "enabled": self.llm.enabled,
            },
        }
