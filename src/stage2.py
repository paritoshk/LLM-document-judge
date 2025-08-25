"""Stage 2: Visual selection judgment using multimodal LLM"""

import os
import json
from typing import List, Dict, Tuple
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from .json_utils import _first_top_level_json_block, _clean_json_minor_issues
import logfire

# Configure logfire
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
if LOGFIRE_TOKEN:
    logfire.configure(token=LOGFIRE_TOKEN)
else:
    logfire.configure()

@logfire.instrument("stage2.judge_visual_selection")
def judge_visual_selection(page_images: List[Tuple], all_candidates_text: str) -> Dict:
    """
    Stage 2: Pass raw 'all_candidates' string (unknown schema).
    The model must return ONLY: {"selected_ids":[...], "evidence":"..."}
    Indexing rule:
      - If top-level is an array, index that array 0..N-1 (appearance order).
      - If top-level is an object with an array field (e.g., 'products'), index that array 0..N-1.
    """
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    if not all_candidates_text:
        return {"selected_ids": [], "evidence": "empty candidates"}

    system_prompt = (
        "Return ONLY one JSON object with keys: selected_ids (array of integers), evidence (string). "
        "Start with '{' and end with '}'. No prose, no preamble."
    )

    # Keep the candidate JSON verbatim so Claude can infer indexing from order of appearance
    content_blocks = [
        {"type": "text", "text":
            "Find visual selection marks on the provided PDF images.\n"
            "Use these rules:\n"
            "- Treat the provided candidates JSON verbatim.\n"
            "- If root is an array, index = array index (0-based).\n"
            "- If root is an object with an array (e.g., 'products'/'items'), index = that array index (0-based).\n"
            "- Return ONLY JSON: {\"selected_ids\": [...], \"evidence\": \"...\"}.\n\n"
            "CANDIDATES_JSON:\n" + all_candidates_text
        }
    ]

    for page_num, media_type, base64_data in page_images:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": base64_data}
        })

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1800,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": content_blocks,}]
    )

    # --- Parse judge response (force JSON using your helpers) ---
    judge_text = "".join(
        getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
    )

    # Extract and clean the first JSON-looking block
    json_str = _first_top_level_json_block(judge_text)
    json_str = _clean_json_minor_issues(json_str)

    try:
        payload = json.loads(json_str)
    except Exception:
        payload = {}

    # Normalize to expected shape
    if not isinstance(payload, dict):
        payload = {}

    # Accept either "selected_ids" or "selected"
    sel = payload.get("selected_ids")
    if not isinstance(sel, list):
        sel = payload.get("selected", [])

    # Coerce to list[int]
    if isinstance(sel, (list, tuple)):
        norm_ids = []
        for x in sel:
            if isinstance(x, int):
                norm_ids.append(x)
            elif isinstance(x, str) and x.strip().isdigit():
                norm_ids.append(int(x.strip()))
        sel = norm_ids
    else:
        sel = []

    evidence = payload.get("evidence")
    if evidence is None:
        evidence = ""

    payload = {"selected_ids": sel, "evidence": str(evidence)}
    return payload

__all__ = ["judge_visual_selection"]