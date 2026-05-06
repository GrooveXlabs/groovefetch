"""AI Agent tool definitions for OpenAI/Anthropic function calling."""

from typing import Dict, Any, List


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get OpenAI/Anthropic-compatible tool definitions.
    
    Returns:
        List of tool schemas for function calling
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "groovefetch_scrape",
                "description": (
                    "Scrape structured data from a web URL. Extracts and validates "
                    "data against a provided schema. Use this when you need to "
                    "gather current information from websites, product listings, "
                    "news articles, or any structured web content."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to scrape. Must be a valid http or https URL.",
                        },
                        "schema_description": {
                            "type": "string",
                            "description": (
                                "Description of the data structure to extract. "
                                "Example: 'Product with name (string), price (number), "
                                "rating (number 0-5), in_stock (boolean)'"
                            ),
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["auto", "http", "stealth"],
                            "description": (
                                "Fetching mode. 'auto' chooses based on target. "
                                "'http' is fast but may be blocked. 'stealth' uses "
                                "a real browser and bypasses most protections."
                            ),
                        },
                        "container_selector": {
                            "type": "string",
                            "description": (
                                "Optional CSS selector for container elements. "
                                "If empty, auto-detection is used."
                            ),
                        },
                    },
                    "required": ["url", "schema_description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "groovefetch_snapshot",
                "description": (
                    "Get a token-efficient accessibility snapshot of a webpage. "
                    "Returns clean text and interactive elements. Much smaller than "
                    "raw HTML — ideal for LLM context windows. Use for reading "
                    "articles, documentation, or any text-heavy page."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to snapshot.",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "groovefetch_crawl",
                "description": (
                    "Crawl multiple pages starting from a URL. Discovers and fetches "
                    "linked pages up to a maximum. Use for site mapping, "
                    "documentation extraction, or bulk data gathering."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_url": {
                            "type": "string",
                            "description": "Starting URL for the crawl.",
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "Maximum pages to fetch (default: 10).",
                            "default": 10,
                        },
                        "same_domain": {
                            "type": "boolean",
                            "description": "Whether to stay on the same domain.",
                            "default": True,
                        },
                    },
                    "required": ["start_url"],
                },
            },
        },
    ]


class AgentAdapter:
    """Adapter for executing agent tool calls.
    
    Usage:
        adapter = AgentAdapter(groovefetch_instance)
        result = await adapter.execute_tool_call(tool_call)
    """
    
    def __init__(self, groovefetch):
        self.gf = groovefetch
    
    async def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call and return the result.
        
        Args:
            tool_call: Tool call from OpenAI/Anthropic API
            
        Returns:
            Tool result
        """
        name = tool_call.get("function", {}).get("name", "")
        arguments = tool_call.get("function", {}).get("arguments", "{}")
        
        import json
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        
        if name == "groovefetch_scrape":
            return await self._handle_scrape(arguments)
        elif name == "groovefetch_snapshot":
            return await self._handle_snapshot(arguments)
        elif name == "groovefetch_crawl":
            return await self._handle_crawl(arguments)
        else:
            return {"error": f"Unknown tool: {name}"}
    
    async def _handle_scrape(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scrape tool call."""
        from pydantic import create_model, Field
        
        # Create dynamic model from description
        # In production, use proper schema generation
        DynamicModel = create_model(
            "DynamicScrape",
            __base__=None,
            text=(str, Field(description="Extracted text content")),
        )
        
        result = await self.gf.scrape(
            url=args["url"],
            schema=DynamicModel,
            mode=args.get("mode", "auto"),
            container_selector=args.get("container_selector", ""),
        )
        
        return {
            "success": result.is_valid,
            "data": result.to_dict(),
            "errors": result.errors,
            "metadata": result.metadata,
        }
    
    async def _handle_snapshot(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle snapshot tool call."""
        return await self.gf.snapshot(args["url"])
    
    async def _handle_crawl(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle crawl tool call."""
        results = await self.gf.crawl(
            start_url=args["start_url"],
            max_pages=args.get("max_pages", 10),
            same_domain=args.get("same_domain", True),
        )
        
        return {
            "pages_fetched": len(results),
            "urls": [r.url for r in results],
            "errors": [r.error for r in results if r.error],
        }
