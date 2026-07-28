"""Browser Automation Tool.

Performs web browsing operations:
- Fetch web pages
- Search the web
- Extract content
- Take screenshots
- Fill forms (limited)

Uses Playwright for reliable browser automation.
Falls back to requests + BeautifulSoup if Playwright is not available.
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from backend.app.tools.base import BaseTool


class BrowserTool(BaseTool):
    """Browser automation for web navigation and interaction."""

    def __init__(self) -> None:
        super().__init__()
        self._browser = None
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "get_page",
                        "search",
                        "screenshot",
                        "get_links",
                        "extract_text",
                    ],
                    "description": "Browser action to perform",
                },
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (for get_page, screenshot)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search action)",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector to extract specific content",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Browse the web: fetch pages, search, take screenshots, extract content"

    async def execute(
        self,
        action: str,
        url: str = "",
        query: str = "",
        selector: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a browser action.

        Args:
            action: Action to perform.
            url: URL for navigation actions.
            query: Search query.
            selector: CSS selector for extraction.

        Returns:
            Dict with action results.
        """
        handlers = {
            "get_page": self._get_page,
            "search": self._web_search,
            "screenshot": self._screenshot,
            "get_links": self._get_links,
            "extract_text": self._extract_text,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}", "result": ""}

        return await handler(url, query, selector)

    async def _get_page(self, url: str, query: str = "", selector: str = "") -> dict[str, Any]:
        """Fetch a web page and extract its content."""
        if not url:
            return {"success": False, "error": "URL required", "result": ""}

        # Validate URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        logger.info(f"Fetching page: {url}")

        try:
            # Try Playwright first
            try:
                return await self._playwright_get_page(url, selector)
            except ImportError:
                pass

            # Fallback to requests + BeautifulSoup
            import requests
            from bs4 import BeautifulSoup

            response = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            if selector:
                elements = soup.select(selector)
                content = "\n".join(el.get_text(strip=True) for el in elements[:20])
            else:
                # Remove script/style elements
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                content = soup.get_text(separator="\n", strip=True)

            # Limit content length
            content = content[:8000]
            if len(content) >= 8000:
                content += "\n... [content truncated]"

            return {
                "success": True,
                "result": content,
                "url": url,
                "content_length": len(content),
            }

        except Exception as e:
            logger.error(f"Failed to fetch page {url}: {e}")
            return {"success": False, "error": str(e), "result": ""}

    async def _playwright_get_page(self, url: str, selector: str) -> dict[str, Any]:
        """Fetch a page using Playwright."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=15000)

                if selector:
                    elements = await page.query_selector_all(selector)
                    content = "\n".join(
                        [await el.inner_text() for el in elements[:20]]
                    )
                else:
                    content = await page.evaluate("document.body.innerText")

                await browser.close()

                content = content[:8000]
                if len(content) >= 8000:
                    content += "\n... [content truncated]"

                return {
                    "success": True,
                    "result": content,
                    "url": url,
                    "method": "playwright",
                }

        except ImportError:
            raise  # Let the caller handle fallback
        except Exception as e:
            return {"success": False, "error": f"Playwright failed: {e}", "result": ""}

    async def _web_search(self, url: str = "", query: str = "", selector: str = "") -> dict[str, Any]:
        """Search the web using DuckDuckGo."""
        if not query:
            return {"success": False, "error": "Search query required", "result": ""}

        try:
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
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

                return {"success": True, "result": formatted, "results_count": len(results)}
            else:
                return {"success": True, "result": "No results found.", "results_count": 0}

        except Exception as e:
            return {"success": False, "error": f"Search failed: {e}", "result": ""}

    async def _screenshot(self, url: str = "", query: str = "", selector: str = "") -> dict[str, Any]:
        """Take a screenshot of a web page."""
        if not url:
            return {"success": False, "error": "URL required", "result": ""}

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(viewport={"width": 1280, "height": 720})
                    await page.goto(url, timeout=15000)

                    screenshot_bytes = await page.screenshot(full_page=False)
                    await browser.close()

                    import base64
                    b64 = base64.b64encode(screenshot_bytes).decode()

                    return {
                        "success": True,
                        "result": f"Screenshot taken ({len(screenshot_bytes)} bytes)",
                        "screenshot_base64": b64[:100] + "...",
                        "url": url,
                    }

            except ImportError:
                return {"success": False, "error": "Screenshots require Playwright", "result": ""}

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _get_links(self, url: str = "", query: str = "", selector: str = "") -> dict[str, Any]:
        """Extract all links from a page."""
        if not url:
            return {"success": False, "error": "URL required", "result": ""}

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin

            response = requests.get(url, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")

            links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                text = a_tag.get_text(strip=True)[:50]
                absolute_url = urljoin(url, href)
                links.append({"text": text, "url": absolute_url})

            # Deduplicate
            seen = set()
            unique_links = []
            for link in links:
                if link["url"] not in seen:
                    seen.add(link["url"])
                    unique_links.append(link)

            formatted = f"Links found on {url}:\n\n"
            for link in unique_links[:30]:
                formatted += f"• {link['text'] or '(no text)'}\n  {link['url']}\n"

            if len(unique_links) > 30:
                formatted += f"\n... and {len(unique_links) - 30} more"

            return {
                "success": True,
                "result": formatted,
                "links_count": len(unique_links),
            }

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _extract_text(self, url: str = "", query: str = "", selector: str = "") -> dict[str, Any]:
        """Extract specific content using CSS selector."""
        return await self._get_page(url, selector=selector)
