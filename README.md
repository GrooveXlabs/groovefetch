# 🌐 GrooveFetch

[![Tests](https://github.com/GrooveXlabs/groovefetch/actions/workflows/test.yml/badge.svg)](https://github.com/GrooveXlabs/groovefetch/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **The AI-native web scraper that learns, validates, and feeds your RAG pipeline.**

GrooveFetch is an adaptive web scraping framework built for the AI era. Unlike traditional scrapers that just extract raw HTML, GrooveFetch understands structure, validates data against schemas, learns optimal fetching strategies per domain, and exports clean data directly to vector databases for LLM consumption.

## ✨ What Makes It Different

| Feature | Scrapling | crawl4ai | **GrooveFetch** |
|---------|-----------|----------|-----------------|
| Adaptive Parsing | ✅ | ✅ | ✅ |
| Anti-Bot Bypass | ✅ | ✅ | ✅ |
| Schema Validation | ❌ | ❌ | ✅ **Pydantic-native** |
| Auto-Learned Rate Limits | ❌ | ❌ | ✅ **Per-domain intelligence** |
| Stealth + HTTP Unified | ❌ | ❌ | ✅ **Single interface** |
| RAG/Vector Export | ❌ | ❌ | ✅ **Built-in** |
| AI Agent Tool Calling | MCP only | Basic | ✅ **Native OpenAI/Anthropic tools** |
| Accessibility Snapshots | ❌ | ❌ | ✅ **Token-efficient** |

## 🚀 Quick Start

```bash
pip install groovefetch
```

```python
import asyncio
from groovefetch import GrooveFetch, Schema
from pydantic import BaseModel, Field

# Define what you want to extract
class Product(BaseModel):
    name: str = Field(description="Product name")
    price: float = Field(description="Current price")
    rating: float = Field(description="Star rating", ge=0, le=5)
    in_stock: bool = Field(description="Availability status")

# One-line scrape with validation
async def main():
    gf = GrooveFetch()
    result = await gf.scrape(
        url="https://example-store.com/products",
        schema=Product,
        mode="auto"  # Chooses stealth or HTTP based on target
    )
    print(result.validated)  # List[Product] — fully typed and validated
    
    # Export to vector DB for RAG
    await gf.export_to_chroma(result, collection="products")

asyncio.run(main())
```

## 🧠 Adaptive Intelligence

GrooveFetch learns from every request:

```python
# After a few scrapes, GrooveFetch automatically knows:
# - Optimal delay between requests for each domain
# - Which headers work best
# - Whether stealth browser or HTTP is needed
# - Retry patterns for transient failures

async with GrooveFetch(learn=True) as gf:
    # First request: exploratory
    r1 = await gf.scrape("https://site.com/page1", schema=MySchema)
    
    # Second request: optimized based on learned patterns
    r2 = await gf.scrape("https://site.com/page2", schema=MySchema)
    
    # Stats show what was learned
    print(gf.learner.stats("site.com"))
    # { 'optimal_delay': 2.3, 'success_rate': 0.97, 'stealth_required': True }
```

## 🕵️ Stealth Mode

When sites fight back, GrooveFetch fights smarter:

```python
from groovefetch import StealthFetcher

# C++-level fingerprint spoofing via Camoufox integration
fetcher = StealthFetcher(
    fingerprint="desktop_chrome",  # or rotate randomly
    geoip="us-west",
    proxy="residential://user:pass@host:port"
)

# Accessibility snapshots — 90% smaller than raw HTML
snapshot = await fetcher.snapshot("https://protected-site.com")
print(snapshot.text)      # Clean, structured text
print(snapshot.elements)  # Interactive elements with stable refs
```

## 🤖 AI Agent Integration

GrooveFetch speaks native agent tools:

```python
from groovefetch.agent import get_tool_definitions

# Returns OpenAI/Anthropic-compatible tool schemas
tools = get_tool_definitions()
# [{
#   "type": "function",
#   "function": {
#     "name": "groovefetch_scrape",
#     "description": "Scrape and validate structured data from any URL...",
#     "parameters": { ... }
#   }
# }]
```

## 📦 Architecture

```
groovefetch/
├── core.py       # Main GrooveFetch engine
├── fetchers.py   # HTTP + Stealth unified interface
├── adaptive.py   # Per-domain learning engine
├── parser.py     # HTML parsing with auto-adaptation
├── schema.py     # Pydantic validation layer
├── stealth.py    # Anti-detection & fingerprinting
├── rag.py        # Vector DB export pipeline
├── agent.py      # AI agent tool definitions
├── cli.py        # Command-line interface
└── utils.py      # Helpers & constants
```

## 🔒 Security First

- Input validation on all URLs (SSRF protection)
- Automatic secret redaction in logs
- Safe defaults: rate limiting, respectful crawling
- No data exfiltration — all learning is local

## Ecosystem

| Project | Description |
|---------|-------------|
| [grooveguard](https://github.com/GrooveXlabs/grooveguard) | MCP Server Security Scanner |
| [groovehub](https://github.com/GrooveXlabs/groovehub) | MCP Server Registry |
| [groovestrike](https://github.com/GrooveXlabs/groovestrike) | Autonomous pentest framework |
| [groovelink](https://github.com/GrooveXlabs/groovelink) | Resilient API client |
| [purpleforge](https://github.com/GrooveXlabs/purpleforge) | Purple team defense rules |
| [threathound](https://github.com/GrooveXlabs/threathound) | Blue Team SOC automation |
| [redtrack](https://github.com/GrooveXlabs/redtrack) | Red Team recon & attack paths |

## 📄 License

MIT — GrooveXlabs
