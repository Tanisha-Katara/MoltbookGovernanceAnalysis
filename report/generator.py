import os
from config import REPORT_PATH


def generate_report(
    post_results: list[dict],
    pattern_data: dict,
    influence_data: dict,
    dataset_stats: dict,
) -> str:
    """Generate the Markdown consensus report and write it to disk."""
    lines = []

    # Header
    lines.append("# Moltbook Consensus Pattern Analysis\n")

    # Dataset section
    lines.append("## Dataset\n")
    lines.append(f"- **Source:** {dataset_stats.get('source', 'lysandrehooh/moltbook')}")
    lines.append(f"- **Posts analyzed:** {dataset_stats.get('post_count', '?')}")
    lines.append(f"- **Total comments across posts:** {dataset_stats.get('total_comments', '?')}")
    lines.append(f"- **Average comments per post:** {dataset_stats.get('avg_comments', '?'):.1f}")
    lines.append(f"- **Upvote range:** {dataset_stats.get('min_upvotes', '?')} – {dataset_stats.get('max_upvotes', '?')}")
    lines.append("")

    # Consensus overview
    consensus_counts = {"YES": 0, "NO": 0, "PARTIAL": 0, "UNKNOWN": 0}
    for r in post_results:
        c = r.get("consensus", "UNKNOWN")
        consensus_counts[c] = consensus_counts.get(c, 0) + 1

    total = len(post_results) or 1
    lines.append("## Consensus Overview\n")
    lines.append(f"| Status | Count | Percentage |")
    lines.append(f"|--------|-------|------------|")
    for status in ("YES", "PARTIAL", "NO", "UNKNOWN"):
        count = consensus_counts[status]
        pct = count / total * 100
        lines.append(f"| {status} | {count} | {pct:.1f}% |")
    lines.append("")

    # Discovered patterns
    patterns = pattern_data.get("patterns", [])
    if patterns:
        lines.append("## Discovered Consensus Patterns\n")
        for p in patterns:
            name = p.get("name", "Unnamed")
            desc = p.get("description", "")
            count = p.get("count", len(p.get("post_titles", [])))
            pct = p.get("percentage", 0)
            lines.append(f"### {name} ({count} posts, {pct:.1f}%)\n")
            lines.append(f"{desc}\n")

            # Show example posts
            example_titles = p.get("post_titles", [])[:3]
            if example_titles:
                lines.append("**Example posts:**")
                for t in example_titles:
                    lines.append(f"- {t}")
                    # Find matching result for quotes
                    for r in post_results:
                        if r.get("post_title") == t:
                            quotes = r.get("evidence_quotes", [])
                            if quotes:
                                lines.append(f"  > {quotes[0]}")
                            break
                lines.append("")
        lines.append("")

    # Agent influence analysis
    lines.append("## Agent Influence Analysis\n")
    lines.append(
        "**Hypothesis:** A small number of agents are disproportionately responsible "
        "for driving consensus across Moltbook discussions.\n"
    )

    ranked = influence_data.get("ranked_agents", [])
    total_events = influence_data.get("total_driver_events", 0)
    consensus_posts = influence_data.get("total_consensus_posts", 0)
    unique_drivers = influence_data.get("unique_drivers", 0)
    baseline = influence_data.get("uniform_baseline", 0)

    lines.append(f"- **Posts with consensus (YES or PARTIAL):** {consensus_posts}")
    lines.append(f"- **Total consensus-driving events:** {total_events}")
    lines.append(f"- **Unique consensus-driving agents:** {unique_drivers}")
    lines.append(f"- **Uniform baseline (expected events per agent):** {baseline:.2f}")
    lines.append("")

    # Top agents table
    if ranked:
        lines.append("### Top Consensus-Driving Agents\n")
        lines.append("| Rank | Agent | Posts Driven | Share | Primary Role |")
        lines.append("|------|-------|-------------|-------|--------------|")
        profiles = influence_data.get("agent_profiles", {})
        for i, (agent, count) in enumerate(ranked[:15], 1):
            share = count / total_events * 100 if total_events else 0
            profile = profiles.get(agent, {})
            role = profile.get("primary_role", "?")
            lines.append(f"| {i} | {agent} | {count} | {share:.1f}% | {role} |")
        lines.append("")

    # Concentration
    concentration = influence_data.get("concentration", {})
    if concentration:
        lines.append("### Concentration Analysis\n")
        lines.append("| Group | Agents | Consensus Events | Share |")
        lines.append("|-------|--------|-----------------|-------|")
        for key in ("top_1", "top_3", "top_5", "top_10"):
            if key in concentration:
                c = concentration[key]
                n = key.replace("top_", "Top ")
                lines.append(
                    f"| {n} | {', '.join(c['agents'][:3])}{'...' if len(c['agents']) > 3 else ''} "
                    f"| {c['consensus_events']} | {c['share']:.1%} |"
                )
        lines.append("")

        # Interpretation
        top5 = concentration.get("top_5", {})
        if top5.get("share", 0) > 0.3:
            lines.append(
                f"**Finding:** The top 5 agents account for **{top5['share']:.1%}** of all "
                f"consensus-driving events, indicating significant concentration of influence. "
                f"Under a uniform distribution, we would expect each agent to drive ~{baseline:.1f} "
                f"consensus events, but the top agents far exceed this.\n"
            )
        else:
            lines.append(
                f"**Finding:** Consensus-driving influence appears relatively distributed, "
                f"with the top 5 agents accounting for {top5.get('share', 0):.1%} of events.\n"
            )

    # Agent profiles
    profiles = influence_data.get("agent_profiles", {})
    if profiles:
        lines.append("### Agent Profiles (Top Consensus Drivers)\n")
        for agent, profile in list(profiles.items())[:5]:
            role_dist = profile.get("role_distribution", {})
            roles_str = ", ".join(f"{r}: {c}" for r, c in sorted(role_dist.items(), key=lambda x: -x[1]))
            lines.append(f"**{agent}** ({profile['consensus_events']} posts)")
            lines.append(f"- Primary role: {profile['primary_role']}")
            lines.append(f"- Role breakdown: {roles_str}")
            lines.append("")

    # Notable observations
    lines.append("## Notable Observations\n")
    # Find posts with interesting characteristics
    high_consensus = [r for r in post_results if r.get("consensus") == "YES" and r.get("comment_count", 0) > 10]
    no_consensus = [r for r in post_results if r.get("consensus") == "NO"]

    if high_consensus:
        lines.append(
            f"- **{len(high_consensus)}** posts achieved full consensus even with substantial "
            f"comment threads (10+ comments)."
        )
    if no_consensus:
        lines.append(
            f"- **{len(no_consensus)}** posts ({len(no_consensus)/total*100:.1f}%) had no consensus, "
            f"suggesting ongoing areas of disagreement."
        )
    lines.append("")

    # Methodology
    lines.append("## Methodology\n")
    lines.append(
        "1. Loaded the top 100 most-upvoted posts from the Moltbook dataset "
        "(lysandrehooh/moltbook on HuggingFace).\n"
        "2. Reconstructed nested comment threads from the relational dataset structure "
        "(posts and comments linked via post_id, with parent_id relationships).\n"
        "3. **Pass 1:** Used Gemini 2.5 Flash to analyze each post's comment thread for "
        "consensus (YES/NO/PARTIAL), formation patterns, key moments, and consensus-driving agents.\n"
        "4. **Pass 2:** Sent all per-post summaries to Gemini for pattern clustering, "
        "identifying 3-5 recurring consensus formation patterns.\n"
        "5. **Pass 3:** Aggregated consensus-driver data across all posts to identify "
        "disproportionately influential agents, compute concentration metrics, and "
        "compare against a uniform distribution baseline.\n"
    )

    report = "\n".join(lines)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    return report
