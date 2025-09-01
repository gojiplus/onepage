"""Translation service integration for cross-lingual alignment."""

import requests
from typing import List, Dict, Optional, Tuple
import time
import re
import wikitextparser as wtp

try:
    from langdetect import detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    def detect(text: str) -> str:
        return "unknown"

from .models import Claim


class TranslationService:
    """Translation service for converting text to English."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "onepage/0.1.0 (https://github.com/soodoku/onepage)"
        })
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
    
    def translate_to_english(self, text: str, source_lang: str) -> Tuple[str, float]:
        """
        Translate text to English.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            
        Returns:
            Tuple of (translated_text, confidence_score)
        """
        # Skip translation if already English
        if source_lang == "en":
            return text, 1.0
        
        # Detect language if not sure
        try:
            detected_lang = detect(text)
            if detected_lang == "en":
                return text, 1.0
        except:
            # Language detection failed, proceed with given source_lang
            pass
        
        # For now, implement a simple translation using a free service
        # In production, you'd want to use a proper translation API
        translated_text = self._translate_via_libre(text, source_lang, "en")
        
        # Simple confidence score based on text length and complexity
        confidence = min(1.0, len(text) / 1000)  # Longer text = lower confidence
        
        return translated_text, confidence
    
    def _translate_via_libre(self, text: str, source: str, target: str) -> str:
        """
        Translate using MyMemory free translation API.
        """
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        
        if source == target:
            return text
            
        # Use MyMemory free translation API
        try:
            # Limit text length to avoid API limits
            text_to_translate = text[:500] if len(text) > 500 else text
            
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text_to_translate,
                'langpair': f'{source}|{target}',
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('responseStatus') == 200:
                translated = data['responseData']['translatedText']
                # Clean up common translation artifacts
                translated = translated.replace('&quot;', '"').replace('&amp;', '&')
                self.last_request_time = time.time()
                return translated
            else:
                # Fallback to placeholder
                return f"[TRANSLATED FROM {source.upper()}] {text}"
                
        except Exception as e:
            # Fallback to placeholder on error
            print(f"Translation failed: {e}")
            return f"[TRANSLATED FROM {source.upper()}] {text}"
    
    def translate_claims(self, claims: List[Claim]) -> List[Claim]:
        """
        Translate a list of claims to English for alignment.
        
        Args:
            claims: List of claims to translate
            
        Returns:
            List of claims with English translations
        """
        translated_claims = []
        
        for claim in claims:
            if claim.lang != "en":
                translated_text, confidence = self.translate_to_english(
                    claim.text, claim.lang
                )
                
                # Update the claim with translation
                claim.text_en = translated_text
                claim.confidence = confidence
            else:
                # English claims don't need translation
                claim.text_en = claim.text
                claim.confidence = 1.0
            
            translated_claims.append(claim)
        
        return translated_claims
    
    def batch_translate(self, texts: List[str], source_lang: str) -> List[Tuple[str, float]]:
        """
        Translate multiple texts in batch for efficiency.
        
        Args:
            texts: List of texts to translate
            source_lang: Source language code
            
        Returns:
            List of (translated_text, confidence) tuples
        """
        results = []
        
        for text in texts:
            translated, confidence = self.translate_to_english(text, source_lang)
            results.append((translated, confidence))
            
        return results


class TextCleaner:
    """Clean and normalize text content."""
    
    @staticmethod
    def clean_sentence(text: str) -> str:
        """Clean a sentence for processing."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove citation needed markers
        text = re.sub(r'\[citation needed\]', '', text, flags=re.IGNORECASE)
        
        # Remove disambiguation markers
        text = re.sub(r'\s*\(disambiguation\)', '', text, flags=re.IGNORECASE)
        
        # Normalize quotation marks
        text = re.sub(r'[""'']', '"', text)
        
        return text
    
    @staticmethod
    def extract_plain_text(wikitext: str) -> str:
        """Extract plain text from wikitext, removing all markup."""
        parsed = wtp.parse(wikitext)
        
        # Remove templates starting from the end so index positions remain
        # valid for earlier entries. ``wikitextparser`` objects become
        # "dead" when text before them is mutated, so iterating in reverse
        # avoids ``DeadIndexError`` when stripping multiple templates.
        for template in parsed.templates[::-1]:
            template.string = ""

        # Remove references using the same reverse-iteration strategy to
        # prevent index invalidation after previous mutations.
        for tag in parsed.get_tags()[::-1]:
            if tag.name and tag.name.lower() in ["ref", "references"]:
                tag.string = ""
        
        # Get plain text
        # ``wikitextparser`` exposes ``plain_text`` for extracting readable text
        # without any markup. The previous implementation attempted to call a
        # non-existent ``plain`` attribute which raised ``AttributeError`` when
        # invoked. Using ``plain_text()`` returns the cleaned string as intended
        # and allows this utility to be used during merge operations.
        plain = parsed.plain_text()
        
        # Final cleanup
        plain = re.sub(r'\s+', ' ', plain)
        plain = re.sub(r'\s+([.,!?])', r'\1', plain)
        return plain.strip()
    
    @staticmethod
    def normalize_reference_text(ref_text: str) -> str:
        """Normalize reference text for deduplication."""
        # Convert to lowercase
        ref_text = ref_text.lower()
        
        # Remove extra whitespace
        ref_text = re.sub(r'\s+', ' ', ref_text.strip())
        
        # Normalize URLs
        ref_text = re.sub(r'https?://(www\.)?', 'https://', ref_text)

        return ref_text
