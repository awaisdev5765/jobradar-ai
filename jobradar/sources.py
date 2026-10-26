from __future__ import annotations

import re
import json
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import certifi

from .core import Opportunity


def _plain(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").replace("&amp;", "&").strip()


def _json(url: str, timeout: float, params: dict[str, object] | None = None) -> object:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "JobRadar/0.1"})
    context=ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=timeout,context=context) as response:  # noqa: S310 - trusted connector URLs
        return json.loads(response.read().decode("utf-8"))


def fetch_remotive(timeout: float) -> list[Opportunity]:
    data = _json("https://remotive.com/api/remote-jobs", timeout, {"limit": 100})
    return [Opportunity(
        title=item.get("title", "Untitled role"), company=item.get("company_name", "Unknown"),
        location=item.get("candidate_required_location") or "Remote",
        description=_plain(item.get("description", "")), url=item.get("url", ""),
        source="Remotive", remote=True,
        tags=[item.get("category", ""), item.get("job_type", "")],
    ) for item in data.get("jobs", [])]


def fetch_remoteok(timeout: float) -> list[Opportunity]:
    data = _json("https://remoteok.com/api", timeout)
    return [Opportunity(
        title=item.get("position", "Untitled role"), company=item.get("company", "Unknown"),
        location=item.get("location") or "Remote · Worldwide",
        description=_plain(item.get("description", "")), url=item.get("url", ""),
        source="Remote OK", salary_min=int(item.get("salary_min") or 0), remote=True,
        tags=list(item.get("tags") or []),
    ) for item in data if isinstance(item, dict) and item.get("position")]


CONNECTORS = {"Remotive": fetch_remotive, "Remote OK": fetch_remoteok}

def discover_public_jobs(timeout: float = 12.0, enabled: set[str] | None = None) -> tuple[list[Opportunity], list[str]]:
    jobs: list[Opportunity] = []
    errors: list[str] = []
    active=enabled if enabled is not None else set(CONNECTORS)
    for name, connector in CONNECTORS.items():
        if name not in active: continue
        try:
            jobs.extend(connector(timeout))
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{name}: {type(exc).__name__}")
    return jobs, errors
