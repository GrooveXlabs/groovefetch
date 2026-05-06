"""Main GrooveFetch engine — ties everything together."""

import asyncio
import time
from typing import Type, Optional, Dict, Any, List
from pydantic import BaseModel

from .utils import validate_url, domain_from_url
from .schema import Schema, ScrapedResult
from .parser import ParsedDocument
from .fetchers import HTTPFetcher, StealthFetcher, FetchResult
from .adaptive import AdaptiveLearner
from .stealth import StealthProfile


class GrooveFetch:
    """Main scraping engine with adaptive learning and schema validation.
    
    Usage:
        gf = GrooveFetch()
        result = await gf.scrape(
            "https://example.com",
            schema=MyPydanticModel,
            mode="auto"
        )
        print(result.validated)
    """
    
    def __init__(
        self,
        learn: bool = True,
        default_mode: str = "auto",
        storage_path: Optional[str] = None,
    ):
        self.learn = learn
        self.default_mode = default_mode
        self.learner = AdaptiveLearner(storage_path)
        self._http: Optional[HTTPFetcher] = None
        self._stealth: Optional[StealthFetcher] = None
    
    async def __aenter__(self):
        self._http = HTTPFetcher()
        self._stealth = StealthFetcher()
        await self._http.__aenter__()
        await self._stealth.__aenter__()
        return self
    
    async def __aexit__(self, *args):
        if self._http:
            await self._http.__aexit__(*args)
            self._http = None
        if self._stealth:
            await self._stealth.__aexit__(*args)
            self._stealth = None
    
    async def scrape(
        self,
        url: str,
        schema: Optional[Type[BaseModel]] = None,
        mode: Optional[str] = None,
        container_selector: str = "",
        wait_for: Optional[str] = None,
    ) -> ScrapedResult:
        """Scrape a URL with automatic mode selection and validation.
        
        Args:
            url: URL to scrape
            schema: Pydantic model for validation
            mode: 'http', 'stealth', or 'auto'
            container_selector: CSS selector for item containers
            wait_for: CSS selector to wait for (stealth mode)
            
        Returns:
            ScrapedResult with validated data
        """
        url = validate_url(url)
        domain = domain_from_url(url)
        mode = mode or self.default_mode
        
        # Determine fetch mode
        if mode == "auto":
            mode = self._choose_mode(domain)
        
        # Get recommended delay
        delay = self.learner.recommend_delay(domain) if self.learn else 1.0
        await asyncio.sleep(delay)
        
        # Fetch
        start = time.time()
        result = await self._fetch(url, mode, wait_for)
        fetch_duration = time.time() - start
        
        # Extract data
        raw_data = []
        if result.parsed:
            if schema:
                schema_wrapper = Schema(schema)
                raw_data = result.parsed.extract_by_schema(
                    schema_wrapper, container_selector
                )
            else:
                # Default: extract links and text
                raw_data = result.parsed.extract_links()
        
        # Validate
        validated = []
        errors = []
        if schema and raw_data:
            schema_wrapper = Schema(schema)
            validated = schema_wrapper.validate(raw_data)
            errors = schema_wrapper.last_errors
        
        # Record learning
        if self.learn:
            self.learner.record(
                domain=domain,
                success=result.error is None and result.status < 400,
                delay=delay,
                used_stealth=(mode == "stealth"),
            )
        
        return ScrapedResult(
            url=url,
            raw_data=raw_data,
            validated=validated,
            schema_name=schema.__name__ if schema else "",
            errors=errors,
            html=result.html,
            metadata={
                "mode": mode,
                "status": result.status,
                "duration": fetch_duration,
                "delay_used": delay,
            }
        )
    
    async def snapshot(self, url: str) -> Dict[str, Any]:
        """Get token-efficient accessibility snapshot.
        
        Args:
            url: URL to snapshot
            
        Returns:
            Snapshot dictionary with text and elements
        """
        url = validate_url(url)
        
        result = await self._stealth.fetch(url)
        
        if result.snapshot:
            return {
                "title": result.snapshot.title,
                "text": result.snapshot.text,
                "elements": result.snapshot.elements,
                "token_estimate": result.snapshot.token_estimate,
                "url": result.url,
            }
        
        return {"error": result.error or "Failed to capture snapshot"}
    
    async def crawl(
        self,
        start_url: str,
        max_pages: int = 10,
        same_domain: bool = True,
        depth: int = 2,
    ) -> List[FetchResult]:
        """Simple breadth-first crawler.
        
        Args:
            start_url: Starting URL
            max_pages: Maximum pages to fetch
            same_domain: Whether to stay on same domain
            depth: Maximum crawl depth
            
        Returns:
            List of fetch results
        """
        start_url = validate_url(start_url)
        start_domain = domain_from_url(start_url)
        
        visited = set()
        queue = [(start_url, 0)]
        results = []
        
        while queue and len(results) < max_pages:
            url, current_depth = queue.pop(0)
            
            if url in visited or current_depth > depth:
                continue
            
            visited.add(url)
            
            try:
                result = await self._fetch(url, "http")
                results.append(result)
                
                if current_depth < depth and result.parsed:
                    links = result.parsed.extract_links()
                    for link in links:
                        next_url = link["url"]
                        if same_domain and domain_from_url(next_url) != start_domain:
                            continue
                        if next_url not in visited:
                            queue.append((next_url, current_depth + 1))
                            
            except Exception:
                continue
        
        return results
    
    def _choose_mode(self, domain: str) -> str:
        """Choose HTTP vs Stealth based on learned profile."""
        if not self.learn:
            return "http"
        
        profile = self.learner.get_profile(domain)
        
        # If we've failed multiple times, try stealth
        if profile.request_count >= 2 and profile.success_rate < 0.5:
            return "stealth"
        
        # If profile says stealth is required
        if self.learner.should_use_stealth(domain):
            return "stealth"
        
        return "http"
    
    async def _fetch(
        self,
        url: str,
        mode: str,
        wait_for: Optional[str] = None,
    ) -> FetchResult:
        """Internal fetch dispatcher."""
        if mode == "stealth":
            return await self._stealth.fetch(url, wait_for=wait_for)
        else:
            return await self._http.fetch(url)
    
    async def export_to_chroma(
        self,
        result: ScrapedResult,
        collection: str = "default",
        embedding_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export validated results to ChromaDB for RAG.
        
        Requires: pip install groovefetch[rag]
        
        Args:
            result: ScrapedResult to export
            collection: ChromaDB collection name
            embedding_model: Sentence transformer model name
            
        Returns:
            Export metadata
        """
        try:
            from .rag import ChromaExporter
        except ImportError:
            raise ImportError(
                "RAG support requires: pip install groovefetch[rag]"
            )
        
        exporter = ChromaExporter()
        return await exporter.export(result, collection, embedding_model)
