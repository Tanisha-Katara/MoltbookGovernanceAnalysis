import json
import pandas as pd
from datasets import load_dataset
from config import DATASET_NAME, POSTS_SUBSET, COMMENTS_SUBSET, TOP_POSTS_COUNT


def _build_comment_tree(comments_for_post: pd.DataFrame) -> list[dict]:
    """Reconstruct nested comment tree from flat DataFrame using parent_id."""
    if comments_for_post.empty:
        return []

    # Convert rows to dict nodes with 'replies' field
    comment_nodes = {}
    for _, row in comments_for_post.iterrows():
        comment_id = row["id"]
        comment_nodes[comment_id] = {
            "author": str(row.get("author_name", "unknown")),
            "text": str(row.get("content", "")),
            "upvotes": int(row.get("upvotes", row.get("score", 0))),
            "replies": []
        }

    # Build parent-child relationships
    roots = []
    for _, row in comments_for_post.iterrows():
        comment_id = row["id"]
        parent_id = row.get("parent_id")

        if pd.isna(parent_id) or parent_id is None:
            # Top-level comment
            roots.append(comment_nodes[comment_id])
        elif parent_id in comment_nodes:
            # Child comment - attach to parent
            comment_nodes[parent_id]["replies"].append(comment_nodes[comment_id])
        else:
            # Orphaned comment (parent missing) - treat as root
            roots.append(comment_nodes[comment_id])

    return roots


def load_top_posts(n: int = TOP_POSTS_COUNT) -> pd.DataFrame:
    """Load the Moltbook dataset and return the top N most-upvoted posts with comments."""
    # 1. Load both subsets
    posts_ds = load_dataset(DATASET_NAME, POSTS_SUBSET, split="train")
    comments_ds = load_dataset(DATASET_NAME, COMMENTS_SUBSET, split="train")
    posts_df = posts_ds.to_pandas()
    comments_df = comments_ds.to_pandas()

    # 2. Sort posts by score descending
    posts_df = posts_df.sort_values("score", ascending=False).reset_index(drop=True)

    # 3. Filter posts with comment_count > 0
    has_comments = posts_df[posts_df["comment_count"] > 0]
    no_comments = posts_df[posts_df["comment_count"] == 0]

    # 4. Select top N posts (prefer posts with comments)
    if len(has_comments) >= n:
        result = has_comments.head(n)
    else:
        result = pd.concat([has_comments, no_comments.head(n - len(has_comments))])

    # 5. For each post, build nested comment tree and serialize to JSON
    result = result.copy()
    result["comments_json"] = ""

    for idx, row in result.iterrows():
        post_id = row["id"]
        post_comments = comments_df[comments_df["post_id"] == post_id]
        comment_tree = _build_comment_tree(post_comments)
        result.at[idx, "comments_json"] = json.dumps(comment_tree)

    # 6. Add compatibility field: comments_count_actual = comment_count
    result["comments_count_actual"] = result["comment_count"]

    # 7. Rename score to upvotes for compatibility
    if "score" in result.columns and "upvotes" not in result.columns:
        result["upvotes"] = result["score"]

    return result.reset_index(drop=True)
