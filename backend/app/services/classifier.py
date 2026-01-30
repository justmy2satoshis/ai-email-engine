"""AI Email Classifier — uses Ollama to classify, score, and summarize emails."""

import json
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Classification categories
CATEGORIES = [
    "newsletter",       # Recurring content from subscriptions
    "transactional",    # Receipts, confirmations, password resets
    "notification",     # Service alerts, social media notifications
    "personal",         # Direct human-to-human communication
    "marketing",        # Promotions, sales, ads
    "actionable",       # Requires action (meetings, requests, deadlines)
    "noise",            # Junk, spam that passed filters, irrelevant
]

# User interest domains for relevance scoring
INTEREST_DOMAINS = [
    "cryptocurrency",
    "machine_learning",
    "ai_research",
    "trading",
    "software_engineering",
    "startup",
    "data_science",
]

CLASSIFY_PROMPT = """You are an email classification AI. Analyze the following email and return a JSON response.

EMAIL:
From: {from_name} <{from_address}>
Subject: {subject}
Date: {date}

Body (first 2000 chars):
{body}

---

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "category": "<one of: newsletter, transactional, notification, personal, marketing, actionable, noise>",
  "confidence": <float 0.0-1.0>,
  "topics": [<list of relevant topics from: cryptocurrency, machine_learning, ai_research, trading, software_engineering, startup, data_science, finance, security, devops, other>],
  "relevance_score": <float 0.0-1.0, how relevant to a technical builder focused on crypto/ML/AI>,
  "summary": "<one sentence summary of the email's content or purpose>",
  "has_useful_links": <boolean, true if email contains links to articles/repos/papers worth extracting>
}}"""

SCORE_LINKS_PROMPT = """You are a link relevance scorer. Given these URLs extracted from an email, score each link's value for a technical builder focused on cryptocurrency, machine learning, AI research, and trading.

Email context:
Subject: {subject}
From: {from_address}
Category: {category}

Links found:
{links}

---

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "scored_links": [
    {{
      "url": "<the url>",
      "relevance_score": <float 0.0-1.0>,
      "link_type": "<one of: article, github, arxiv, video, tool, docs, social, other>",
      "reason": "<brief reason for the score>"
    }}
  ]
}}"""


@dataclass
class ClassificationResult:
    """Result from AI email classification."""
    category: str = "noise"
    confidence: float = 0.0
    topics: list[str] = None
    relevance_score: float = 0.0
    summary: str = ""
    has_useful_links: bool = False
    model_used: str = ""

    def __post_init__(self):
        if self.topics is None:
            self.topics = []


@dataclass
class LinkScore:
    """AI-scored link relevance."""
    url: str
    relevance_score: float = 0.0
    link_type: str = "other"
    reason: str = ""


class EmailClassifier:
    """Classifies emails using Ollama local LLMs."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=120.0)
        self._model = settings.ollama_model

    async def classify_email(
        self,
        subject: Optional[str],
        from_name: Optional[str],
        from_address: Optional[str],
        body_text: Optional[str],
        date_sent: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a single email using Ollama."""
        try:
            # Build prompt
            body_preview = (body_text or "")[:2000]
            prompt = CLASSIFY_PROMPT.format(
                from_name=from_name or "Unknown",
                from_address=from_address or "unknown@unknown",
                subject=subject or "(no subject)",
                date=date_sent or "unknown",
                body=body_preview if body_preview else "(empty body)",
            )

            # Call Ollama
            response_text = await self._call_ollama(prompt)
            if not response_text:
                return ClassificationResult(model_used=self._model)

            # Parse JSON response
            result = self._parse_classification(response_text)
            result.model_used = self._model
            return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return ClassificationResult(model_used=self._model)

    async def score_links(
        self,
        links: list[str],
        subject: Optional[str],
        from_address: Optional[str],
        category: str,
    ) -> list[LinkScore]:
        """Score extracted links for relevance using Ollama."""
        if not links:
            return []

        try:
            # Format links — cap at 10 to keep JSON output within token limits
            links_text = "\n".join(f"  - {url}" for url in links[:10])

            prompt = SCORE_LINKS_PROMPT.format(
                subject=subject or "(no subject)",
                from_address=from_address or "unknown",
                category=category,
                links=links_text,
            )

            response_text = await self._call_ollama(prompt)
            if not response_text:
                return [LinkScore(url=url) for url in links]

            return self._parse_link_scores(response_text, links)

        except Exception as e:
            logger.error(f"Link scoring failed: {e}")
            return [LinkScore(url=url) for url in links]

    async def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API and return the response text."""
        try:
            response = await self._client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temp for consistent classification
                        "num_predict": 2048,  # Enough for link scoring JSON
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return None
        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return None

    def _parse_classification(self, text: str) -> ClassificationResult:
        """Parse Ollama's JSON response into a ClassificationResult."""
        try:
            # Try to extract JSON from the response
            json_str = self._extract_json(text)
            data = json.loads(json_str)

            return ClassificationResult(
                category=data.get("category", "noise").lower().strip(),
                confidence=float(data.get("confidence", 0.0)),
                topics=data.get("topics", []),
                relevance_score=float(data.get("relevance_score", 0.0)),
                summary=data.get("summary", ""),
                has_useful_links=bool(data.get("has_useful_links", False)),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse classification response: {e}")
            logger.debug(f"Raw response: {text[:500]}")
            return ClassificationResult()

    def _parse_link_scores(self, text: str, original_links: list[str]) -> list[LinkScore]:
        """Parse Ollama's link scoring response."""
        try:
            json_str = self._extract_json(text)
            data = json.loads(json_str)

            scored = []
            for item in data.get("scored_links", []):
                scored.append(LinkScore(
                    url=item.get("url", ""),
                    relevance_score=float(item.get("relevance_score", 0.0)),
                    link_type=item.get("link_type", "other"),
                    reason=item.get("reason", ""),
                ))

            # Add any links that weren't scored
            scored_urls = {s.url for s in scored}
            for url in original_links:
                if url not in scored_urls:
                    scored.append(LinkScore(url=url))

            return scored

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse link scores: {e}")
            return [LinkScore(url=url) for url in original_links]

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from a response that might have markdown wrapping."""
        text = text.strip()

        # Remove markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Find start and end of JSON block
            start = 1 if lines[0].strip().startswith("```") else 0
            end = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            text = "\n".join(lines[start:end]).strip()

        # Find the JSON object
        brace_start = text.find("{")
        if brace_start == -1:
            return text

        # Find matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[brace_start:i + 1]

        return text[brace_start:]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# Singleton
email_classifier = EmailClassifier()
