"""Anti-detection and fingerprint randomization for stealth scraping."""

import random
from typing import Dict, Optional, List
from dataclasses import dataclass


# Realistic viewport sizes
_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
]

# Realistic Chrome/Edge/Firefox user agents
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Accept-Language headers per region
_LOCALE_HEADERS = {
    "us": {"Accept-Language": "en-US,en;q=0.9"},
    "eu": {"Accept-Language": "en-GB,en;q=0.9,fr;q=0.8"},
    "asia": {"Accept-Language": "en;q=0.9,ja;q=0.8"},
}


@dataclass
class Fingerprint:
    """Browser fingerprint configuration."""
    user_agent: str
    viewport: Dict[str, int]
    headers: Dict[str, str]
    platform: str
    color_depth: int
    device_memory: int
    hardware_concurrency: int


class StealthProfile:
    """Generates and manages stealth browser profiles.
    
    Usage:
        profile = StealthProfile.random()
        print(profile.fingerprint.user_agent)
    """
    
    def __init__(self, fingerprint: Optional[Fingerprint] = None):
        self.fingerprint = fingerprint or self._generate_random()
    
    @classmethod
    def random(cls, region: str = "us") -> "StealthProfile":
        """Generate a random stealth profile.
        
        Args:
            region: Target region for locale settings
            
        Returns:
            StealthProfile instance
        """
        fp = cls._generate_random(region)
        return cls(fp)
    
    @classmethod
    def desktop_chrome(cls, region: str = "us") -> "StealthProfile":
        """Generate a consistent desktop Chrome profile."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        fp = Fingerprint(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": _LOCALE_HEADERS.get(region, _LOCALE_HEADERS["us"])["Accept-Language"],
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            },
            platform="Win32",
            color_depth=24,
            device_memory=8,
            hardware_concurrency=4,
        )
        return cls(fp)
    
    @staticmethod
    def _generate_random(region: str = "us") -> Fingerprint:
        """Generate a random but realistic fingerprint."""
        viewport = random.choice(_VIEWPORTS)
        ua = random.choice(_USER_AGENTS)
        locale = _LOCALE_HEADERS.get(region, _LOCALE_HEADERS["us"])
        
        platform = "Win32" if "Windows" in ua else "MacIntel" if "Mac" in ua else "Linux x86_64"
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": locale["Accept-Language"],
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
        return Fingerprint(
            user_agent=ua,
            viewport=viewport,
            headers=headers,
            platform=platform,
            color_depth=24,
            device_memory=random.choice([4, 8, 16]),
            hardware_concurrency=random.choice([2, 4, 8]),
        )
    
    async def apply_to_page(self, page) -> None:
        """Apply fingerprint to a Playwright page object.
        
        Args:
            page: Playwright page instance
        """
        fp = self.fingerprint
        
        # Set viewport
        await page.set_viewport_size(fp.viewport)
        
        # Override navigator properties
        await page.evaluate(f"""
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined
            }});
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{fp.platform}'
            }});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {fp.hardware_concurrency}
            }});
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {fp.device_memory}
            }});
        """)
        
        # Remove Playwright-specific properties
        await page.evaluate("""
            delete navigator.__proto__.webdriver;
            window.chrome = { runtime: {} };
        """)


class ProxyRotator:
    """Simple proxy rotation for distributed scraping.
    
    Usage:
        rotator = ProxyRotator(["https://proxy1:8080", "https://proxy2:8080"])
        proxy = rotator.next()
    """
    
    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self._index = 0
    
    def next(self) -> Optional[str]:
        """Get next proxy in rotation."""
        if not self.proxies:
            return None
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return proxy
    
    def random(self) -> Optional[str]:
        """Get random proxy."""
        if not self.proxies:
            return None
        return random.choice(self.proxies)
