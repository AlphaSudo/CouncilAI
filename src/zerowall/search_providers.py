"""Tavily Basic only. No native generation-provider search or paid fallback."""

import math

import httpx

from .db import DomainError
from .free_provider import OpenRouterFreeProvider


class TavilyBasic:
    name = "tavily_basic"

    def __init__(self, settings):
        self.settings = settings

    def allowance(self):
        if not self.settings.tavily_api_key:
            raise DomainError(
                "Web search is unavailable; use supplied or saved sources", 412
            )
        with httpx.Client(
            timeout=10, follow_redirects=False, trust_env=False
        ) as client:
            response = client.get(
                "https://api.tavily.com/usage",
                headers={"Authorization": "Bearer " + self.settings.tavily_api_key},
            )
        if response.status_code != 200:
            raise DomainError("Free search allowance could not be verified", 412)
        data = response.json().get("account", {})
        used, limit = data.get("plan_usage"), data.get("plan_limit")
        if (
            data.get("current_plan") != "Researcher"
            or type(used) not in (int, float)
            or type(limit) not in (int, float)
            or not math.isfinite(used)
            or not math.isfinite(limit)
            or used < 0
            or limit > 1000
            or limit - used < 1
            or type(data.get("paygo_usage")) not in (int, float)
            or data.get("paygo_usage") != 0
        ):
            raise DomainError(
                "Confirmed free search allowance is unavailable; no paid request was sent",
                402,
            )
        return {"plan": "Researcher", "used": used, "limit": limit, "paygo_usage": 0}

    def search(self, query, domains=(), limit=5, freshness=None):
        body = {
            "query": query,
            "search_depth": "basic",
            "auto_parameters": False,
            "topic": "general",
            "max_results": limit,
            "include_domains": list(domains),
            "include_answer": False,
            "include_raw_content": False,
            "include_usage": True,
        }
        if freshness:
            body["time_range"] = freshness
        with httpx.Client(
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = OpenRouterFreeProvider.bounded_post(
                client,
                "https://api.tavily.com/search",
                headers={"Authorization": "Bearer " + self.settings.tavily_api_key},
                json=body,
            )
        if response.status_code != 200:
            raise DomainError(
                f"Web search returned HTTP {response.status_code}; saved sources remain available",
                response.status_code
                if response.status_code in (401, 402, 403, 429)
                else 502,
            )
        data = response.json()
        if not isinstance(data.get("results"), list):
            raise DomainError("Search returned an invalid result", 502)
        return {
            "provider": self.name,
            "query": query,
            "results": [
                {
                    "title": str(x.get("title", ""))[:240],
                    "url": str(x.get("url", ""))[:2000],
                    "snippet": str(x.get("content", ""))[:2000],
                    "snippet_original_chars": len(str(x.get("content", ""))),
                    "snippet_truncated": len(str(x.get("content", ""))) > 2000,
                    "rank": i + 1,
                    "access": "search_snippet_only",
                }
                for i, x in enumerate(data["results"][:limit])
                if isinstance(x, dict)
            ],
            "usage": data.get("usage"),
            "reserved_credits": 1,
            "request_id": data.get("request_id"),
            "retrieval_is_verification": False,
            "raw_response": data,
        }

    def extract(self, urls):
        """Basic batch extraction; no generated answer or paid fallback."""
        with httpx.Client(timeout=httpx.Timeout(25, connect=5), follow_redirects=False, trust_env=False) as client:
            response = OpenRouterFreeProvider.bounded_post(client, "https://api.tavily.com/extract",
                headers={"Authorization": "Bearer " + self.settings.tavily_api_key},
                json={"urls": list(urls), "extract_depth": "basic", "format": "markdown", "include_usage": True, "timeout": 15})
        if response.status_code != 200:
            raise DomainError(f"Page extraction returned HTTP {response.status_code}; saved search results remain available", response.status_code if response.status_code in (401, 402, 403, 429) else 502)
        data = response.json()
        if not isinstance(data.get("results"), list):
            raise DomainError("Page extraction returned an invalid result", 502)
        return data
