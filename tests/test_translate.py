"""Tests for translation service error handling and fallback."""

from onepage.translate import TranslationService


def test_libretranslate_invalid_json(monkeypatch, capsys):
    """LibreTranslate failure should return placeholder and log error."""
    service = TranslationService()

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("invalid JSON")

    def fake_post(url, data, timeout):
        return FakeResponse()

    # Ensure no actual HTTP request is made
    monkeypatch.setattr(service.session, "post", fake_post)

    result = service._translate_via_libre("Bonjour", "fr", "en")
    captured = capsys.readouterr()

    assert result == "[TRANSLATION UNAVAILABLE FROM FR]"
    assert "Translation failed" in captured.out


def test_translate_to_english_falls_back(monkeypatch):
    """Fallback to Google translation when LibreTranslate fails."""
    service = TranslationService()

    def fake_libre(text, source, target):
        return "[TRANSLATION UNAVAILABLE FROM FR]"

    def fake_google(text, source, target):
        assert text == "Bonjour"
        assert source == "fr"
        assert target == "en"
        return "Hello"

    monkeypatch.setattr(service, "_translate_via_libre", fake_libre)
    monkeypatch.setattr(service, "_translate_via_google", fake_google)

    translated, confidence = service.translate_to_english("Bonjour", "fr")

    assert translated == "Hello"
    assert confidence > 0
