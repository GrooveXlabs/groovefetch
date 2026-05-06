"""HTML parsing with auto-adaptation and structured extraction."""

from typing import List, Dict, Any, Optional, Type
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel
import re

from .schema import Schema


class ParsedDocument:
    """Represents a parsed HTML document with extraction capabilities."""
    
    def __init__(self, html: str, url: str = ""):
        self.html = html
        self.url = url
        self.soup = BeautifulSoup(html, "lxml")
        self._text_cache: Optional[str] = None
    
    @property
    def title(self) -> str:
        """Page title."""
        tag = self.soup.find("title")
        return tag.get_text(strip=True) if tag else ""
    
    @property
    def text(self) -> str:
        """Clean extracted text."""
        if self._text_cache is None:
            # Remove script and style elements
            for script in self.soup(["script", "style", "nav", "footer"]):
                script.decompose()
            self._text_cache = self.soup.get_text(separator="\n", strip=True)
        return self._text_cache
    
    def find_all(self, selector: str, **kwargs) -> List[Tag]:
        """Find all elements matching CSS selector."""
        return self.soup.select(selector)
    
    def find(self, selector: str, **kwargs) -> Optional[Tag]:
        """Find first element matching CSS selector."""
        results = self.soup.select(selector)
        return results[0] if results else None
    
    def extract_table(self, table_selector: str = "table") -> List[Dict[str, str]]:
        """Extract data from HTML tables.
        
        Args:
            table_selector: CSS selector for the table
            
        Returns:
            List of row dictionaries
        """
        table = self.soup.select_one(table_selector)
        if not table:
            return []
        
        headers = []
        header_row = table.find("thead")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
        
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(["th", "td"])]
        
        results = []
        rows = table.find_all("tr")
        start_idx = 1 if not table.find("thead") and rows else 0
        
        for row in rows[start_idx:]:
            cells = row.find_all(["td", "th"])
            if len(cells) == len(headers):
                row_data = {}
                for header, cell in zip(headers, cells):
                    row_data[header] = cell.get_text(strip=True)
                results.append(row_data)
        
        return results
    
    def extract_list(self, list_selector: str = "ul li, ol li") -> List[str]:
        """Extract text from list items.
        
        Args:
            list_selector: CSS selector for list items
            
        Returns:
            List of item texts
        """
        items = self.soup.select(list_selector)
        return [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
    
    def extract_links(self, selector: str = "a[href]") -> List[Dict[str, str]]:
        """Extract links from the page.
        
        Args:
            selector: CSS selector for link elements
            
        Returns:
            List of dicts with text and href
        """
        links = []
        for a in self.soup.select(selector):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if href and not href.startswith(("javascript:", "mailto:", "tel:")):
                links.append({"text": text, "url": href})
        return links
    
    def extract_by_schema(self, schema: Schema, container_selector: str = "") -> List[Dict[str, Any]]:
        """Extract data matching a Pydantic schema using heuristics.
        
        This uses intelligent heuristics to map HTML structure to schema fields.
        For production use, combine with LLM-based extraction.
        
        Args:
            schema: Schema to extract
            container_selector: CSS selector for container elements
            
        Returns:
            List of extracted dictionaries
        """
        json_schema = schema.to_json_schema()
        properties = json_schema.get("properties", {})
        
        results = []
        
        if container_selector:
            containers = self.soup.select(container_selector)
        else:
            # Auto-detect containers — look for repeated structures
            containers = self._detect_repeated_containers()
        
        for container in containers[:50]:  # Limit to prevent overload
            item = self._extract_item_from_container(container, properties)
            if item:
                results.append(item)
        
        return results
    
    def _detect_repeated_containers(self) -> List[Tag]:
        """Heuristic to detect repeated container elements."""
        # Common container patterns
        selectors = [
            "article", ".item", ".product", ".card", ".entry",
            "[class*='item']", "[class*='product']", "[class*='card']",
            ".search-result", ".listing", ".post"
        ]
        
        for selector in selectors:
            elements = self.soup.select(selector)
            if len(elements) >= 3:
                return elements
        
        # Fallback: look for divs with similar class patterns
        divs = self.soup.find_all("div")
        class_counts: Dict[str, List[Tag]] = {}
        for div in divs:
            classes = div.get("class", [])
            for cls in classes:
                class_counts.setdefault(cls, []).append(div)
        
        # Find most common class with multiple instances
        best = max(class_counts.items(), key=lambda x: len(x[1]) if len(x[1]) >= 3 else 0, default=(None, []))
        if best[0]:
            return best[1]
        
        return []
    
    def _extract_item_from_container(self, container: Tag, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract a single item from a container element."""
        item: Dict[str, Any] = {}
        
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "string")
            
            # Try to find matching element
            value = self._find_field_value(container, field_name, field_type)
            if value is not None:
                item[field_name] = value
        
        return item if item else None
    
    def _find_field_value(self, container: Tag, field_name: str, field_type: str) -> Any:
        """Find a field value within a container using name-based heuristics."""
        # Try selector-based matching
        selectors = [
            f"[class*='{field_name}']",
            f"[class*='{field_name.replace('_', '-')}']",
            f"[data-field='{field_name}']",
        ]
        
        for selector in selectors:
            el = container.select_one(selector)
            if el:
                return self._coerce_type(el.get_text(strip=True), field_type)
        
        # Try semantic HTML matching
        semantic_map = {
            "name": ["h1", "h2", "h3", ".title", "[class*='title']"],
            "price": [".price", "[class*='price']", "[class*='cost']"],
            "rating": [".rating", "[class*='rating']", "[class*='stars']"],
            "description": ["p", ".description", "[class*='desc']"],
            "image": ["img"],
            "url": ["a[href]"],
        }
        
        if field_name.lower() in semantic_map:
            for selector in semantic_map[field_name.lower()]:
                el = container.select_one(selector)
                if el:
                    if field_name == "image":
                        return el.get("src", "")
                    if field_name == "url":
                        return el.get("href", "")
                    return self._coerce_type(el.get_text(strip=True), field_type)
        
        return None
    
    def _coerce_type(self, value: str, field_type: str) -> Any:
        """Coerce a string value to the expected type."""
        if not value:
            return None
        
        if field_type == "integer":
            # Extract first number
            match = re.search(r'-?\d+', value.replace(",", ""))
            return int(match.group()) if match else None
        
        if field_type == "number":
            match = re.search(r'-?\d+\.?\d*', value.replace(",", ""))
            return float(match.group()) if match else None
        
        if field_type == "boolean":
            return value.lower() in ("true", "yes", "1", "in stock", "available")
        
        return value


class AccessibilitySnapshot:
    """Token-efficient accessibility tree snapshot of a page."""
    
    def __init__(self, title: str = "", text: str = "", elements: List[Dict] = None):
        self.title = title
        self.text = text
        self.elements = elements or []
    
    @property
    def token_estimate(self) -> int:
        """Rough estimate of token count (useful for LLM context limits)."""
        # Very rough: ~4 chars per token
        text_tokens = len(self.text) // 4
        element_tokens = sum(len(str(e)) for e in self.elements) // 4
        return text_tokens + element_tokens
    
    def to_text(self) -> str:
        """Convert to plain text representation."""
        lines = [f"# {self.title}", ""]
        lines.append(self.text)
        
        if self.elements:
            lines.append("")
            lines.append("## Interactive Elements")
            for el in self.elements:
                lines.append(f"- [{el.get('type', 'unknown')}] {el.get('text', '')} (ref: {el.get('ref', '')})")
        
        return "\n".join(lines)
