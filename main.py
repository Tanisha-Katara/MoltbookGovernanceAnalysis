import argparse
import asyncio
import json
import os
import sys
from typing import Optional

from tqdm import tqdm

from config import (
    GOOGLE_API_KEY,
    TOP_POSTS_COUNT,
    DRY_RUN_COUNT,
    OUTPUT_DIR,
    RAW_RESULTS_PATH,
    REPORT_PATH,
)
from data.loader import load_top_posts
from data.comment_parser import parse_comments, format_thread_for_llm
from analysis.consensus_detector import analyze_post
from analysis.pattern_classifier import classify_patterns
from analysis.agent_influence import analyze_agent_influence
from report.generator import generate_report


def load_cached_results() -> Optional[dict[str, dict]]:
    """Load previously saved raw results keyed by post title."""
    if not os.path.exists(RAW_RESULTS_PATH):
        return None
    try:
        with open(RAW_RESULTS_PATH) as f:
            results_list = json.load(f)
        return {r["post_title"]: r for r in results_list}
    except (json.JSONDecodeError, KeyError):
        return None


def save_raw_results(results: list[dict]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(RAW_RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)


async def run(dry_run: bool = False):
    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    n = DRY_RUN_COUNT if dry_run else TOP_POSTS_COUNT
    print(f"{'[DRY RUN] ' if dry_run else ''}Loading top {n} posts...")
    df = load_top_posts(n)
    print(f"Loaded {len(df)} posts.")

    # Dataset stats
    dataset_stats = {
        "source": "lysandrehooh/moltbook",
        "post_count": len(df),
        "total_comments": int(df["comments_count_actual"].sum()),
        "avg_comments": float(df["comments_count_actual"].mean()),
        "min_upvotes": int(df["upvotes"].min()),
        "max_upvotes": int(df["upvotes"].max()),
    }

    # Load cached results
    cached = load_cached_results()
    if cached:
        print(f"Found {len(cached)} cached results.")

    # Pass 1: Per-post analysis
    print("\n--- Pass 1: Per-post consensus analysis ---")
    results = []
    tasks = []

    for _, row in df.iterrows():
        title = row.get("title", "Untitled")

        # Use cached result if available
        if cached and title in cached:
            results.append(cached[title])
            continue

        comments = parse_comments(row.get("comments_json", ""))
        if not comments:
            results.append({
                "post_title": title,
                "post_upvotes": row.get("upvotes", 0),
                "comment_count": 0,
                "consensus": "UNKNOWN",
                "consensus_position": None,
                "formation_pattern": "No comments to analyze",
                "key_moments": [],
                "consensus_drivers": [],
                "evidence_quotes": [],
            })
            continue

        tasks.append((row.to_dict(), comments))

    if tasks:
        print(f"Analyzing {len(tasks)} posts via Gemini...")
        pbar = tqdm(total=len(tasks), desc="Analyzing posts")

        async def analyze_with_progress(post, comments):
            result = await analyze_post(post, comments)
            pbar.update(1)
            return result

        api_results = await asyncio.gather(
            *[analyze_with_progress(post, comments) for post, comments in tasks]
        )
        pbar.close()
        results.extend(api_results)

    # Save intermediate results
    save_raw_results(results)
    print(f"Saved {len(results)} results to {RAW_RESULTS_PATH}")

    # Pass 2: Pattern clustering
    print("\n--- Pass 2: Pattern clustering ---")
    pattern_data = await classify_patterns(results)
    print(f"Discovered {len(pattern_data.get('patterns', []))} patterns.")

    # Pass 3: Agent influence analysis
    print("\n--- Pass 3: Agent influence analysis ---")
    influence_data = analyze_agent_influence(results)
    print(f"Found {influence_data['unique_drivers']} unique consensus-driving agents.")
    top3 = influence_data.get("concentration", {}).get("top_3", {})
    if top3:
        print(f"Top 3 agents account for {top3['share']:.1%} of consensus events.")

    # Generate report
    print("\n--- Generating report ---")
    report = generate_report(results, pattern_data, influence_data, dataset_stats)
    print(f"Report written to {REPORT_PATH}")
    print(f"\nDone! Analyzed {len(results)} posts.")


def main():
    parser = argparse.ArgumentParser(description="Moltbook Consensus Analysis")
    parser.add_argument("--dry-run", action="store_true", help=f"Test on {DRY_RUN_COUNT} posts only")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
