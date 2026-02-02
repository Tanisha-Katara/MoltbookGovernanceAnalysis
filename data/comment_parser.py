import json
from typing import Any, Optional


# Cached field mappings discovered from schema discovery
_field_map: Optional[dict[str, str]] = None


def discover_schema(comments_raw: list[dict]) -> dict[str, str]:
    """Discover the field names used in comment objects.

    Returns a mapping of canonical names to actual field names:
      - author: the username/author field
      - text: the comment body/content field
      - replies: the nested replies/children field
      - upvotes: the upvote/score field
    """
    if not comments_raw:
        return {}

    sample = comments_raw[0]
    keys = set(sample.keys())

    mapping = {}

    # Author field
    for candidate in ("author", "user", "username", "commenter", "name"):
        if candidate in keys:
            mapping["author"] = candidate
            break

    # Text/body field
    for candidate in ("text", "body", "content", "comment", "message"):
        if candidate in keys:
            mapping["text"] = candidate
            break

    # Replies/children field
    for candidate in ("replies", "children", "responses", "nested", "sub_comments"):
        if candidate in keys:
            mapping["replies"] = candidate
            break

    # Upvotes/score field
    for candidate in ("upvotes", "score", "likes", "votes", "karma", "ups"):
        if candidate in keys:
            mapping["upvotes"] = candidate
            break

    return mapping


def _flatten_thread(
    comments: list[dict],
    field_map: dict[str, str],
    depth: int = 0,
    parent_author: Optional[str] = None,
) -> list[dict]:
    """Recursively flatten a nested comment tree into a linear list."""
    result = []
    for comment in comments:
        author = comment.get(field_map.get("author", "author"), "unknown")
        text = comment.get(field_map.get("text", "text"), "")
        upvotes = comment.get(field_map.get("upvotes", "upvotes"), 0)

        if text is None:
            text = ""

        result.append({
            "author": str(author),
            "text": str(text),
            "depth": depth,
            "parent_author": parent_author,
            "upvotes": upvotes if upvotes is not None else 0,
        })

        # Recurse into replies
        replies_key = field_map.get("replies", "replies")
        children = comment.get(replies_key, [])
        if children:
            result.extend(_flatten_thread(children, field_map, depth + 1, str(author)))

    return result


def parse_comments(comments_json_str: str) -> list[dict]:
    """Parse a comments_json string into a flat list of comment dicts."""
    global _field_map

    if not comments_json_str:
        return []

    try:
        raw: Any = json.loads(comments_json_str)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(raw, list) or len(raw) == 0:
        return []

    # Discover schema on first call
    if _field_map is None:
        _field_map = discover_schema(raw)

    return _flatten_thread(raw, _field_map)


def reset_schema_cache():
    """Reset the cached field map (useful for testing)."""
    global _field_map
    _field_map = None


def format_thread_for_llm(comments: list[dict]) -> str:
    """Format a flat comment list into a readable string for LLM analysis."""
    lines = []
    for c in comments:
        indent = "  " * c["depth"]
        reply_to = f" (replying to {c['parent_author']})" if c["parent_author"] else ""
        lines.append(f"{indent}[{c['author']}{reply_to}]: {c['text']}")
    return "\n".join(lines)
