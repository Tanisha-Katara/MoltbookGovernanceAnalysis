import asyncio
import json
import re
from typing import Optional
from google import genai
from config import GCP_PROJECT, GCP_LOCATION, GEMINI_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return _client

PATTERN_CLUSTERING_PROMPT = """\
You have analyzed {count} discussion threads from Moltbook (an AI agent discussion platform) for consensus patterns.

Here are the per-post analysis summaries:

{summaries}

Based on all of these analyses, please:

1. Identify 3-5 distinct consensus formation patterns that recur across posts.
2. Name and describe each pattern in 2-3 sentences.
3. Classify each post (by title) into one of the discovered patterns.
4. Provide a distribution (count and percentage for each pattern).

Respond with ONLY valid JSON (no markdown fences):
{{
  "patterns": [
    {{
      "name": "Pattern Name",
      "description": "2-3 sentence description of this pattern",
      "post_titles": ["list of post titles that match this pattern"],
      "count": 0,
      "percentage": 0.0
    }}
  ],
  "unclassified": ["post titles that don't fit any pattern, if any"]
}}
"""


def _extract_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _build_summaries_text(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. **{r['post_title']}** (upvotes: {r.get('post_upvotes', '?')}, "
            f"comments: {r.get('comment_count', '?')})\n"
            f"   Consensus: {r.get('consensus', '?')}\n"
            f"   Pattern: {r.get('formation_pattern', 'N/A')}\n"
        )
    return "\n".join(lines)


async def classify_patterns(results: list[dict]) -> dict:
    """Send all post analyses to Gemini for pattern clustering."""
    # Only include posts that had comments analyzed
    analyzed = [r for r in results if r.get("consensus") != "UNKNOWN"]

    if not analyzed:
        return {"patterns": [], "unclassified": []}

    summaries_text = _build_summaries_text(analyzed)
    prompt = PATTERN_CLUSTERING_PROMPT.format(
        count=len(analyzed),
        summaries=summaries_text,
    )

    response = await _get_client().aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    result = _extract_json(response.text)
    if result is None:
        result = {"patterns": [], "unclassified": [], "error": "Failed to parse clustering response"}

    return result
