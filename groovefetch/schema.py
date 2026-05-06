"""Schema validation layer for scraped data using Pydantic."""

import re
from typing import Type, List, Any, Optional, Dict
from pydantic import BaseModel, ValidationError
import json


class Schema:
    """Wraps a Pydantic model for scraping validation.
    
    Usage:
        class Product(BaseModel):
            name: str
            price: float
        
        schema = Schema(Product)
        validated = schema.validate([{"name": "X", "price": 10.0}])
    """
    
    def __init__(self, model: Type[BaseModel]):
        self.model = model
        self.name = model.__name__
    
    def validate(self, data: List[Dict[str, Any]]) -> List[BaseModel]:
        """Validate raw scraped data against the schema.
        
        Args:
            data: List of dictionaries from scraping
            
        Returns:
            List of validated Pydantic model instances
            
        Raises:
            ValidationError: If data doesn't match schema
        """
        results = []
        errors = []
        
        for idx, item in enumerate(data):
            try:
                # Coerce common types
                cleaned = self._coerce_item(item)
                results.append(self.model(**cleaned))
            except ValidationError as e:
                errors.append({"index": idx, "item": item, "errors": e.errors()})
        
        if errors:
            # Return what we can, log errors
            self._last_errors = errors
        else:
            self._last_errors = []
        
        return results
    
    def validate_single(self, data: Dict[str, Any]) -> BaseModel:
        """Validate a single item.
        
        Args:
            data: Dictionary to validate
            
        Returns:
            Validated model instance
        """
        cleaned = self._coerce_item(data)
        return self.model(**cleaned)
    
    @property
    def last_errors(self) -> List[Dict]:
        """Return validation errors from last validate() call."""
        return getattr(self, '_last_errors', [])
    
    def _coerce_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce common scraped types to match schema expectations."""
        import re
        cleaned = dict(item)
        
        for key, val in cleaned.items():
            if isinstance(val, str):
                val = val.strip()
                # Strip currency symbols for numeric fields
                val = re.sub(r'^[\$€£¥]\s*', '', val)
                # Remove thousands separators
                val = val.replace(',', '')
                cleaned[key] = val
        
        return cleaned
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Export as JSON Schema for agent tool definitions."""
        return self.model.model_json_schema()


class ScrapedResult:
    """Container for scrape results with validation metadata."""
    
    def __init__(
        self,
        url: str,
        raw_data: List[Dict[str, Any]],
        validated: List[BaseModel],
        schema_name: str,
        errors: List[Dict],
        html: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.url = url
        self.raw_data = raw_data
        self.validated = validated
        self.schema_name = schema_name
        self.errors = errors
        self.html = html
        self.metadata = metadata or {}
    
    @property
    def success_rate(self) -> float:
        """Ratio of successfully validated items."""
        total = len(self.raw_data)
        if total == 0:
            return 0.0
        return len(self.validated) / total
    
    @property
    def is_valid(self) -> bool:
        """Whether all items validated successfully."""
        return len(self.errors) == 0 and len(self.validated) > 0
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """Export validated data as list of dictionaries."""
        return [item.model_dump() for item in self.validated]
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Export validated data as JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
