"""Tests for API clients."""

import pytest
from unittest.mock import Mock, patch

from onepage.api import WikidataClient, WikipediaClient


class TestWikidataClient:
    """Test Wikidata API client."""
    
    def test_init(self):
        """Test client initialization."""
        client = WikidataClient()
        assert client.base_url == "https://www.wikidata.org/w/api.php"
        assert "onepage" in client.session.headers["User-Agent"]
    
    @patch('requests.Session.get')
    def test_get_sitelinks(self, mock_get):
        """Test getting sitelinks for an entity."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "entities": {
                "Q1058": {
                    "sitelinks": {
                        "enwiki": {"title": "Narendra Modi"},
                        "hiwiki": {"title": "नरेन्द्र मोदी"},
                    }
                }
            }
        }
        mock_get.return_value = mock_response
        
        client = WikidataClient()
        sitelinks = client.get_sitelinks("Q1058", ["en", "hi"])
        
        assert sitelinks["en"] == "Narendra Modi"
        assert sitelinks["hi"] == "नरेन्द्र मोदी"
    
    def test_get_sitelinks_entity_not_found(self):
        """Test error handling for non-existent entity."""
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"entities": {}}
            mock_get.return_value = mock_response
            
            client = WikidataClient()
            
            with pytest.raises(ValueError, match="Entity Q999999 not found"):
                client.get_sitelinks("Q999999")


class TestWikipediaClient:
    """Test Wikipedia API client."""
    
    def test_init(self):
        """Test client initialization."""
        client = WikipediaClient()
        assert "onepage" in client.session.headers["User-Agent"]
    
    def test_get_api_url(self):
        """Test API URL generation."""
        client = WikipediaClient()
        assert client._get_api_url("en") == "https://en.wikipedia.org/w/api.php"
        assert client._get_api_url("hi") == "https://hi.wikipedia.org/w/api.php"