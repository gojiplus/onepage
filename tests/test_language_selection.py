"""Tests for language selection functionality."""

from unittest.mock import MagicMock, patch

from onepage.api import WikipediaClient, select_top_languages


class TestWikipediaClientGetArticleLength:
    """Test get_article_length method."""

    @patch("requests.Session.get")
    def test_get_article_length_success(self, mock_get):
        """Test getting article length successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": {
                "pages": {
                    "12345": {
                        "pageid": 12345,
                        "title": "Test Article",
                        "length": 5000,
                    }
                }
            }
        }
        mock_get.return_value = mock_response

        client = WikipediaClient()
        length = client.get_article_length("Test Article", "en")

        assert length == 5000

    @patch("requests.Session.get")
    def test_get_article_length_not_found(self, mock_get):
        """Test getting length for non-existent article returns 0."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": {"pages": {"-1": {"title": "Missing Article", "missing": True}}}
        }
        mock_get.return_value = mock_response

        client = WikipediaClient()
        length = client.get_article_length("Missing Article", "en")

        assert length == 0

    @patch("requests.Session.get")
    def test_get_article_length_missing_query(self, mock_get):
        """Test handling missing query in response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        client = WikipediaClient()
        length = client.get_article_length("Test", "en")

        assert length == 0


class TestSelectTopLanguages:
    """Test select_top_languages function."""

    @patch("onepage.api.WikipediaClient")
    @patch("onepage.api.WikidataClient")
    def test_select_top_languages_basic(self, mock_wikidata, mock_wikipedia):
        """Test selecting top languages by size."""
        mock_wikidata_instance = MagicMock()
        mock_wikidata_instance.get_sitelinks.return_value = {
            "en": "Test Article",
            "fr": "Article de test",
            "de": "Testartikel",
        }
        mock_wikidata.return_value = mock_wikidata_instance

        mock_wikipedia_instance = MagicMock()
        mock_wikipedia_instance.get_article_length.side_effect = [
            1000,
            3000,
            2000,
        ]
        mock_wikipedia.return_value = mock_wikipedia_instance

        result = select_top_languages("Q12345", top_n=2)

        assert "fr" in result
        assert "de" in result
        assert "en" in result

    @patch("onepage.api.WikipediaClient")
    @patch("onepage.api.WikidataClient")
    def test_select_top_languages_always_includes_english(
        self, mock_wikidata, mock_wikipedia
    ):
        """Test that English is always included."""
        mock_wikidata_instance = MagicMock()
        mock_wikidata_instance.get_sitelinks.return_value = {
            "en": "Test Article",
            "fr": "Article de test",
            "de": "Testartikel",
            "es": "Articulo de prueba",
        }
        mock_wikidata.return_value = mock_wikidata_instance

        mock_wikipedia_instance = MagicMock()
        mock_wikipedia_instance.get_article_length.side_effect = [
            100,
            3000,
            2000,
            1500,
        ]
        mock_wikipedia.return_value = mock_wikipedia_instance

        result = select_top_languages("Q12345", top_n=2)

        assert "en" in result

    @patch("onepage.api.WikipediaClient")
    @patch("onepage.api.WikidataClient")
    def test_select_top_languages_no_sitelinks(self, mock_wikidata, mock_wikipedia):
        """Test handling entity with no sitelinks."""
        mock_wikidata_instance = MagicMock()
        mock_wikidata_instance.get_sitelinks.return_value = {}
        mock_wikidata.return_value = mock_wikidata_instance

        result = select_top_languages("Q12345", top_n=2)

        assert result == ["en"]

    @patch("onepage.api.WikipediaClient")
    @patch("onepage.api.WikidataClient")
    def test_select_top_languages_custom_always_include(
        self, mock_wikidata, mock_wikipedia
    ):
        """Test custom always_include languages."""
        mock_wikidata_instance = MagicMock()
        mock_wikidata_instance.get_sitelinks.return_value = {
            "en": "Test Article",
            "fr": "Article de test",
            "hi": "Test",
        }
        mock_wikidata.return_value = mock_wikidata_instance

        mock_wikipedia_instance = MagicMock()
        mock_wikipedia_instance.get_article_length.side_effect = [3000, 2000, 100]
        mock_wikipedia.return_value = mock_wikipedia_instance

        result = select_top_languages("Q12345", top_n=1, always_include=["hi"])

        assert "en" in result
        assert "hi" in result
