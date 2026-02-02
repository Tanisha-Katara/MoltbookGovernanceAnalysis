from collections import Counter, defaultdict


def analyze_agent_influence(results: list[dict]) -> dict:
    """Aggregate consensus-driving data across all posts.

    Returns a dict with:
      - agent_frequency: {agent: count} of how many posts each agent drove consensus in
      - ranked_agents: list of (agent, count) sorted descending
      - total_consensus_posts: how many posts had YES or PARTIAL consensus
      - concentration: stats about top-N agent share
      - agent_profiles: per-agent role summaries
      - uniform_baseline: expected frequency if drivers were uniformly distributed
    """
    agent_frequency: Counter = Counter()
    agent_roles: defaultdict[str, list[str]] = defaultdict(list)
    agent_posts: defaultdict[str, list[str]] = defaultdict(list)
    all_participating_agents: set[str] = set()
    consensus_posts = 0

    for r in results:
        consensus = r.get("consensus", "")
        if consensus not in ("YES", "PARTIAL"):
            continue
        consensus_posts += 1

        drivers = r.get("consensus_drivers", [])
        post_title = r.get("post_title", "?")

        for d in drivers:
            agent = d.get("agent", "unknown")
            role = d.get("role", "unknown")
            agent_frequency[agent] += 1
            agent_roles[agent].append(role)
            agent_posts[agent].append(post_title)

        # Track all agents who participated (not just drivers) — we'd need comment data
        # for a full picture, but drivers give us the influence picture

    ranked = agent_frequency.most_common()
    total_driver_events = sum(agent_frequency.values())
    unique_drivers = len(agent_frequency)

    # Concentration metrics
    concentration = {}
    for top_n in (1, 3, 5, 10):
        top_agents = ranked[:top_n]
        top_count = sum(c for _, c in top_agents)
        concentration[f"top_{top_n}"] = {
            "agents": [a for a, _ in top_agents],
            "consensus_events": top_count,
            "share": top_count / total_driver_events if total_driver_events else 0,
        }

    # Agent profiles
    agent_profiles = {}
    for agent, count in ranked[:20]:  # Top 20 agents
        roles = agent_roles[agent]
        role_counts = Counter(roles)
        primary_role = role_counts.most_common(1)[0][0] if role_counts else "unknown"
        agent_profiles[agent] = {
            "consensus_events": count,
            "posts": agent_posts[agent],
            "role_distribution": dict(role_counts),
            "primary_role": primary_role,
        }

    # Uniform baseline
    uniform_expected = consensus_posts / unique_drivers if unique_drivers else 0

    return {
        "agent_frequency": dict(agent_frequency),
        "ranked_agents": ranked,
        "total_consensus_posts": consensus_posts,
        "total_driver_events": total_driver_events,
        "unique_drivers": unique_drivers,
        "concentration": concentration,
        "agent_profiles": agent_profiles,
        "uniform_baseline": uniform_expected,
    }
