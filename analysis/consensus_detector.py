import asyncio
import json
import re
from typing import Optional
from google import genai
from config import GOOGLE_API_KEY, GEMINI_MODEL, CONCURRENCY_LIMIT, MAX_COMMENTS_FULL_THREAD, CHUNK_SIZE
from data.comment_parser import format_thread_for_llm

_client = None
_semaphore = None


def _get_semaphore():
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    return _semaphore


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client

PER_POST_PROMPT = """\
You are analyzing a discussion thread from Moltbook, a platform where AI agents discuss and debate topics.

**Post Title:** {title}
**Post Content:** {post_content}

**Comment Thread:**
{thread}

Analyze this thread and respond with ONLY valid JSON (no markdown fences):
{{
  "consensus": "YES" | "NO" | "PARTIAL",
  "consensus_position": "Brief description of what they agreed on, or null if no consensus",
  "formation_pattern": "2-3 sentence description of how consensus formed (or why it didn't)",
  "key_moments": ["1-3 key comments or turning points that drove the outcome"],
  "consensus_drivers": [
    {{
      "agent": "username",
      "role": "proposed_position | reframed_debate | provided_evidence | synthesized_views | built_momentum | other",
      "description": "Brief description of what this agent did to drive consensus"
    }}
  ],
  "evidence_quotes": ["1-3 direct quotes from comments that illustrate the consensus or key disagreement"]
}}
"""

CHUNK_SUMMARY_PROMPT = """\
Summarize this portion of a discussion thread, preserving:
- Key arguments and positions taken
- Which agents said what
- Any agreements or disagreements
- The flow of the conversation

Thread chunk:
{chunk}
"""


def _chunk_comments(comments: list[dict]) -> list[list[dict]]:
    """Split comments into chunks of ~CHUNK_SIZE."""
    chunks = []
    for i in range(0, len(comments), CHUNK_SIZE):
        chunks.append(comments[i:i + CHUNK_SIZE])
    return chunks


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response, handling markdown fences."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding JSON object in text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def _summarize_chunk(chunk: list[dict]) -> str:
    """Summarize a chunk of comments using Gemini."""
    thread_text = format_thread_for_llm(chunk)
    prompt = CHUNK_SUMMARY_PROMPT.format(chunk=thread_text)

    # Retry with exponential backoff on rate limit errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                _get_client().models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < max_retries - 1:
                    # Extract retry delay from error message or use exponential backoff
                    wait_time = (2 ** attempt) * 15  # 15, 30, 60 seconds
                    print(f"Rate limit hit, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            else:
                raise
    return ""  # Fallback


async def analyze_post(post: dict, comments: list[dict]) -> dict:
    """Analyze a single post's comment thread for consensus patterns."""
    async with _get_semaphore():
        title = post.get("title", "Untitled")
        post_content = post.get("content", post.get("text", ""))
        if post_content is None:
            post_content = ""

        # Handle large threads by summarizing chunks
        if len(comments) > MAX_COMMENTS_FULL_THREAD:
            chunks = _chunk_comments(comments)
            # Process chunks sequentially to respect rate limits
            summaries = []
            for chunk in chunks:
                summary = await _summarize_chunk(chunk)
                summaries.append(summary)
            thread_text = "\n\n---\n\n".join(
                f"[Chunk {i+1} summary]: {s}" for i, s in enumerate(summaries)
            )
        else:
            thread_text = format_thread_for_llm(comments)

        prompt = PER_POST_PROMPT.format(
            title=title,
            post_content=post_content[:2000],
            thread=thread_text,
        )

        # Retry with exponential backoff on rate limit errors
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    _get_client().models.generate_content,
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 15
                        print(f"Rate limit hit for '{title[:50]}...', waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise
                else:
                    raise

        if response is None:
            raise Exception("Failed to get response after retries")

        result = _extract_json(response.text)
        if result is None:
            result = {
                "consensus": "UNKNOWN",
                "consensus_position": None,
                "formation_pattern": "Failed to parse LLM response",
                "key_moments": [],
                "consensus_drivers": [],
                "evidence_quotes": [],
            }

        result["post_title"] = title
        result["post_upvotes"] = post.get("upvotes", 0)
        result["comment_count"] = len(comments)
        return result
