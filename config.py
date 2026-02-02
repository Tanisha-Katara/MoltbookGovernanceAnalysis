import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
CONCURRENCY_LIMIT = 2  # Free tier limit is 5 RPM, use 2 to account for chunking
TOP_POSTS_COUNT = 500  # Reduced to safely fit in free tier
DRY_RUN_COUNT = 5
CHUNK_SIZE = 50
MAX_COMMENTS_FULL_THREAD = 100

DATASET_NAME = "lysandrehooh/moltbook"
POSTS_SUBSET = "posts"
COMMENTS_SUBSET = "comments"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
RAW_RESULTS_PATH = os.path.join(OUTPUT_DIR, "raw_results.json")
REPORT_PATH = os.path.join(OUTPUT_DIR, "consensus_report.md")
