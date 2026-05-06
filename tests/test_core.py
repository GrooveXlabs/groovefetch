"""Tests for GrooveFetch core engine."""

import pytest
from pydantic import BaseModel, Field

from groovefetch.core import GrooveFetch
from groovefetch.schema import Schema
from groovefetch.utils import validate_url


class TestURLValidation:
    """Test URL validation and security."""
    
    def test_valid_url(self) -> None:
        assert validate_url("https://example.com") == "https://example.com"
    
    def test_localhost_blocked(self) -> None:
        with pytest.raises(ValueError):
            validate_url("http://localhost:8080")
    
    def test_private_ip_blocked(self):
        with pytest.raises(ValueError):
            validate_url("http://192.168.1.1")
    
    def test_invalid_scheme_blocked(self):
        with pytest.raises(ValueError):
            validate_url("file:///etc/passwd")


class TestSchemaValidation:
    """Test schema validation layer."""
    
    def test_schema_validation(self):
        class Product(BaseModel):
            name: str
            price: float
        
        schema = Schema(Product)
        data = [
            {"name": "Widget", "price": 19.99},
            {"name": "Gadget", "price": 29.99},
        ]
        
        validated = schema.validate(data)
        assert len(validated) == 2
        assert validated[0].name == "Widget"
        assert validated[0].price == 19.99
    
    def test_schema_validation_errors(self):
        class Product(BaseModel):
            name: str
            price: float
        
        schema = Schema(Product)
        data = [
            {"name": "Widget", "price": "not_a_number"},
        ]
        
        validated = schema.validate(data)
        assert len(validated) == 0
        assert len(schema.last_errors) == 1


class TestAdaptiveLearning:
    """Test adaptive learning engine."""
    
    def test_profile_creation(self):
        from groovefetch.adaptive import DomainProfile
        
        profile = DomainProfile(domain="example.com")
        assert profile.domain == "example.com"
        assert profile.success_rate == 0.0
    
    def test_learning_records(self, tmp_path):
        from groovefetch.adaptive import AdaptiveLearner
        
        learner = AdaptiveLearner(storage_path=str(tmp_path / "profiles.json"))
        learner.record("example.com", success=True, delay=1.5, used_stealth=False)
        learner.record("example.com", success=True, delay=2.0, used_stealth=False)
        
        profile = learner.get_profile("example.com")
        assert profile.request_count == 2
        assert profile.success_rate == 1.0


class TestStealthProfile:
    """Test stealth fingerprint generation."""
    
    def test_random_profile(self):
        from groovefetch.stealth import StealthProfile
        
        profile = StealthProfile.random()
        assert profile.fingerprint.user_agent
        assert profile.fingerprint.viewport["width"] > 0
    
    def test_desktop_chrome_profile(self):
        from groovefetch.stealth import StealthProfile
        
        profile = StealthProfile.desktop_chrome()
        assert "Chrome" in profile.fingerprint.user_agent
        assert profile.fingerprint.viewport["width"] == 1920


@pytest.mark.asyncio
class TestGrooveFetch:
    """Integration tests for main engine."""
    
    async def test_scrape_with_http(self):
        """Test basic HTTP scraping."""
        gf = GrooveFetch(learn=False)
        
        async with gf:
            # Use a simple test page
            result = await gf.scrape(
                "https://httpbin.org/html",
                mode="http",
            )
            
            assert result.url == "https://httpbin.org/html"
            assert result.metadata["mode"] == "http"
            assert result.html != ""
    
    async def test_snapshot(self):
        """Test accessibility snapshot."""
        gf = GrooveFetch(learn=False)
        
        async with gf:
            snapshot = await gf.snapshot("https://httpbin.org/html")
            assert "error" not in snapshot or snapshot.get("text")
