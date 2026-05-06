"""Unified fetchers — HTTP and Stealth browser in one interface."""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

import httpx
from playwright.async_api import async_playwright, Page, Browser

from .utils import validate_url, redact_secrets, domain_from_url
from .stealth import StealthProfile, ProxyRotator
from .parser import ParsedDocument, AccessibilitySnapshot


@dataclass
class FetchResult:
    """Standard result from any fetcher."""
    url: str
    status: int
    html: str
    headers: Dict[str, str]
    duration: float
    mode: str  # 'http' or 'stealth'
    parsed: Optional[ParsedDocument] = None
    snapshot: Optional[AccessibilitySnapshot] = None
    error: Optional[str] = None


class HTTPFetcher:
    """Fast HTTP fetcher with retry logic and header rotation.
    
    Usage:
        fetcher = HTTPFetcher()
        result = await fetcher.fetch("https://example.com")
        print(result.parsed.title)
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        follow_redirects: bool = True,
        proxy: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        self.proxy = proxy
        self.default_headers = headers or {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        transport = httpx.AsyncHTTPTransport(limits=limits)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=self.follow_redirects,
            headers=self.default_headers,
            transport=transport,
        )
        return self
    
    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def fetch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> FetchResult:
        """Fetch a URL via HTTP.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            retry_count: Number of retries on failure
            retry_delay: Base delay between retries
            
        Returns:
            FetchResult with parsed document
        """
        url = validate_url(url)
        start = time.time()
        
        merged_headers = {**self.default_headers, **(headers or {})}
        
        for attempt in range(retry_count + 1):
            try:
                client = self._client or httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=self.follow_redirects,
                )
                
                response = await client.get(url, headers=merged_headers)
                duration = time.time() - start
                
                parsed = ParsedDocument(response.text, url)
                
                return FetchResult(
                    url=str(response.url),
                    status=response.status_code,
                    html=response.text,
                    headers=dict(response.headers),
                    duration=duration,
                    mode="http",
                    parsed=parsed,
                )
                
            except Exception as e:
                if attempt < retry_count:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                
                duration = time.time() - start
                return FetchResult(
                    url=url,
                    status=0,
                    html="",
                    headers={},
                    duration=duration,
                    mode="http",
                    error=redact_secrets(str(e)),
                )
        
        # Should never reach here
        return FetchResult(url=url, status=0, html="", headers={}, duration=0, mode="http")


class StealthFetcher:
    """Stealth browser fetcher using Playwright with anti-detection.
    
    Usage:
        fetcher = StealthFetcher()
        result = await fetcher.fetch("https://protected-site.com")
        print(result.snapshot.text)
    """
    
    def __init__(
        self,
        headless: bool = True,
        profile: Optional[StealthProfile] = None,
        proxy: Optional[str] = None,
        extra_args: Optional[list] = None,
    ):
        self.headless = headless
        self.profile = profile or StealthProfile.random()
        self.proxy = proxy
        self.extra_args = extra_args or [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        self._playwright = None
        self._browser: Optional[Browser] = None
    
    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        
        browser_args = {
            "headless": self.headless,
            "args": self.extra_args,
        }
        
        if self.proxy:
            browser_args["proxy"] = {"server": self.proxy}
        
        self._browser = await self._playwright.chromium.launch(**browser_args)
        return self
    
    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    async def fetch(
        self,
        url: str,
        wait_for: Optional[str] = None,
        wait_timeout: float = 10.0,
    ) -> FetchResult:
        """Fetch a URL via stealth browser.
        
        Args:
            url: URL to fetch
            wait_for: CSS selector to wait for
            wait_timeout: Max time to wait for selector
            
        Returns:
            FetchResult with accessibility snapshot
        """
        url = validate_url(url)
        start = time.time()
        
        try:
            context = await self._browser.new_context(
                user_agent=self.profile.fingerprint.user_agent,
                viewport=self.profile.fingerprint.viewport,
                extra_http_headers=self.profile.fingerprint.headers,
            )
            
            page = await context.new_page()
            self.profile.apply_to_page(page)
            
            response = await page.goto(url, wait_until="networkidle")
            
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=wait_timeout * 1000)
            
            html = await page.content()
            title = await page.title()
            
            # Build accessibility snapshot
            snapshot = await self._build_snapshot(page, title)
            
            await context.close()
            
            duration = time.time() - start
            parsed = ParsedDocument(html, url)
            
            return FetchResult(
                url=url,
                status=response.status if response else 0,
                html=html,
                headers={},
                duration=duration,
                mode="stealth",
                parsed=parsed,
                snapshot=snapshot,
            )
            
        except Exception as e:
            duration = time.time() - start
            return FetchResult(
                url=url,
                status=0,
                html="",
                headers={},
                duration=duration,
                mode="stealth",
                error=redact_secrets(str(e)),
            )
    
    async def snapshot(self, url: str) -> AccessibilitySnapshot:
        """Get accessibility snapshot only (fast, token-efficient).
        
        Args:
            url: URL to snapshot
            
        Returns:
            AccessibilitySnapshot
        """
        result = await self.fetch(url)
        return result.snapshot or AccessibilitySnapshot()
    
    async def _build_snapshot(self, page: Page, title: str) -> AccessibilitySnapshot:
        """Build accessibility snapshot from page."""
        # Extract main text content
        text = await page.evaluate("""
            () => {
                const main = document.querySelector('main') || document.body;
                const clone = main.cloneNode(true);
                // Remove hidden elements
                clone.querySelectorAll('script, style, nav, footer, [aria-hidden="true"]')
                    .forEach(el => el.remove());
                return clone.innerText || '';
            }
        """)
        
        # Extract interactive elements
        elements = await page.evaluate("""
            () => {
                const interactive = document.querySelectorAll(
                    'a, button, input, select, textarea, [role="button"], [role="link"]'
                );
                return Array.from(interactive).slice(0, 100).map((el, i) => ({
                    ref: `e${i}`,
                    type: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || el.placeholder || '').slice(0, 100),
                    role: el.getAttribute('role') || '',
                }));
            }
        """)
        
        return AccessibilitySnapshot(
            title=title,
            text=text[:5000],  # Limit text length
            elements=elements,
        )
