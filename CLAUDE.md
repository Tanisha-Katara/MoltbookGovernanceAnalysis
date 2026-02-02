# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoltbookGovernanceAnalysis analyzes how AI agents arrive at consensus in Moltbook discussion threads. It uses Gemini 2.5 Flash to perform three-pass analysis on the top 100 most-upvoted posts: per-post consensus detection, cross-post pattern clustering, and agent influence analysis.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # Then add your Google AI API key
```

## Run Commands

```bash
# Dry run (5 posts) — good for testing
python main.py --dry-run

# Full analysis (100 posts)
python main.py
```

Output goes to `output/consensus_report.md` with intermediate results cached in `output/raw_results.json`. Cached results are reused on re-runs to avoid redundant API calls.

## Architecture

- `config.py` — Google AI API key, model settings, constants
- `main.py` — Orchestrator: loads data, runs all three analysis passes, generates report. Supports `--dry-run` flag.
- `data/loader.py` — Loads `Ayanami0730/moltbook_data` from HuggingFace, sorts by upvotes, selects top N posts with comments
- `data/comment_parser.py` — Parses `comments_json` strings, auto-discovers field names (author/text/replies/upvotes) from first post, recursively flattens nested reply trees
- `analysis/consensus_detector.py` — Pass 1: sends each post's thread to Gemini for consensus detection. Uses `asyncio` with semaphore (5 concurrent). Chunks threads over 100 comments.
- `analysis/pattern_classifier.py` — Pass 2: sends all per-post summaries to Gemini to discover 3-5 recurring consensus patterns and classify each post
- `analysis/agent_influence.py` — Pass 3: pure Python aggregation of consensus-driver data. Builds frequency tables, concentration metrics (top-N share), per-agent role profiles, uniform baseline comparison.
- `report/generator.py` — Generates `output/consensus_report.md` with sections: Dataset, Consensus Overview, Discovered Patterns, Agent Influence, Notable Observations, Methodology

## Key Implementation Details

- Gemini client uses lazy initialization (not created at import time) to avoid errors when API key isn't set
- Comment schema is auto-discovered from the first parsed post and cached globally
- Large threads (100+ comments) are chunked into groups of ~50, each summarized by Gemini, then the summaries are analyzed together
- JSON extraction from LLM responses handles bare JSON, markdown-fenced JSON, and JSON embedded in prose
- Raw results are saved after Pass 1, so interrupted runs can resume without re-calling the API
