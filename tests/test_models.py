"""Tests for core data models."""

import json
import pytest

from onepage.models import (
    Entity,
    Claim,
    Fact,
    Reference,
    Provenance,
    Section,
    IntermediateRepresentation,
)


class TestEntity:
    """Test Entity model."""
    
    def test_create_entity(self):
        """Test creating an entity."""
        entity = Entity(
            qid="Q1058",
            labels={"en": "Narendra Modi", "hi": "नरेन्द्र मोदी"},
            descriptions={"en": "Indian politician"},
        )
        
        assert entity.qid == "Q1058"
        assert entity.labels["en"] == "Narendra Modi"
        assert entity.descriptions["en"] == "Indian politician"


class TestClaim:
    """Test Claim model."""
    
    def test_create_claim(self):
        """Test creating a claim."""
        provenance = Provenance(
            wiki="enwiki",
            title="Narendra Modi",
            rev_id=123456,
        )
        
        claim = Claim(
            id="c1",
            lang="en",
            text="Narendra Modi is an Indian politician.",
            sources=["r1", "r2"],
            provenance=provenance,
        )
        
        assert claim.id == "c1"
        assert claim.lang == "en"
        assert claim.text == "Narendra Modi is an Indian politician."
        assert claim.sources == ["r1", "r2"]
        assert claim.provenance.wiki == "enwiki"
    
    def test_claim_to_dict(self):
        """Test claim serialization to dictionary."""
        claim = Claim(
            id="c1",
            lang="hi",
            text="नरेन्द्र मोदी एक भारतीय राजनीतिज्ञ हैं।",
            text_en="Narendra Modi is an Indian politician.",
        )
        
        result = claim.to_dict()
        
        assert result["type"] == "claim"
        assert result["lang"] == "hi"
        assert result["text"] == "नरेन्द्र मोदी एक भारतीय राजनीतिज्ञ हैं।"
        assert result["text_en"] == "Narendra Modi is an Indian politician."


class TestFact:
    """Test Fact model."""
    
    def test_create_fact(self):
        """Test creating a fact."""
        fact = Fact(
            id="f1",
            property="P39",
            value={"qid": "Q11696"},
            qualifiers={"start_time": "2014-05-26"},
            sources=["r5"],
        )
        
        assert fact.id == "f1"
        assert fact.property == "P39"
        assert fact.value == {"qid": "Q11696"}
        assert fact.qualifiers["start_time"] == "2014-05-26"
    
    def test_fact_to_dict(self):
        """Test fact serialization."""
        fact = Fact(
            id="f1",
            property="P569",
            value="1950-09-17",
            from_source="wikidata",
        )
        
        result = fact.to_dict()
        
        assert result["type"] == "fact"
        assert result["property"] == "P569"
        assert result["value"] == "1950-09-17"
        assert result["from"] == "wikidata"


class TestIntermediateRepresentation:
    """Test IR model."""
    
    def test_create_ir(self):
        """Test creating an IR."""
        entity = Entity(qid="Q1058", labels={"en": "Test"})
        section = Section(id="lead", items=["c1"])
        claim = Claim(id="c1", text="Test claim")
        
        ir = IntermediateRepresentation(
            entity=entity,
            sections=[section],
            content={"c1": claim},
        )
        
        assert ir.entity.qid == "Q1058"
        assert len(ir.sections) == 1
        assert "c1" in ir.content
    
    def test_ir_json_roundtrip(self):
        """Test IR JSON serialization and deserialization."""
        entity = Entity(qid="Q1058", labels={"en": "Test"})
        section = Section(id="lead", items=["c1"])
        claim = Claim(id="c1", text="Test claim", lang="en")
        ref = Reference(id="r1", title="Test Reference")
        
        ir = IntermediateRepresentation(
            entity=entity,
            sections=[section],
            content={"c1": claim},
            references={"r1": ref},
        )
        
        # Serialize to JSON
        json_str = ir.to_json()
        
        # Deserialize back
        ir_restored = IntermediateRepresentation.from_json(json_str)
        
        # Check that data is preserved
        assert ir_restored.entity.qid == "Q1058"
        assert len(ir_restored.sections) == 1
        assert ir_restored.sections[0].id == "lead"
        assert "c1" in ir_restored.content
        assert ir_restored.content["c1"].text == "Test claim"
        assert "r1" in ir_restored.references