"""Translation service integration for cross-lingual alignment."""

import math
import os
import re
import time
from contextlib import suppress
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests
import wikitextparser as wtp

from .models import Claim


class TranslationError(RuntimeError):
    """A translation could not be completed without losing source content."""


class TranslationService:
    """Translate complete inputs using a configurable LibreTranslate endpoint."""

    def __init__(self, url: str | None = None, api_key: str | None = None):
        self.url = (
            url
            if url is not None
            else os.environ.get(
                "WIKIFUSE_TRANSLATE_URL", "https://libretranslate.com/translate"
            )
        )
        try:
            endpoint = urlsplit(self.url)
            valid_endpoint = endpoint.scheme in {"http", "https"} and bool(
                endpoint.hostname
            )
        except ValueError:
            valid_endpoint = False
        if not valid_endpoint:
            raise TranslationError(
                "WIKIFUSE_TRANSLATE_URL must be an HTTP(S) translation endpoint."
            )
        self.api_key = (
            api_key
            if api_key is not None
            else os.environ.get("WIKIFUSE_TRANSLATE_API_KEY")
        )
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "wikifuse/0.1.0 (https://github.com/gojiplus/wikifuse)"}
        )
        self.last_request_time = 0.0
        self.min_request_interval = 0.1
        self.cache: dict[tuple[str, str, str], tuple[str, float | None]] = {}

    def translate_to_english(
        self, text: str, source_lang: str
    ) -> tuple[str, float | None]:
        """Translate the complete text, raising TranslationError on failure.

        Successful translations have no estimated confidence; unchanged English
        text has confidence 1.0. Failures are never cached.
        """
        return self.translate(text, source_lang, "en")

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> tuple[str, float | None]:
        """Translate complete text to the requested language or raise TranslationError."""
        if source_lang == target_lang or not text.strip():
            return text, 1.0
        cache_key = (text, source_lang, target_lang)
        if cache_key not in self.cache:
            translated = self._translate_via_libre(text, source_lang, target_lang)
            self.cache[cache_key] = (translated, None)
        return self.cache[cache_key]

    @staticmethod
    def _chunks(text: str) -> list[str]:
        chunks = []
        while len(text) > 500:
            boundaries = list(re.finditer(r"\s+", text[:500]))
            end = boundaries[-1].end() if boundaries else 500
            chunks.append(text[:end])
            text = text[end:]
        if text:
            chunks.append(text)
        return chunks

    def _translate_via_libre(self, text: str, source: str, target: str) -> str:
        """Translate every chunk, returning no partial result if any chunk fails."""
        if source == target or not text.strip():
            return text
        translated = []
        for index, chunk in enumerate(self._chunks(text), 1):
            if not chunk.strip():
                continue
            try:
                translated.append(self._request_chunk(chunk, source, target))
            except TranslationError as error:
                raise TranslationError(
                    f"Translation from {source} to {target} failed at chunk {index}: {error}"
                ) from error
        return " ".join(translated)

    @staticmethod
    def _retry_delay(header: str | None, attempt: int) -> float:
        delay = float(2**attempt)
        if header:
            try:
                delay = float(header)
            except ValueError:
                with suppress(TypeError, ValueError, OverflowError):
                    delay = parsedate_to_datetime(header).timestamp() - time.time()
        return min(30.0, max(0.0, delay)) if math.isfinite(delay) else float(2**attempt)

    def _request_chunk(self, text: str, source: str, target: str) -> str:
        data = {"q": text, "source": source, "target": target, "format": "text"}
        if self.api_key:
            data["api_key"] = self.api_key
        for attempt in range(3):
            wait = self.min_request_interval - (
                time.monotonic() - self.last_request_time
            )
            if wait > 0:
                time.sleep(wait)
            self.last_request_time = time.monotonic()
            try:
                response = self.session.post(self.url, data=data, timeout=15)
            except (requests.Timeout, requests.ConnectionError):
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise TranslationError(
                    "Translation service timed out or could not be reached after 3 attempts."
                ) from None
            except requests.RequestException:
                raise TranslationError("Translation request failed.") from None
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(
                    self._retry_delay(response.headers.get("Retry-After"), attempt)
                )
                continue
            if response.status_code != 200:
                raise TranslationError(
                    f"Translation service returned HTTP {response.status_code}. "
                    "Check WIKIFUSE_TRANSLATE_URL and WIKIFUSE_TRANSLATE_API_KEY."
                )
            try:
                result = response.json()
            except ValueError:
                raise TranslationError(
                    "Translation service returned invalid JSON."
                ) from None
            translated = (
                result.get("translatedText") if isinstance(result, dict) else None
            )
            if not isinstance(translated, str) or not translated.strip():
                raise TranslationError(
                    "Translation service returned no valid translatedText string."
                )
            return translated.strip()
        raise TranslationError("Translation retries exhausted.")

    def translate_claims(self, claims: list[Claim]) -> list[Claim]:
        """Translate all claims before updating any claim's English text."""
        results = [
            self.translate_to_english(claim.text, claim.lang) for claim in claims
        ]
        for claim, (text, confidence) in zip(claims, results, strict=True):
            claim.text_en = text
            claim.confidence = confidence
        return claims

    def batch_translate(
        self, texts: list[str], source_lang: str, target_lang: str = "en"
    ) -> list[tuple[str, float | None]]:
        """Translate complete inputs, raising if any input cannot be translated."""
        return [self.translate(text, source_lang, target_lang) for text in texts]


class TextCleaner:
    """Clean and normalize text content."""

    @staticmethod
    def clean_sentence(text: str) -> str:
        """Clean a sentence for processing."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text.strip())

        # Remove citation needed markers
        text = re.sub(r"\[citation needed\]", "", text, flags=re.IGNORECASE)

        # Remove disambiguation markers
        text = re.sub(r"\s*\(disambiguation\)", "", text, flags=re.IGNORECASE)

        # Normalize quotation marks
        text = re.sub(r'[""' "]", '"', text)

        return text

    @staticmethod
    def extract_plain_text(wikitext: str) -> str:
        """Extract plain text from wikitext, removing all markup."""
        parsed = wtp.parse(wikitext)

        # Remove templates
        # ``wikitextparser`` invalidates indices of later nodes when earlier
        # ones are mutated.  Iterate over copies of the template/tag lists so
        # that we can safely mutate the original parse tree without hitting
        # ``DeadIndexError``.
        for template in reversed(list(parsed.templates)):
            template.string = ""

        # Remove references
        for tag in reversed(list(parsed.get_tags())):
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
        plain = re.sub(r"\s+", " ", plain)
        plain = re.sub(r"\s+([.,!?])", r"\1", plain)
        return plain.strip()

    @staticmethod
    def normalize_reference_text(ref_text: str) -> str:
        """Normalize reference text for deduplication."""
        # Convert to lowercase
        ref_text = ref_text.lower()

        # Remove extra whitespace
        ref_text = re.sub(r"\s+", " ", ref_text.strip())

        # Normalize URLs
        ref_text = re.sub(r"https?://(www\.)?", "https://", ref_text)

        return ref_text
