"""Translation integrity, transport failures, and CLI regression tests."""

from email.utils import formatdate
from unittest.mock import Mock

import pytest
import requests
from click.testing import CliRunner

from wikifuse import translate
from wikifuse.cli import cli
from wikifuse.merge import TextMerger, merge_article
from wikifuse.models import Claim, Entity, Provenance


@pytest.fixture
def service(monkeypatch):
    monkeypatch.delenv("WIKIFUSE_TRANSLATE_URL", raising=False)
    monkeypatch.delenv("WIKIFUSE_TRANSLATE_API_KEY", raising=False)
    instance = translate.TranslationService()
    instance.min_request_interval = 0
    monkeypatch.setattr(instance.session, "post", Mock())
    monkeypatch.setattr(translate.time, "sleep", Mock())
    return instance


def response(text="Translated", status=200, headers=None):
    return Mock(
        status_code=status, headers=headers or {}, json=lambda: {"translatedText": text}
    )


@pytest.mark.parametrize(
    "text",
    [
        "Bonjour le monde. " * 100,
        "é" * 1201,
        "你好世界。" * 250,
        "A" * 500 + " B" * 501,
    ],
)
def test_long_translation_sends_every_character(service, text):
    service.session.post.side_effect = lambda url, data, timeout: response(data["q"])
    translated, confidence = service.translate_to_english(text, "fr")
    chunks = [call.kwargs["data"]["q"] for call in service.session.post.call_args_list]
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 500 for chunk in chunks)
    assert "".join(chunks) == text
    assert translated == " ".join(chunk.strip() for chunk in chunks)
    assert confidence is None


def test_short_foreign_text_is_translated_and_source_language_is_respected(service):
    service.session.post.return_value = response("at")
    assert service.translate_to_english("à", "fr") == ("at", None)
    assert service.session.post.call_args.kwargs["data"]["source"] == "fr"


def test_identity_translation_needs_no_service(service):
    assert service.translate_to_english("English text.", "en") == ("English text.", 1.0)
    assert service.translate_to_english("   ", "fr") == ("   ", 1.0)
    service.session.post.assert_not_called()


def test_cache_is_scoped_to_source_and_target_languages(service):
    service.session.post.side_effect = [
        response("English"),
        response("Deutsch"),
        response("Other"),
    ]
    assert service.translate("texte", "fr", "en") == ("English", None)
    assert service.translate("texte", "fr", "en") == ("English", None)
    assert service.translate("texte", "fr", "de") == ("Deutsch", None)
    assert service.translate("texte", "es", "en") == ("Other", None)
    assert service.session.post.call_count == 3


def test_second_chunk_failure_returns_no_partial_result_and_is_not_cached(service):
    text = "é" * 700
    service.session.post.side_effect = [response("First"), response(status=403)]
    with pytest.raises(translate.TranslationError, match="chunk 2.*HTTP 403"):
        service.translate_to_english(text, "fr")
    service.session.post.side_effect = [response("First"), response("Second")]
    assert service.translate_to_english(text, "fr") == ("First Second", None)
    assert service.session.post.call_count == 4


@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        {},
        {"translatedText": []},
        {"translatedText": 1},
        {"translatedText": " "},
    ],
)
def test_malformed_success_payload_is_an_explicit_error(service, payload):
    service.session.post.return_value = Mock(status_code=200, json=lambda: payload)
    with pytest.raises(translate.TranslationError, match="valid translatedText"):
        service.translate_to_english("Bonjour", "fr")
    assert service.session.post.call_count == 1
    assert not service.cache


def test_invalid_json_is_an_explicit_error(service):
    service.session.post.return_value = Mock(
        status_code=200, json=Mock(side_effect=ValueError("invalid JSON"))
    )
    with pytest.raises(translate.TranslationError, match="invalid JSON"):
        service.translate_to_english("Bonjour", "fr")
    assert not service.cache


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_http_failure_retries_then_succeeds(service, status):
    service.session.post.side_effect = [response(status=status), response("Hello")]
    assert service.translate_to_english("Bonjour", "fr") == ("Hello", None)
    assert service.session.post.call_count == 2
    translate.time.sleep.assert_called_once_with(1.0)


def test_retries_are_bounded_and_do_not_cache_failure(service):
    service.session.post.return_value = response(status=503)
    with pytest.raises(translate.TranslationError, match="HTTP 503"):
        service.translate_to_english("Bonjour", "fr")
    assert service.session.post.call_count == 3
    assert [call.args[0] for call in translate.time.sleep.call_args_list] == [1.0, 2.0]
    assert not service.cache


@pytest.mark.parametrize("error", [requests.Timeout, requests.ConnectionError])
def test_network_failures_retry_without_exposing_request_details(service, error):
    service.session.post.side_effect = error("sensitive request details")
    with pytest.raises(translate.TranslationError, match="after 3 attempts") as exc:
        service.translate_to_english("Bonjour", "fr")
    assert "sensitive" not in str(exc.value)
    assert service.session.post.call_count == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_http_errors_do_not_retry(service, status):
    service.session.post.return_value = response(status=status)
    with pytest.raises(translate.TranslationError, match=f"HTTP {status}"):
        service.translate_to_english("Bonjour", "fr")
    assert service.session.post.call_count == 1


@pytest.mark.parametrize(
    "header,expected",
    [("5", 5), ("999999", 30), ("-3", 0), ("nonsense", 1), ("nan", 1)],
)
def test_retry_after_is_validated_and_capped(service, header, expected):
    service.session.post.side_effect = [
        response(status=429, headers={"Retry-After": header}),
        response("Hello"),
    ]
    service.translate_to_english("Bonjour", "fr")
    translate.time.sleep.assert_called_once_with(expected)


def test_retry_after_http_date(service, monkeypatch):
    monkeypatch.setattr(translate.time, "time", lambda: 1_700_000_000)
    service.session.post.side_effect = [
        response(
            status=429, headers={"Retry-After": formatdate(1_700_000_012, usegmt=True)}
        ),
        response("Hello"),
    ]
    service.translate_to_english("Bonjour", "fr")
    translate.time.sleep.assert_called_once_with(12.0)


def test_endpoint_and_key_configuration(monkeypatch):
    monkeypatch.setenv("WIKIFUSE_TRANSLATE_URL", "https://translate.example/translate")
    monkeypatch.setenv("WIKIFUSE_TRANSLATE_API_KEY", "test-key")
    instance = translate.TranslationService()
    instance.session.post = Mock(return_value=response("Hello"))
    instance.translate_to_english("Bonjour", "fr")
    call = instance.session.post.call_args
    assert call.args[0] == "https://translate.example/translate"
    assert call.kwargs["data"]["api_key"] == "test-key"
    assert call.kwargs["timeout"] == 15


def test_claim_batch_failure_leaves_existing_translations_unchanged(service):
    claims = [
        Claim("a", lang="fr", text="Bonjour", text_en="old-a"),
        Claim("b", lang="fr", text="Bonsoir", text_en="old-b"),
    ]
    service.session.post.side_effect = [response("Hello"), response(status=403)]
    with pytest.raises(translate.TranslationError):
        service.translate_claims(claims)
    assert [claim.text_en for claim in claims] == ["old-a", "old-b"]


def test_translation_failure_propagates_from_text_merger(service):
    service.session.post.return_value = response(status=403)
    merger = TextMerger()
    merger.translator = service
    with pytest.raises(translate.TranslationError):
        merger.merge([("fr", {"Biographie": "Un texte assez long."})])


def test_short_and_unicode_headings_are_preserved(service):
    service.session.post.side_effect = [response("AI"), response("人工知能")]
    merger = TextMerger()
    merger.translator = service
    assert merger._normalize_heading("Intelligence artificielle", "fr", "en") == "AI"
    assert (
        merger._normalize_heading("Intelligence artificielle", "fr", "ja") == "人工知能"
    )
    assert service.session.post.call_args.kwargs["data"]["target"] == "ja"


def test_merge_translates_to_requested_target_and_preserves_citations(
    service, monkeypatch
):
    fetched = {
        "entity": Entity("Q1", {"en": "Example"}),
        "articles": {
            "en": {
                "wikitext": "Born in Paris.<ref>Birth source</ref>",
                "provenance": Provenance("enwiki", "Example", 123),
            }
        },
    }
    monkeypatch.setattr(
        "wikifuse.merge.ArticleFetcher.fetch_all", Mock(return_value=fetched)
    )
    monkeypatch.setattr("wikifuse.merge.TranslationService", lambda: service)
    service.session.post.return_value = response("Née à Paris.")
    ir = merge_article("Q1", ["en"], target_lang="fr", use_llm=False)
    claim = next(iter(ir.content.values()))
    assert claim.text == "Née à Paris."
    assert claim.lang == "fr"
    assert claim.text_en is None
    assert ir.references[claim.sources[0]].title == "Birth source"
    assert all(
        call.kwargs["data"]["target"] == "fr"
        for call in service.session.post.call_args_list
    )


def test_failed_merge_cli_does_not_overwrite_existing_output(
    service, monkeypatch, tmp_path
):
    fetched = {
        "entity": Entity("Q1", {"en": "Example"}),
        "articles": {
            "en": {
                "wikitext": "Born in Paris.",
                "provenance": Provenance("enwiki", "Example", 123),
            },
            "fr": {
                "wikitext": "Née à Paris.",
                "provenance": Provenance("frwiki", "Exemple", 456),
            },
        },
    }
    monkeypatch.setattr(
        "wikifuse.merge.ArticleFetcher.fetch_all", Mock(return_value=fetched)
    )
    monkeypatch.setattr("wikifuse.merge.TranslationService", lambda: service)
    service.session.post.return_value = response(status=403)
    out = tmp_path / "wikifuse.ir.json"
    out.write_text("previous output")
    result = CliRunner().invoke(
        cli,
        [
            "merge",
            "--qid",
            "Q1",
            "--languages",
            "en,fr",
            "--no-llm",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "Error: Translation" in result.output
    assert "WIKIFUSE_TRANSLATE_API_KEY" in result.output
    assert "Merged IR written" not in result.output
    assert out.read_text() == "previous output"
    assert not (tmp_path / "ATTRIBUTION.md").exists()


def test_failed_diff_cli_does_not_write_html(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "wikifuse.cli.compare_articles",
        Mock(side_effect=translate.TranslationError("Translation failed")),
    )
    result = CliRunner().invoke(
        cli,
        [
            "diff",
            "--qid",
            "Q1",
            "--compare",
            "en,fr",
            "--no-llm",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "Error: Translation failed" in result.output
    assert not (tmp_path / "diff.html").exists()


def test_lead_section_identifier_is_not_sent_for_translation(service):
    merger = TextMerger()
    merger.translator = service
    assert merger._normalize_heading("lead", "fr", "en") == "lead"
    service.session.post.assert_not_called()


@pytest.mark.parametrize(
    "url", ["", "file:///tmp/service", "https://", "http://[broken"]
)
def test_invalid_endpoint_is_a_clear_configuration_error(monkeypatch, url):
    monkeypatch.setenv("WIKIFUSE_TRANSLATE_URL", url)
    with pytest.raises(translate.TranslationError, match="HTTP\\(S\\)"):
        translate.TranslationService()
