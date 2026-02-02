# MoltbookGovernanceAnalysis

Analyzes how AI agents arrive at consensus in [Moltbook](https://moltbook.com) discussion threads. Uses Gemini 2.5 Flash to perform a three-pass analysis on the top 100 most-upvoted posts: per-post consensus detection, cross-post pattern clustering, and agent influence analysis.

## Setup

Requires Python 3.13+.

```bash
pip install -r requirements.txt
cp .env.example .env  # Then add your Google AI API key
```

Get a Google AI API key at https://aistudio.google.com/apikey.

## Usage

```bash
# Dry run — analyzes 5 posts to validate setup
python main.py --dry-run

# Full analysis — 100 posts
python main.py
```

Results are written to `output/consensus_report.md`. Intermediate per-post results are cached in `output/raw_results.json` so re-runs skip already-analyzed posts.

## How It Works

The analysis runs in three passes:

1. **Per-post consensus detection** — Each post's comment thread is sent to Gemini 2.5 Flash, which determines whether consensus emerged (YES/NO/PARTIAL), describes the formation pattern, identifies key moments, names the agents who drove the outcome, and extracts evidence quotes.

2. **Pattern clustering** — All per-post summaries are sent to Gemini in a single call to identify 3-5 recurring consensus formation patterns across the dataset and classify each post into one.

3. **Agent influence analysis** — Consensus-driver data is aggregated across all posts to build a frequency table of which agents drive consensus most often, compute concentration metrics (do the top N agents account for a disproportionate share?), profile each top agent's typical role, and compare against a uniform distribution baseline.

## Project Structure

```
MoltbookGovernanceAnalysis/
├── requirements.txt          # Python dependencies
├── .env.example              # Template for API key
├── config.py                 # API key, model, constants
├── main.py                   # Orchestrator (load → parse → analyze → report)
├── data/
│   ├── loader.py             # Load HF dataset, select top 100 by upvotes
│   └── comment_parser.py     # Parse comments JSON, flatten nested threads
├── analysis/
│   ├── consensus_detector.py # Pass 1: per-post Gemini analysis
│   ├── pattern_classifier.py # Pass 2: cross-post pattern clustering
│   └── agent_influence.py    # Pass 3: agent frequency & concentration
├── report/
│   └── generator.py          # Generate Markdown report
└── output/                   # Generated artifacts (gitignored)
    ├── raw_results.json
    └── consensus_report.md
```

## Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `CONCURRENCY_LIMIT` | `5` | Max concurrent API calls |
| `TOP_POSTS_COUNT` | `100` | Number of top posts to analyze |
| `DRY_RUN_COUNT` | `5` | Number of posts in dry-run mode |
| `CHUNK_SIZE` | `50` | Comments per chunk for large threads |
| `MAX_COMMENTS_FULL_THREAD` | `100` | Threshold before chunking kicks in |

## Dataset

Uses [`Ayanami0730/moltbook_data`](https://huggingface.co/datasets/Ayanami0730/moltbook_data) from HuggingFace. The comment schema is auto-discovered at runtime from the first post's `comments_json` field.
