import urllib.request
import urllib.parse
import re
from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class SearchTool(BaseTool):
    """Tool that performs web search query lookups via DuckDuckGo Lite."""

    name = "search_tool"
    description = (
        "Searches the web for up-to-date information. IMPORTANT: keep search queries extremely short, "
        "simple, and keyword-focused (maximum 3-4 words, e.g. 'Maruti Brezza news' or 'Brezza recall 2026'). "
        "Do not pass long sentences or complex descriptions as the search query."
    )
    version = "2.0.0"
    category = "general"
    tags = ["search", "web", "lookup", "info"]

    def _execute_ddg_lite(self, query: str) -> list:
        """Executes search query via DuckDuckGo Lite interface."""
        logger.info("Executing DuckDuckGo Lite Search", query=query)
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        try:
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
                
            results = []
            parts = html.split("class='result-link'")
            for i in range(1, len(parts)):
                prev_part = parts[i - 1]
                curr_part = parts[i]
                
                href_match = re.search(r'href="([^"]+)"[^"]*$', prev_part)
                if not href_match:
                    href_match = re.search(r"href='([^']+)'[^']*$", prev_part)
                if not href_match:
                    continue
                href = href_match.group(1)
                
                title_match = re.search(r'^[^>]*>(.*?)</a>', curr_part, re.DOTALL)
                if not title_match:
                    continue
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                
                snippet = ""
                snippet_match = re.search(r"class='result-snippet'[^>]*>(.*?)</td>", curr_part, re.DOTALL)
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                    
                if title and href:
                    # Clean up common HTML entities
                    title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&ndash;", "-").replace("&mdash;", "-").replace("&#x27;", "'")
                    snippet = snippet.replace("&amp;", "&").replace("&quot;", '"').replace("&ndash;", "-").replace("&mdash;", "-").replace("&#x27;", "'")
                    results.append({
                        "title": title,
                        "body": snippet,
                        "href": href
                    })
            return results
        except Exception as e:
            logger.error("DuckDuckGo Lite search execution failed", error=str(e))
            return []

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the search query using DuckDuckGo Lite.

        Args:
            state: The current workflow state.
        """
        logger.info("Executing Search Tool")
        context = state.get("context", {})
        query = context.get("search_query") or state.get("query")

        if not query:
            return {"status": "error", "message": "No search query provided in context or state."}

        results = self._execute_ddg_lite(query)
        source_used = "duckduckgo_lite"

        # Try simplified query if first query returned 0 results
        if not results and len(query.split()) > 3:
            simplified_query = " ".join(query.split()[:3])
            logger.info("DDG Lite returned 0 results. Retrying with simplified query", simplified_query=simplified_query)
            results = self._execute_ddg_lite(simplified_query)
            query = simplified_query
            source_used = "duckduckgo_lite_simplified"

        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "href": r.get("href", "")
            })

        return {
            "status": "success",
            "query": query,
            "source": source_used,
            "results": formatted_results
        }
