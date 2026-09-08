"""Web search — Tavily (agar API kaliti bo'lsa) yoki DuckDuckGo.

Hech qanday qo'shimcha bog'liqlik talab qilmaydi (stdlib `urllib`).
`TAVILY_API_KEY` `.env` da bo'lsa Tavily ishlatiladi (yuqori sifatli,
kalit talab qiladi), aks holda DuckDuckGo Instant Answer API (bepul,
kalitsiz) orqali qidiriladi.
"""

import json
import urllib.parse
import urllib.request

from orion.tools import Tool

_TIMEOUT = 15
_DDG_URL = "https://api.duckduckgo.com/"
_TAVILY_URL = "https://api.tavily.com/search"


def _http_json(url, payload=None, headers=None, timeout=_TIMEOUT):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers = dict(headers or {})
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers or {})
    req.add_header("User-Agent", "orion/0.8 (+https://github.com)")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _search_tavily(query, limit, api_key):
    data = _http_json(
        _TAVILY_URL,
        payload={
            "api_key": api_key,
            "query": query,
            "max_results": limit,
            "search_depth": "basic",
        },
    )
    results = []
    for item in data.get("results", [])[:limit]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:300],
            }
        )
    return results


def _flatten_topics(topics, out):
    for topic in topics or []:
        if not isinstance(topic, dict):
            continue
        if "Topics" in topic:
            _flatten_topics(topic.get("Topics"), out)
        elif topic.get("Text"):
            out.append(topic)


def _search_duckduckgo(query, limit):
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    )
    data = _http_json(f"{_DDG_URL}?{params}")

    results = []
    abstract = (data.get("Abstract") or "").strip()
    abstract_url = data.get("AbstractURL") or ""
    if abstract:
        results.append(
            {
                "title": data.get("Heading") or query,
                "url": abstract_url,
                "snippet": abstract[:300],
            }
        )

    topics = []
    _flatten_topics(data.get("RelatedTopics"), topics)
    for topic in topics:
        if len(results) >= limit:
            break
        results.append(
            {
                "title": topic.get("Text", "")[:80],
                "url": topic.get("FirstURL", ""),
                "snippet": topic.get("Text", "")[:300],
            }
        )

    return results


def web_search(query: str, limit: int = 5, api_key: str = "") -> dict:
    query = query.strip()
    if not query:
        return {"error": "query is required"}

    limit = max(1, min(int(limit or 5), 10))

    try:
        if api_key:
            results = _search_tavily(query, limit, api_key)
        else:
            results = _search_duckduckgo(query, limit)
    except urllib.error.URLError as err:
        return {"error": f"web search failed (network): {err.reason}"}
    except Exception as err:  # noqa: BLE001
        return {"error": f"web search failed: {type(err).__name__}: {err}"}

    return {"results": results, "engine": "tavily" if api_key else "duckduckgo"}


def register(registry, config):
    registry.register(WebSearchTool(config))


class WebSearchTool(Tool):
    def __init__(self, config):
        super().__init__(
            name="web_search",
            description=(
                "Search the live web for up-to-date information, current "
                "versions, documentation, news, or facts beyond your "
                "training data. Returns a list of results with title, URL "
                "and a snippet. Cite the source URLs in your answer."
            ),
            parameters={
                "query": {
                    "type": "string",
                    "description": "The search query (natural language)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 5, max 10)",
                },
            },
            required=["query"],
        )
        self.api_key = getattr(config, "tavily_api_key", "") or ""

    def execute(self, query, limit=5):
        return web_search(query, limit, self.api_key)
