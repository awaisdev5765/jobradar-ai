from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Iterable
from urllib.parse import urlparse


SCAM_TERMS = {
    "crypto payment", "registration fee", "training fee", "telegram only",
    "whatsapp only", "buy equipment", "payment upfront", "gift card",
}


@dataclass(frozen=True)
class CandidateProfile:
    skills: tuple[str, ...]
    desired_titles: tuple[str, ...]
    countries: tuple[str, ...] = ("Worldwide",)
    min_salary: int = 0
    remote_only: bool = True
    blocked_terms: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.skills: errors.append("Add at least one skill")
        if not self.desired_titles: errors.append("Add at least one target role")
        if self.min_salary < 0: errors.append("Minimum salary cannot be negative")
        return errors


@dataclass
class Opportunity:
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    salary_min: int = 0
    remote: bool = False
    tags: list[str] = field(default_factory=list)
    match_score: int = 0
    risk_score: int = 0
    reasons: list[str] = field(default_factory=list)
    status: str = "New"

    @property
    def fingerprint(self) -> str:
        normalized = re.sub(r"\W+", " ", f"{self.title} {self.company} {self.location}".lower()).strip()
        return sha256(normalized.encode()).hexdigest()[:20]

    @property
    def safe_url(self) -> bool:
        parsed = urlparse(self.url)
        return parsed.scheme == "https" and bool(parsed.netloc)


def score_opportunity(job: Opportunity, profile: CandidateProfile) -> Opportunity:
    text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()
    title = job.title.lower()
    reasons: list[str] = []
    score = 20

    matched_skills = [skill for skill in profile.skills if skill.lower() in text]
    if matched_skills:
        score += min(40, len(matched_skills) * 15)
        reasons.append(f"Matches {', '.join(matched_skills[:4])}")
    if any(target.lower() in title for target in profile.desired_titles):
        score += 25
        reasons.append("Preferred role title")
    if job.remote:
        score += 12
        reasons.append("Remote")
    elif profile.remote_only:
        score -= 35
        reasons.append("Not remote")
    if job.salary_min and job.salary_min >= profile.min_salary:
        score += 8
        reasons.append("Meets salary target")
    if any(term.lower() in text for term in profile.blocked_terms):
        score -= 60
        reasons.append("Contains blocked term")

    risk_hits = [term for term in SCAM_TERMS if term in text]
    job.risk_score = min(100, len(risk_hits) * 35)
    if risk_hits:
        reasons.append("Potential scam language")
    if not job.safe_url:
        job.risk_score = min(100, job.risk_score + 35)
        reasons.append("Listing link is not a verified HTTPS address")
    job.match_score = max(0, min(100, score - job.risk_score // 2))
    job.reasons = reasons or ["General profile match"]
    return job


def deduplicate(items: Iterable[Opportunity]) -> list[Opportunity]:
    best: dict[str, Opportunity] = {}
    for item in items:
        current = best.get(item.fingerprint)
        if current is None or item.match_score > current.match_score:
            best[item.fingerprint] = item
    return list(best.values())
