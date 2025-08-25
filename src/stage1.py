"""Stage 1: High-recall candidate extraction using LLM"""

import os
import json
from typing import List, Tuple
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from .json_utils import _first_top_level_json_block, _clean_json_minor_issues, _product_schema_block
import logfire

# Configure logfire
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
if LOGFIRE_TOKEN:
    logfire.configure(token=LOGFIRE_TOKEN)
else:
    logfire.configure()

@logfire.instrument("stage1.extract_all_candidates")
def extract_all_candidates(text: str, pdf_name: str) -> Tuple[str, str, List[dict]]:
    """Stage 1: Extract ALL product variants (high recall) and return (raw_text, parsed_block_str, items_list)."""
    
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = (
        "You are an information-extraction engine. "
        "Return the result as a single JSON object. No prose. "
        "If a field is unknown, use null (or [] for arrays). Do not invent data."
    )
    user_prompt = f"""You are extracting products from a construction submittal.
Extract ALL product variants mentioned in this document.

Include:
 - Every variant in tables (all thicknesses, all model numbers)
 - Every type/series mentioned (e.g., 812, 813, 814, 815, 817)
 - All options and configurations

Domain examples:
 - Gypsum: ALL thicknesses (1/4", 1/2", 5/8"), ALL types (XP, Fire-Shield, etc)
 - Screws: ALL models in the catalog
 - Insulation: ALL type numbers in the series

Extract everything - we'll filter later.
Output as JSON matching this schema:
{_product_schema_block()}

=== DOCUMENT ({pdf_name}) ===
{text}
=== END DOCUMENT ==="""

    # IMPORTANT: each turn is its own dict; no duplicate keys in one dict
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        temperature=0,
        system=system_prompt,
        messages=[
            {"role": "user", "content": "Return ONLY JSON. Start with '{' and end with '}'."},
            {"role": "user", "content": user_prompt},
        ],
    )

    all_candidates = resp.content[0].text if resp.content else ""

    # Keep your existing forceful extraction helpers
    parsed_block_str = _first_top_level_json_block(all_candidates)  # returns a string slice (may be entire)
    try:
        items = json.loads(_clean_json_minor_issues(parsed_block_str))
        if isinstance(items, dict):
            # prefer common container keys if present
            if "products" in items and isinstance(items["products"], list):
                items = items["products"]
            elif "items" in items and isinstance(items["items"], list):
                items = items["items"]
            else:
                # If dict but no obvious array → empty list (avoid dict-iteration bugs)
                items = []
        elif not isinstance(items, list):
            items = []
    except Exception:
        items = []

    return all_candidates, parsed_block_str, items

__all__ = ["extract_all_candidates"]