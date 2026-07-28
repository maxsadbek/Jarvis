"""Web Search Tool.

Performs web searches and returns results.
Uses DuckDuckGo as the primary search engine.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from backend.app.config import settings
from backend.app.tools.base import BaseTool


class WebSearchTool(BaseTool):
    """Search the web for information."""

    def __init__(self) -> None:
        super().__init__()
        self._parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current information, news, or any topic"

    async def execute(self, query: str, max_results: int = 5, **kwargs: Any) -> dict[str, Any]:
        """Execute a web search."""
        try:
            from duckduckgo_search import DDGS

            logger.info(f"Searching web for: {query}")
            max_results = min(max_results, settings.SEARCH_MAX_RESULTS)

            results = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })

            if results:
                formatted = "Search results:\n\n"
                for i, r in enumerate(results, 1):
                    formatted += f"{i}. {r['title']}\n"
                    formatted += f"   URL: {r['url']}\n"
                    formatted += f"   {r['snippet']}\n\n"

                return {
                    "success": True,
                    "result": formatted,
                    "num_results": len(results),
                }
            else:
                return {
                    "success": True,
                    "result": "No search results found for your query.",
                    "num_results": 0,
                }

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}",
                "result": "",
            }

    async def fetch_page(self, url: str) -> dict[str, Any]:
        """Fetch and extract text from a web page."""
        try:
            import requests
            from bs4 import BeautifulSoup

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Limit to first 4000 chars
            text = text[:4000]

            return {
                "success": True,
                "result": text,
                "url": url,
            }

        except Exception as e:
            logger.error(f"Page fetch failed for {url}: {e}")
            return {
                "success": False,
                "error": str(e),
                "result": "",
            }
