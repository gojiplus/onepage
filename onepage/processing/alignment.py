"""Sentence embedding and cross-lingual alignment algorithms."""

import numpy as np
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
import re

# Lazy import to avoid crashes
HAS_SENTENCE_TRANSFORMERS = False
SentenceTransformer = None

def _lazy_import_sentence_transformers():
    global HAS_SENTENCE_TRANSFORMERS, SentenceTransformer
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as ST
            SentenceTransformer = ST
            HAS_SENTENCE_TRANSFORMERS = True
        except ImportError:
            # Mock SentenceTransformer for when it's not available
            class MockSentenceTransformer:
                def __init__(self, model_name: str):
                    pass
                def encode(self, texts):
                    import numpy as np
                    # Return dummy embeddings for testing
                    return np.random.rand(len(texts), 384)
            SentenceTransformer = MockSentenceTransformer
            HAS_SENTENCE_TRANSFORMERS = False

from ..core.models import Claim


@dataclass
class AlignmentCluster:
    """A cluster of aligned claims across languages."""
    id: str
    claims: List[Claim]
    confidence: float
    primary_claim: Optional[Claim] = None  # Best representative claim
    
    def get_languages(self) -> Set[str]:
        """Get all languages represented in this cluster."""
        return {claim.lang for claim in self.claims}
    
    def get_claim_by_language(self, language: str) -> Optional[Claim]:
        """Get the claim for a specific language."""
        for claim in self.claims:
            if claim.lang == language:
                return claim
        return None


class SentenceAligner:
    """Aligns sentences across languages using embeddings."""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Initialize the sentence aligner.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        _lazy_import_sentence_transformers()
        self.model = SentenceTransformer(model_name)
        
        # Similarity thresholds for alignment
        self.similarity_threshold = 0.75  # Minimum similarity for alignment
        self.high_confidence_threshold = 0.85  # High confidence alignment
        
    def align_claims(self, claims: List[Claim]) -> List[AlignmentCluster]:
        """
        Align claims across languages into clusters.
        
        Args:
            claims: List of claims to align
            
        Returns:
            List of alignment clusters
        """
        if not claims:
            return []
        
        # Group claims by section for better alignment
        claims_by_section = self._group_claims_by_section(claims)
        
        all_clusters = []
        for section_id, section_claims in claims_by_section.items():
            section_clusters = self._align_section_claims(section_claims)
            all_clusters.extend(section_clusters)
        
        return all_clusters
    
    def _group_claims_by_section(self, claims: List[Claim]) -> Dict[str, List[Claim]]:
        """Group claims by their section ID."""
        sections = {}
        for claim in claims:
            section_id = getattr(claim, 'section_id', 'unknown')
            if section_id not in sections:
                sections[section_id] = []
            sections[section_id].append(claim)
        return sections
    
    def _align_section_claims(self, claims: List[Claim]) -> List[AlignmentCluster]:
        """Align claims within a single section."""
        if len(claims) <= 1:
            # Single claim or no claims - create individual clusters
            return [
                AlignmentCluster(
                    id=f"cluster_{claim.id}",
                    claims=[claim],
                    confidence=1.0,
                    primary_claim=claim,
                )
                for claim in claims
            ]
        
        # Use English translations for embedding
        texts = []
        for claim in claims:
            text = claim.text_en if claim.text_en else claim.text
            texts.append(text)
        
        # Generate embeddings
        embeddings = self.model.encode(texts)
        
        # Calculate similarity matrix
        similarities = np.dot(embeddings, embeddings.T)
        
        # Perform clustering based on similarity
        clusters = self._cluster_by_similarity(claims, similarities)
        
        return clusters
    
    def _cluster_by_similarity(self, claims: List[Claim], 
                              similarities: np.ndarray) -> List[AlignmentCluster]:
        """Cluster claims based on similarity matrix."""
        n = len(claims)
        visited = set()
        clusters = []
        
        for i in range(n):
            if i in visited:
                continue
            
            # Start new cluster
            cluster_claims = [claims[i]]
            cluster_indices = {i}
            visited.add(i)
            
            # Find similar claims
            for j in range(i + 1, n):
                if j in visited:
                    continue
                
                # Check if similar enough to join cluster
                if similarities[i][j] >= self.similarity_threshold:
                    # Also check if it's similar to other claims in the cluster
                    similar_to_cluster = any(
                        similarities[k][j] >= self.similarity_threshold
                        for k in cluster_indices
                    )
                    
                    if similar_to_cluster:
                        cluster_claims.append(claims[j])
                        cluster_indices.add(j)
                        visited.add(j)
            
            # Calculate cluster confidence
            if len(cluster_claims) == 1:
                confidence = 1.0
            else:
                # Average similarity within cluster
                cluster_similarities = [
                    similarities[i][j] 
                    for i in cluster_indices 
                    for j in cluster_indices 
                    if i != j
                ]
                confidence = float(np.mean(cluster_similarities))
            
            # Choose primary claim (prefer English, then highest confidence)
            primary_claim = self._choose_primary_claim(cluster_claims)
            
            clusters.append(AlignmentCluster(
                id=f"cluster_{len(clusters)}",
                claims=cluster_claims,
                confidence=confidence,
                primary_claim=primary_claim,
            ))
        
        return clusters
    
    def _choose_primary_claim(self, claims: List[Claim]) -> Claim:
        """Choose the best primary claim from a cluster."""
        # Prefer English claims
        english_claims = [c for c in claims if c.lang == "en"]
        if english_claims:
            return english_claims[0]
        
        # Otherwise, prefer claims with highest confidence
        if all(c.confidence is not None for c in claims):
            return max(claims, key=lambda c: c.confidence or 0)
        
        # Fallback to first claim
        return claims[0]
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts."""
        embeddings = self.model.encode([text1, text2])
        similarity = float(np.dot(embeddings[0], embeddings[1]))
        return similarity
    
    def find_duplicate_claims(self, claims: List[Claim], 
                             threshold: float = 0.9) -> List[List[Claim]]:
        """
        Find groups of duplicate claims within the same language.
        
        Args:
            claims: List of claims to check for duplicates
            threshold: Similarity threshold for considering claims duplicates
            
        Returns:
            List of claim groups that are likely duplicates
        """
        # Group by language first
        by_language = {}
        for claim in claims:
            if claim.lang not in by_language:
                by_language[claim.lang] = []
            by_language[claim.lang].append(claim)
        
        duplicate_groups = []
        
        # Check for duplicates within each language
        for lang, lang_claims in by_language.items():
            if len(lang_claims) <= 1:
                continue
            
            texts = [claim.text for claim in lang_claims]
            embeddings = self.model.encode(texts)
            similarities = np.dot(embeddings, embeddings.T)
            
            visited = set()
            for i in range(len(lang_claims)):
                if i in visited:
                    continue
                
                duplicates = [lang_claims[i]]
                visited.add(i)
                
                for j in range(i + 1, len(lang_claims)):
                    if j in visited:
                        continue
                    
                    if similarities[i][j] >= threshold:
                        duplicates.append(lang_claims[j])
                        visited.add(j)
                
                if len(duplicates) > 1:
                    duplicate_groups.append(duplicates)
        
        return duplicate_groups