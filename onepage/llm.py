"""LLM service for intelligent content merging."""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

HAS_OPENAI = False
OpenAI: Any = None
try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    pass


class LLMService:
    """LLM service for merging Wikipedia sections intelligently."""

    client: Any

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
    ):
        """Initialize LLM service.

        Args:
            api_key: API key for the LLM provider. If None, reads from
                     OPENAI_API_KEY environment variable.
            model: Model identifier to use.
            provider: LLM provider (currently only "openai" supported).
        """
        self.model = model
        self.provider = provider
        self.client = None

        if provider == "openai":
            if not HAS_OPENAI:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                    "or pass api_key parameter."
                )
            self.client = OpenAI(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def merge_sections(
        self,
        sections: List[Tuple[str, str, str]],
        entity_name: str,
        section_heading: str,
    ) -> str:
        """Merge sections from different Wikipedia language versions.

        Args:
            sections: List of (source_wiki, lang, content) tuples.
                      e.g., [("enwiki", "en", "..."), ("frwiki", "fr", "...")]
            entity_name: Name of the entity being described.
            section_heading: The section heading being merged.

        Returns:
            Merged text combining information from all sources.
        """
        if not sections:
            return ""

        if len(sections) == 1:
            return sections[0][2]

        prompt = self._build_merge_prompt(sections, entity_name, section_heading)
        return self._call_llm(prompt)

    def _build_merge_prompt(
        self,
        sections: List[Tuple[str, str, str]],
        entity_name: str,
        section_heading: str,
    ) -> str:
        """Build the prompt for section merging."""
        sources_text = []
        for i, (wiki, lang, content) in enumerate(sections, 1):
            lang_note = " (translated to English)" if lang != "en" else ""
            sources_text.append(f"Source {i} ({wiki}{lang_note}):\n{content}")

        sources_combined = "\n\n".join(sources_text)

        prompt = f"""Merge these Wikipedia sections about "{entity_name}" (section: {section_heading}) into one comprehensive section.

Instructions:
- Preserve ALL unique facts from each source
- Remove duplicate information
- Maintain factual accuracy
- Write in encyclopedic style
- Keep citations markers like [1], [2] if present
- Output only the merged section text, no explanations

{sources_combined}

Merged section:"""
        return prompt

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API."""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert Wikipedia editor. Your task is to merge "
                            "content from multiple Wikipedia language versions into a "
                            "single comprehensive section. Preserve all unique facts "
                            "and maintain encyclopedic tone."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        raise ValueError(f"Unsupported provider: {self.provider}")


class MockLLMService:
    """Mock LLM service for testing without API calls."""

    def __init__(self, **_kwargs: Any) -> None:
        pass

    def merge_sections(
        self,
        sections: List[Tuple[str, str, str]],
        entity_name: str,
        section_heading: str,
    ) -> str:
        """Return combined content from all sections for testing."""
        del entity_name, section_heading
        if not sections:
            return ""
        combined = []
        for _wiki, _lang, content in sections:
            combined.append(content)
        return " ".join(combined)
