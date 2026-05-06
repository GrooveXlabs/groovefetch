"""Tests for schema validation."""

import pytest
from pydantic import BaseModel, Field, ValidationError

from groovefetch.schema import Schema, ScrapedResult


class Product(BaseModel):
    name: str = Field(description="Product name")
    price: float = Field(description="Product price")
    in_stock: bool = Field(default=True)


class TestSchemaValidation:
    """Test schema validation functionality."""
    
    def test_validate_single_item(self) -> None:
        schema = Schema(Product)
        item = {"name": "Test Product", "price": "19.99"}
        
        result = schema.validate_single(item)
        assert result.name == "Test Product"
        assert result.price == 19.99
    
    def test_validate_list(self):
        schema = Schema(Product)
        data = [
            {"name": "Product A", "price": 10.0},
            {"name": "Product B", "price": 20.0},
        ]
        
        results = schema.validate(data)
        assert len(results) == 2
        assert results[0].name == "Product A"
        assert results[1].price == 20.0
    
    def test_coerce_string_to_number(self):
        schema = Schema(Product)
        data = [{"name": "Widget", "price": "$15.50"}]
        
        results = schema.validate(data)
        assert len(results) == 1
        assert results[0].price == 15.50
    
    def test_invalid_data_captured(self):
        schema = Schema(Product)
        data = [{"name": "Bad", "price": "not_a_price"}]
        
        results = schema.validate(data)
        assert len(results) == 0
        assert len(schema.last_errors) == 1
    
    def test_partial_validation(self):
        schema = Schema(Product)
        data = [
            {"name": "Good", "price": 10.0},
            {"name": "Bad", "price": "invalid"},
        ]
        
        results = schema.validate(data)
        assert len(results) == 1
        assert len(schema.last_errors) == 1


class TestScrapedResult:
    """Test ScrapedResult container."""
    
    def test_success_rate(self):
        result = ScrapedResult(
            url="https://example.com",
            raw_data=[{"a": 1}, {"b": 2}],
            validated=[Product(name="X", price=1.0)],
            schema_name="Product",
            errors=[],
        )
        assert result.success_rate == 0.5
    
    def test_is_valid(self):
        result = ScrapedResult(
            url="https://example.com",
            raw_data=[{"name": "X", "price": 1.0}],
            validated=[Product(name="X", price=1.0)],
            schema_name="Product",
            errors=[],
        )
        assert result.is_valid is True
    
    def test_to_json(self):
        result = ScrapedResult(
            url="https://example.com",
            raw_data=[{"name": "X", "price": 1.0}],
            validated=[Product(name="X", price=1.0)],
            schema_name="Product",
            errors=[],
        )
        json_str = result.to_json()
        assert '"name": "X"' in json_str
        assert '"price": 1.0' in json_str
