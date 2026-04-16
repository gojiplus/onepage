"""Tests for LLM service."""

from unittest.mock import MagicMock, patch

import pytest

from wikifuse.llm import LLMService, MockLLMService


class TestMockLLMService:
    """Test the mock LLM service used for testing."""

    def test_merge_sections_empty(self):
        """Test merging empty sections list."""
        mock = MockLLMService()
        result = mock.merge_sections([], "Test Entity", "Introduction")
        assert result == ""

    def test_merge_sections_single(self):
        """Test merging single section returns its content."""
        mock = MockLLMService()
        sections = [("enwiki", "en", "This is the content.")]
        result = mock.merge_sections(sections, "Test Entity", "Introduction")
        assert result == "This is the content."

    def test_merge_sections_multiple(self):
        """Test merging multiple sections concatenates content."""
        mock = MockLLMService()
        sections = [
            ("enwiki", "en", "First content."),
            ("frwiki", "fr", "Second content."),
        ]
        result = mock.merge_sections(sections, "Test Entity", "Introduction")
        assert result == "First content. Second content."


class TestLLMService:
    """Test the real LLM service."""

    def test_init_without_api_key_raises(self):
        """Test that initializing without API key raises error."""
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(ValueError, match="OpenAI API key required"),
        ):
            LLMService()

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch("wikifuse.llm.OpenAI") as mock_openai:
            service = LLMService(api_key="test-key")
            assert service.api_key == "test-key"
            assert service.model == "gpt-4o-mini"
            assert service.provider == "openai"
            mock_openai.assert_called_once_with(api_key="test-key")

    def test_init_with_env_api_key(self):
        """Test initialization reads API key from environment."""
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "env-test-key"}),
            patch("wikifuse.llm.OpenAI") as mock_openai,
        ):
            service = LLMService()
            assert service.api_key == "env-test-key"
            mock_openai.assert_called_once_with(api_key="env-test-key")

    def test_init_unsupported_provider(self):
        """Test that unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMService(api_key="test-key", provider="unknown")

    def test_merge_sections_empty(self):
        """Test merging empty sections list."""
        with patch("wikifuse.llm.OpenAI"):
            service = LLMService(api_key="test-key")
            result = service.merge_sections([], "Test Entity", "Introduction")
            assert result == ""

    def test_merge_sections_single_returns_content(self):
        """Test merging single section returns its content without LLM call."""
        with patch("wikifuse.llm.OpenAI"):
            service = LLMService(api_key="test-key")
            sections = [("enwiki", "en", "Single section content.")]
            result = service.merge_sections(sections, "Test Entity", "Introduction")
            assert result == "Single section content."

    def test_merge_sections_multiple_calls_llm(self):
        """Test merging multiple sections calls the LLM."""
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Merged content from LLM."
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        with patch("wikifuse.llm.OpenAI", mock_openai):
            service = LLMService(api_key="test-key")
            sections = [
                ("enwiki", "en", "English content."),
                ("frwiki", "fr", "French content."),
            ]
            result = service.merge_sections(sections, "Test Entity", "Career")
            assert result == "Merged content from LLM."

    def test_build_merge_prompt(self):
        """Test prompt construction."""
        with patch("wikifuse.llm.OpenAI"):
            service = LLMService(api_key="test-key")
            sections = [
                ("enwiki", "en", "English content."),
                ("frwiki", "fr", "French content."),
            ]
            prompt = service._build_merge_prompt(sections, "Test Entity", "Career")
            assert "Test Entity" in prompt
            assert "Career" in prompt
            assert "English content." in prompt
            assert "French content." in prompt
            assert "Source 1 (enwiki)" in prompt
            assert "Source 2 (frwiki (translated to English))" in prompt
