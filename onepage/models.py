"""Core data models for the Intermediate Representation (IR)."""

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Provenance:
    """Source provenance information for content."""

    wiki: str  # e.g., "enwiki", "hiwiki"
    title: str  # Article title in the source language
    rev_id: int  # Revision ID

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "wiki": self.wiki,
            "title": self.title,
            "rev_id": self.rev_id,
        }


@dataclass
class Reference:
    """A reference/citation for claims and facts."""

    id: str
    doi: str | None = None
    url: str | None = None
    title: str | None = None
    date: str | None = None
    author: str | None = None
    publisher: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Entity:
    """Wikidata entity information."""

    qid: str
    labels: dict[str, str] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Claim:
    """A textual claim from a Wikipedia article."""

    id: str
    type: str = "claim"
    lang: str = "en"
    text: str = ""
    text_en: str | None = None  # English translation for alignment
    sources: list[str] = field(default_factory=list)
    provenance: Provenance | None = None
    confidence: float | None = None  # Translation/alignment confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "type": self.type,
            "lang": self.lang,
            "text": self.text,
            "sources": self.sources,
        }
        if self.text_en:
            result["text_en"] = self.text_en
        if self.provenance:
            result["provenance"] = {
                "wiki": self.provenance.wiki,
                "title": self.provenance.title,
                "rev_id": self.provenance.rev_id,
            }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result


@dataclass
class Fact:
    """A structured fact (typically from infobox or Wikidata)."""

    id: str
    type: str = "fact"
    property: str = ""  # Wikidata property ID (e.g., P39)
    value: str | dict[str, Any] = ""
    qualifiers: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    from_source: str = "wikidata"  # "wikidata", "infobox", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "property": self.property,
            "value": self.value,
            "qualifiers": self.qualifiers,
            "sources": self.sources,
            "from": self.from_source,
        }


@dataclass
class Section:
    """A section in the merged article."""

    id: str
    title: dict[str, str] = field(default_factory=dict)  # multilingual titles
    items: list[str] = field(default_factory=list)  # IDs of claims/facts
    level: int = 2  # Heading level (2 = ==, 3 = ===, etc.)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "items": self.items,
        }
        if self.title:
            result["title"] = self.title
        if self.level != 2:
            result["level"] = self.level
        return result


@dataclass
class IntermediateRepresentation:
    """Complete IR for a merged Wikipedia article."""

    entity: Entity
    sections: list[Section] = field(default_factory=list)
    content: dict[str, Claim | Fact] = field(default_factory=dict)
    references: dict[str, Reference] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity": {
                "qid": self.entity.qid,
                "labels": self.entity.labels,
                "descriptions": self.entity.descriptions,
                "aliases": self.entity.aliases,
            },
            "sections": [s.to_dict() for s in self.sections],
            "content": {k: v.to_dict() for k, v in self.content.items()},
            "references": {k: v.to_dict() for k, v in self.references.items()},
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntermediateRepresentation":
        """Create IR from dictionary."""
        entity = Entity(
            qid=data["entity"]["qid"],
            labels=data["entity"].get("labels", {}),
            descriptions=data["entity"].get("descriptions", {}),
            aliases=data["entity"].get("aliases", {}),
        )

        sections = [
            Section(
                id=s["id"],
                title=s.get("title", {}),
                items=s["items"],
                level=s.get("level", 2),
            )
            for s in data["sections"]
        ]

        content = {}
        for item_id, item_data in data["content"].items():
            if item_data["type"] == "claim":
                prov_data = item_data.get("provenance")
                provenance = None
                if prov_data:
                    provenance = Provenance(
                        wiki=prov_data["wiki"],
                        title=prov_data["title"],
                        rev_id=prov_data["rev_id"],
                    )

                content[item_id] = Claim(
                    id=item_id,
                    lang=item_data["lang"],
                    text=item_data["text"],
                    text_en=item_data.get("text_en"),
                    sources=item_data.get("sources", []),
                    provenance=provenance,
                    confidence=item_data.get("confidence"),
                )
            elif item_data["type"] == "fact":
                content[item_id] = Fact(
                    id=item_id,
                    property=item_data["property"],
                    value=item_data["value"],
                    qualifiers=item_data.get("qualifiers", {}),
                    sources=item_data.get("sources", []),
                    from_source=item_data.get("from", "wikidata"),
                )

        references = {}
        for ref_id, ref_data in data["references"].items():
            # Remove 'id' from ref_data if it exists to avoid duplicate parameter
            ref_dict = dict(ref_data)
            ref_dict.pop("id", None)
            references[ref_id] = Reference(id=ref_id, **ref_dict)

        return cls(
            entity=entity,
            sections=sections,
            content=content,
            references=references,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "IntermediateRepresentation":
        """Create IR from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
